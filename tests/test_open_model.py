import httpx
import pytest
from fastapi.testclient import TestClient
from smaip.errors import UnknownEngine
from smaip.serving.app import create_app
from smaip.serving.engines import engine_for_model
from smaip.serving.open_model import HfLocalEngine, OpenModelConfig, OpenModelUnavailable, VllmLocalEngine


def test_new_open_model_selectors_require_opt_in_and_construct_lazily(monkeypatch):
    monkeypatch.delenv('SMAIP_OPEN_MODEL_ENABLE', raising=False)
    with pytest.raises(UnknownEngine, match='off'):
        engine_for_model('hf-local')
    monkeypatch.setenv('SMAIP_OPEN_MODEL_ENABLE', '1')
    assert isinstance(engine_for_model('hf-local'), HfLocalEngine)
    assert isinstance(engine_for_model('vllm-local'), VllmLocalEngine)


def test_vllm_uses_self_hosted_server_and_records_actual_usage():
    def serve(request):
        assert request.url == 'http://127.0.0.1:8001/v1/chat/completions'
        assert 'authorization' not in request.headers
        return httpx.Response(200, json={'choices': [{'message': {'content': 'draft'}}],
                                         'usage': {'prompt_tokens': 12, 'completion_tokens': 3}})
    client = httpx.Client(transport=httpx.MockTransport(serve))
    engine = VllmLocalEngine(OpenModelConfig(), client=client)
    result = engine.complete_result([{'role': 'user', 'content': 'summarize'}])
    assert result.text == 'draft' and result.input_tokens == 12 and result.output_tokens == 3
    assert result.revision is None  # The endpoint has not attested a commit.


def test_redirects_or_missing_usage_are_not_fabricated():
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(302, headers={'Location': 'https://example.com'})))
    engine = VllmLocalEngine(OpenModelConfig(), client=client)
    with pytest.raises(OpenModelUnavailable):
        engine.complete([{'role': 'user', 'content': 'hi'}])
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={'choices': [{'message': {'content': 'hi'}}]})))
    result = VllmLocalEngine(OpenModelConfig(), client=client).complete_result([{'role': 'user', 'content': 'hi'}])
    assert result.input_tokens is None and result.output_tokens is None


def test_cache_namespace_changes_with_model_configuration_and_api_can_use_adapter():
    a = VllmLocalEngine(OpenModelConfig())
    b = VllmLocalEngine(OpenModelConfig(max_new_tokens=64))
    assert a.cache_namespace != b.cache_namespace
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={'choices': [{'message': {'content': 'real transport boundary'}}]})))
    api = TestClient(create_app(engine=VllmLocalEngine(OpenModelConfig(), client=client)))
    response = api.post('/v1/chat/completions', json={'model': 'vllm-local', 'messages': [{'role': 'user', 'content': 'hi'}]})
    assert response.status_code == 200
    assert response.json()['choices'][0]['message']['content'] == 'real transport boundary'


def test_nonlocal_endpoint_and_backend_errors_fail_closed():
    with pytest.raises(ValueError, match='loopback'):
        OpenModelConfig(base_url='http://example.com/v1')
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(503)))
    api = TestClient(create_app(engine=VllmLocalEngine(OpenModelConfig(), client=client)))
    response = api.post('/v1/chat/completions', json={'messages': [{'role': 'user', 'content': 'hi'}]})
    assert response.status_code == 503
    assert response.json()['detail']['type'] == 'backend_unavailable'


def test_api_preserves_exact_usage_on_cache_hit_and_declares_no_inference():
    calls = []
    def serve(request):
        calls.append(request)
        return httpx.Response(200, json={'choices': [{'message': {'content': 'a'}}],
                                         'usage': {'prompt_tokens': 17, 'completion_tokens': 2}})
    client = httpx.Client(transport=httpx.MockTransport(serve))
    api = TestClient(create_app(engine=VllmLocalEngine(OpenModelConfig(), client=client)))
    payload = {'messages': [{'role': 'user', 'content': 'hi'}]}
    first = api.post('/v1/chat/completions', json=payload).json()
    second = api.post('/v1/chat/completions', json=payload).json()
    assert first['usage'] == second['usage'] == {'prompt_tokens': 17, 'completion_tokens': 2, 'total_tokens': 19}
    assert first['smaip']['inference_executed'] and not second['smaip']['inference_executed']
    assert len(calls) == 1
    assert second['smaip']['usage_kind'] == 'backend-reported'
    assert api.post('/v1/chat/completions', json={**payload, 'temperature': 0.9}).status_code == 400


def test_completion_metadata_evicted_with_cache_entry():
    from smaip.serving.cache import ExactPromptCache
    cache = ExactPromptCache(max_entries=1)
    cache.put('a', 'one', metadata={'input_tokens': 2})
    cache.put('b', 'two', metadata={'input_tokens': 3})
    assert cache.metadata('a') == {}
    assert cache.metadata('b') == {'input_tokens': 3}


def test_vllm_agent_requests_pydantic_schema_and_never_silently_falls_back():
    import json
    from smaip.agents.action_schema import ACTION_SCHEMA
    requests = []
    def serve(request):
        payload = json.loads(request.content)
        requests.append(payload)
        assert payload['response_format']['type'] == 'json_schema'
        assert payload['response_format']['json_schema']['schema'] == ACTION_SCHEMA
        return httpx.Response(200, json={'choices': [{'message': {'content': '{"final":"done"}'}}]})
    engine = VllmLocalEngine(OpenModelConfig(), client=httpx.Client(transport=httpx.MockTransport(serve)))
    result = engine.complete_action_result([{'role': 'user', 'content': 'research'}], ACTION_SCHEMA)
    assert result.response_format == 'json_schema' and result.schema_sha256
    assert len(requests) == 1


def test_hf_attaches_token_filter_only_for_actions_and_reuses_tokenizer_data(monkeypatch):
    import contextlib
    import sys
    from types import SimpleNamespace
    import smaip.probes.activations as activations
    import smaip.serving.structured as structured
    from smaip.agents.action_schema import ACTION_SCHEMA
    class Tensor:
        shape = (1, 2)
        def to(self, device):
            return self
    class Output:
        def __getitem__(self, key):
            return SimpleNamespace(shape=(1,))
    class Tokenizer:
        eos_token_id = 3
        def apply_chat_template(self, *args, **kwargs):
            return 'prompt'
        def __call__(self, *args, **kwargs):
            return {'input_ids': Tensor()}
        def decode(self, *args, **kwargs):
            return '{"final":"done"}'
    generation_calls, builds, filters = [], [], []
    def generate(**kwargs):
        generation_calls.append(kwargs)
        return Output()
    def build_filter(data, schema, width):
        filters.append((data, schema, width))
        return lambda batch, tokens: [3]
    tokenizer = Tokenizer()
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(no_grad=contextlib.nullcontext))
    monkeypatch.setitem(sys.modules, 'huggingface_hub', SimpleNamespace(snapshot_download=lambda *a, **k: '/cached/pinned'))
    monkeypatch.setattr(activations, 'resolve_device', lambda *a: 'cpu')
    monkeypatch.setattr(activations, '_load_hf', lambda *a: (SimpleNamespace(generate=generate), tokenizer))
    monkeypatch.setattr(structured, 'tokenizer_data', lambda tokenizer: builds.append(tokenizer) or 'cached-data')
    monkeypatch.setattr(structured, 'prefix_filter', build_filter)
    engine = HfLocalEngine(OpenModelConfig())
    chat = [{'role': 'user', 'content': 'research'}]
    assert engine.complete_result(chat).response_format == 'text'
    assert 'prefix_allowed_tokens_fn' not in generation_calls[0]
    for _ in range(2):
        completion = engine.complete_action_result(chat, ACTION_SCHEMA)
        assert completion.response_format == 'json_schema' and completion.schema_sha256
        assert callable(generation_calls[-1]['prefix_allowed_tokens_fn'])
    assert len(builds) == 1 and len(filters) == 2
    assert filters[0] == ('cached-data', ACTION_SCHEMA, 2)
