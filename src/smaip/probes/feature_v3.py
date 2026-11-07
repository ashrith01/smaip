"""Forward-only development features at a documented assistant boundary.

Version 3 is deliberately separate from the frozen version-2 probe contract.
No saved version-2 weights or thresholds can be used with these vectors.
"""

from dataclasses import asdict, dataclass
import hashlib
import json
import re

from smaip.probes.protocol import QUERY, SYSTEM, render_tool_content


LAYERS = (6, 18, 30)
RENDERING = 'qwen-tool-inspection-plus-assistant-generation-prompt-v1'


def sha256(value):
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class FeatureProtocolV3:
    model_id: str
    model_revision: str
    tokenizer_revision: str
    chat_template_sha256: str
    dtype: str = 'float16'
    execution_device: str = 'cuda'
    max_length: int = 512
    batch_size: int = 1
    pooling_reduction: str = 'float32'
    token_scope: str = 'fully-contained-tool-content'
    layer_indexing: str = 'hidden_states[layer+1]'
    protocol_version: int = 3
    rendering: str = RENDERING
    boundary_position: str = 'last token of rendered assistant generation prompt'

    def __post_init__(self):
        if not self.model_id or any(not re.fullmatch(r'[0-9a-f]{40}', value)
                                    for value in (self.model_revision, self.tokenizer_revision)):
            raise ValueError('pin model and tokenizer to immutable revisions')
        if not re.fullmatch(r'[0-9a-f]{64}', self.chat_template_sha256):
            raise ValueError('chat template SHA256 is required')
        if (self.protocol_version != 3 or self.rendering != RENDERING or
                self.boundary_position != 'last token of rendered assistant generation prompt' or
                self.token_scope != 'fully-contained-tool-content' or
                self.layer_indexing != 'hidden_states[layer+1]' or
                self.pooling_reduction != 'float32' or self.batch_size != 1 or
                self.dtype != 'float16' or self.execution_device != 'cuda' or
                not 32 <= self.max_length <= 8192):
            raise ValueError('unsupported development feature configuration')

    def as_dict(self):
        return asdict(self)

    @property
    def fingerprint(self):
        return sha256(json.dumps(self.as_dict(), sort_keys=True, separators=(',', ':')))


def render_boundary(tokenizer, text):
    """Require a literal V2 inspection prefix and a nonempty generation suffix."""
    base, start, end = render_tool_content(tokenizer, text)
    messages = [
        {'role': 'system', 'content': SYSTEM},
        {'role': 'user', 'content': QUERY},
        {'role': 'assistant', 'content': 'Tool result follows.'},
        {'role': 'tool', 'content': text},
    ]
    full = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    if not isinstance(full, str) or not full.startswith(base) or len(full) == len(base):
        raise ValueError('generation prompt must append a nonempty suffix to the literal inspection rendering')
    if full[start:end] != text:
        raise ValueError('tool content is transformed at its literal span')
    return base, full, start, end


def encode_views(tokenizer, text, protocol):
    if not getattr(tokenizer, 'is_fast', False) or not isinstance(tokenizer.chat_template, str):
        raise ValueError('fast tokenizer and explicit chat template required')
    if sha256(tokenizer.chat_template) != protocol.chat_template_sha256:
        raise ValueError('chat template differs from protocol')
    base, full, start, end = render_boundary(tokenizer, text)
    encoded = []
    for rendered in (base, full):
        row = tokenizer(rendered, add_special_tokens=False, truncation=False, return_offsets_mapping=True)
        ids, offsets = list(row['input_ids']), list(row['offset_mapping'])
        if not ids or len(ids) != len(offsets):
            raise ValueError('empty or inconsistent tokenization')
        if len(ids) > protocol.max_length:
            raise ValueError('rendered input exceeds feature budget; truncation is forbidden')
        mask = [int(b > a and start <= a and b <= end) for a, b in offsets]
        if not any(mask):
            raise ValueError('no fully contained tool-content tokens')
        encoded.append({'input_ids': ids, 'attention_mask': [1] * len(ids),
                        'content_mask': mask, 'rendered_sha256': sha256(rendered),
                        'content_positions': [i for i, selected in enumerate(mask) if selected],
                        'token_count': len(ids)})
    baseline, boundary = encoded
    prefix_stable = boundary['input_ids'][:len(baseline['input_ids'])] == baseline['input_ids']
    if boundary['content_positions'][-1] >= boundary['token_count'] - 1:
        raise ValueError('boundary position overlaps tool content')
    boundary['boundary_position'] = boundary['token_count'] - 1
    boundary['boundary_token_id'] = boundary['input_ids'][-1]
    boundary['boundary_neighbor_ids'] = boundary['input_ids'][-min(8, boundary['token_count']):]
    boundary['suffix_sha256'] = sha256(full[len(base):])
    return {'baseline': baseline, 'boundary': boundary, 'prefix_token_ids_stable': prefix_stable,
            'content_char_span': [start, end], 'baseline_rendered_sha256': sha256(base),
            'boundary_rendered_sha256': sha256(full)}


def pooled_vectors(hidden_states, view, layers):
    """Pool only selected blocks; convert reductions to float32 before saving."""
    result = {'content_last': {}, 'content_mean': {}}
    positions = view['content_positions']
    boundary = view.get('boundary_position')
    if boundary is not None:
        result['assistant_boundary'] = {}
    for layer in layers:
        if layer < 0 or layer + 1 >= len(hidden_states):
            raise ValueError('selected layer outside model')
        values = hidden_states[layer + 1][0].float()
        if values.shape[0] != view['token_count']:
            raise ValueError('hidden-state token count differs')
        content = values[positions]
        result['content_last'][str(layer)] = content[-1].cpu().tolist()
        result['content_mean'][str(layer)] = content.mean(dim=0).cpu().tolist()
        if boundary is not None:
            result['assistant_boundary'][str(layer)] = values[boundary].cpu().tolist()
    return result
