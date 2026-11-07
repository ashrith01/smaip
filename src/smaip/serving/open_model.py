"""Opt-in open-model generation. Offline HF or a self-hosted vLLM endpoint.

No OpenAI SDK, hosted provider, or API key is involved. Constructing an engine
never loads weights or opens a connection; mock/stub selectors stay unchanged.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
import os
import re
import time
from urllib.parse import urlsplit

from smaip.agents.action_generation import Completion
from smaip.errors import UnknownEngine, SmaipError
from smaip.serving.engines import Engine


class OpenModelUnavailable(SmaipError):
    pass


@dataclass(frozen=True)
class OpenModelConfig:
    model_id: str = 'Qwen/Qwen2.5-3B-Instruct'
    revision: str = 'aa8e72537993ba99e69dfaafa59ed015b17504d1'
    device: str = 'cpu'
    dtype: str = 'float32'
    max_new_tokens: int = 256
    max_input_tokens: int = 2048
    base_url: str = 'http://127.0.0.1:8001/v1'

    def __post_init__(self):
        if not self.model_id or not re.fullmatch(r'[0-9a-f]{40}', self.revision):
            raise ValueError('model id and pinned revision are required')
        if self.device not in {'cpu', 'cuda'} or self.dtype not in {'float16', 'float32'}:
            raise ValueError('unsupported device or precision')
        if not 1 <= self.max_new_tokens <= 4096 or not 32 <= self.max_input_tokens <= 8192:
            raise ValueError('invalid generation budget')
        url = urlsplit(self.base_url)
        if url.scheme != 'http' or url.hostname not in {'localhost', '127.0.0.1', '::1'} or url.username or url.password or url.query or url.fragment:
            raise ValueError('vLLM must be a loopback HTTP endpoint; use SSH forwarding for a remote GPU')
        if url.path.rstrip('/') != '/v1':
            raise ValueError('vLLM base URL must end in /v1')

    @classmethod
    def from_env(cls):
        return cls(model_id=os.environ.get('SMAIP_OPEN_MODEL_ID', cls.model_id),
                   revision=os.environ.get('SMAIP_OPEN_MODEL_REVISION', cls.revision),
                   device=os.environ.get('SMAIP_OPEN_MODEL_DEVICE', 'cpu'),
                   dtype=os.environ.get('SMAIP_OPEN_MODEL_DTYPE', 'float32'),
                   max_new_tokens=int(os.environ.get('SMAIP_OPEN_MODEL_MAX_NEW_TOKENS', '256')),
                   max_input_tokens=int(os.environ.get('SMAIP_OPEN_MODEL_MAX_INPUT_TOKENS', '2048')),
                   base_url=os.environ.get('SMAIP_VLLM_BASE_URL', cls.base_url))

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


def validate_messages(messages):
    if not messages or any(not isinstance(m, dict) or m.get('role') not in {'system', 'user', 'assistant', 'tool'} or not isinstance(m.get('content'), str) for m in messages):
        raise ValueError('messages must contain valid role/content pairs')
    return [{'role': m['role'], 'content': m['content']} for m in messages]


class HfLocalEngine(Engine):
    name = 'hf-local'
    action_decoding = 'lm-format-enforcer-0.11.3'

    def __init__(self, config):
        self.config = config
        self.cache_namespace = self.name + ':' + config.fingerprint
        self._structured_tokenizer = None
        self._structured_data = None

    def complete_result(self, messages):
        return self._complete_result(messages)

    def complete_action_result(self, messages, schema):
        return self._complete_result(messages, schema=schema)

    def _complete_result(self, messages, *, schema=None):
        chat = validate_messages(messages)
        try:
            from huggingface_hub import snapshot_download
            from smaip.probes.activations import _load_hf, resolve_device
            device = resolve_device(self.config.device, 'hf')
            snapshot = snapshot_download(self.config.model_id, revision=self.config.revision, local_files_only=True)
            model, tokenizer = _load_hf(snapshot, device, self.config.dtype)
            import torch
            prompt = tokenizer.apply_chat_template(chat, tokenize=False, add_generation_prompt=True)
            encoded = tokenizer(prompt, return_tensors='pt', add_special_tokens=False, truncation=False)
            width = int(encoded['input_ids'].shape[-1])
            if width > self.config.max_input_tokens:
                raise OpenModelUnavailable('prompt exceeds configured token budget; no truncation was applied')
            encoded = {key: value.to(device) for key, value in encoded.items()}
            kwargs = {}
            fingerprint = None
            if schema is not None:
                from smaip.serving.structured import tokenizer_data, prefix_filter, schema_fingerprint
                if self._structured_tokenizer is not tokenizer:
                    self._structured_data = tokenizer_data(tokenizer)
                    self._structured_tokenizer = tokenizer
                kwargs['prefix_allowed_tokens_fn'] = prefix_filter(self._structured_data, schema, width)
                fingerprint = schema_fingerprint(schema)
            started = time.perf_counter()
            with torch.no_grad():
                generated = model.generate(**encoded, max_new_tokens=self.config.max_new_tokens,
                                           do_sample=False, pad_token_id=tokenizer.eos_token_id, **kwargs)
            new_ids = generated[0, width:]
            text = tokenizer.decode(new_ids, skip_special_tokens=True)
            return Completion(text, self.name, self.config.model_id, self.config.revision, width,
                              int(new_ids.shape[-1]), (time.perf_counter() - started) * 1000,
                              'json_schema' if schema is not None else 'text', fingerprint)
        except OpenModelUnavailable:
            raise
        except Exception as exc:
            raise OpenModelUnavailable('local HF generation failed; check cached revision, hf dependencies, device and memory') from exc

    def complete(self, messages):
        return self.complete_result(messages).text


class VllmLocalEngine(Engine):
    name = 'vllm-local'
    action_decoding = 'vllm-json-schema'

    def __init__(self, config, *, client=None):
        self.config = config
        self.client = client
        self.cache_namespace = self.name + ':' + config.fingerprint

    def complete_result(self, messages):
        return self._complete_result(messages)

    def complete_action_result(self, messages, schema):
        return self._complete_result(messages, schema=schema)

    def _complete_result(self, messages, *, schema=None):
        import httpx
        chat = validate_messages(messages)
        started = time.perf_counter()
        payload = {'model': self.config.model_id, 'messages': chat, 'temperature': 0,
                   'max_tokens': self.config.max_new_tokens, 'stream': False}
        fingerprint = None
        if schema is not None:
            from smaip.serving.structured import schema_fingerprint
            payload['response_format'] = {'type': 'json_schema', 'json_schema': {'name': 'smaip_action', 'schema': schema}}
            fingerprint = schema_fingerprint(schema)
        try:
            if self.client is None:
                with httpx.Client(timeout=90, trust_env=False, follow_redirects=False) as client:
                    response = client.post(self.config.base_url.rstrip('/') + '/chat/completions', json=payload)
            else:
                response = self.client.post(self.config.base_url.rstrip('/') + '/chat/completions', json=payload)
            response.raise_for_status()
            result = response.json()
            text = result['choices'][0]['message']['content']
            if not isinstance(text, str):
                raise ValueError('response content is not text')
            usage = result.get('usage') or {}
            counts = [usage.get('prompt_tokens'), usage.get('completion_tokens')]
            if any(value is not None and (type(value) is not int or value < 0) for value in counts):
                raise ValueError('invalid token usage')
            # The service does not attest its model commit. Keep revision unknown.
            return Completion(text, self.name, self.config.model_id, None, counts[0], counts[1],
                              (time.perf_counter() - started) * 1000,
                              'json_schema' if schema is not None else 'text', fingerprint)
        except Exception as exc:
            raise OpenModelUnavailable('self-hosted vLLM generation failed; check its endpoint, served model and token budget') from exc

    def complete(self, messages):
        return self.complete_result(messages).text


def configured_engine(name):
    if os.environ.get('SMAIP_OPEN_MODEL_ENABLE', '').lower() not in {'1', 'true', 'yes'}:
        raise UnknownEngine('open-model generation is off; set SMAIP_OPEN_MODEL_ENABLE=1 to opt in')
    try:
        config = OpenModelConfig.from_env()
    except ValueError as exc:
        raise UnknownEngine('invalid open-model configuration') from exc
    return HfLocalEngine(config) if name == 'hf-local' else VllmLocalEngine(config)
