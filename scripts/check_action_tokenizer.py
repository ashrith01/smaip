"""Check the actual Qwen tokenizer against the Pydantic output grammar.

Tokenizer-only diagnostic; no torch import, model weights or forward pass.
Use an explicitly supplied tokenizer.json from the pinned model revision.
"""
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from smaip.agents.action_schema import ACTION_SCHEMA, validate_action
from smaip.serving.structured import prefix_filter, schema_fingerprint, tokenizer_data


def check(path):
    from tokenizers import Tokenizer
    raw = Tokenizer.from_file(str(path))
    metadata = json.loads(path.read_text())

    class TokenizerAdapter:
        all_special_ids = [x['id'] for x in metadata['added_tokens'] if x['special']]
        eos_token_id = next(x['id'] for x in metadata['added_tokens'] if x['content'] == '<|im_end|>')

        def __len__(self):
            return raw.get_vocab_size(with_added_tokens=True)

        def encode(self, text, **kwargs):
            return raw.encode(text, add_special_tokens=False).ids

        def decode(self, ids, **kwargs):
            return raw.decode(ids, skip_special_tokens=False)

    tokenizer = TokenizerAdapter()
    data = tokenizer_data(tokenizer)

    def accepts(text):
        ids = [999, 998]
        allowed = prefix_filter(data, ACTION_SCHEMA, len(ids))
        for token in tokenizer.encode(text):
            if token not in allowed(0, SimpleNamespace(tolist=lambda: list(ids))):
                return False
            ids.append(token)
        return tokenizer.eos_token_id in allowed(0, SimpleNamespace(tolist=lambda: list(ids)))

    valid = [
        {'tool': 'list_pages', 'arguments': {'vendor': 'acme_analytics'}},
        {'tool': 'read_page', 'arguments': {'vendor': 'acme_analytics', 'page': 'overview.md'}},
        {'tool': 'calculate', 'arguments': {'expression': '120+15'}},
        {'tool': 'summarize', 'arguments': {'fields': {'active_accounts': 48}}},
        {'tool': 'send', 'arguments': {'to': 'evil@example.com', 'subject': 'Test', 'body': 'Revenue 120'}},
        {'tool': 'write', 'arguments': {'path': 'summary.txt', 'content': 'text'}},
        {'tool': 'delete', 'arguments': {'path': 'audit.log'}},
        {'final': 'Résumé checked.'},
    ]
    malformed = [
        '{"list_pages":{"vendor":"acme_analytics"}}',
        '{"tool":"read_page","arguments":{"vendor":"x","page":"x.md"}},{"final":"done"}',
        '{"tool":"research","arguments":{"vendor_id":"x"}}',
        '{"tool":"read_page","arguments":{"vendor":"x","page":"x.md"},"tool":"delete"}',
    ]
    for action in valid:
        validate_action(action)
        if not accepts(json.dumps(action, ensure_ascii=False)):
            raise ValueError('valid action rejected: ' + repr(action))
    if any(accepts(text) for text in malformed):
        raise ValueError('malformed action accepted')
    return {'kind': 'tokenizer-only-schema-check',
            'tokenizer_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'tokenizer_vocab_size': len(tokenizer), 'schema_sha256': schema_fingerprint(ACTION_SCHEMA),
            'valid_sequences_accepted': len(valid), 'malformed_sequences_rejected': len(malformed),
            'model_weights_loaded': False, 'model_quality_measured': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tokenizer_json', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = check(args.tokenizer_json)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
