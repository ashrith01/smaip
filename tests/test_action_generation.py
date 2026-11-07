from types import SimpleNamespace

import pytest

from smaip.agents.action_generation import Completion, generate_action


def test_structured_adapter_preserves_schema_and_measured_metadata():
    schema = {'type': 'object'}
    calls = []

    class Engine:
        name = 'structured'
        def complete_action_result(self, messages, received_schema):
            calls.append((messages, received_schema))
            return Completion('{"final":"done"}', self.name, 'pinned-model', 'a' * 40,
                              12, 3, 4.5, 'json_schema', 'b' * 64)

    messages = [{'role': 'user', 'content': 'task'}]
    result = generate_action(Engine(), messages, schema)
    assert calls == [(messages, schema)]
    assert result.text == '{"final":"done"}'
    assert result.usage == {'engine': 'structured', 'model_id': 'pinned-model',
                            'revision': 'a' * 40, 'input_tokens': 12,
                            'output_tokens': 3, 'latency_ms': 4.5,
                            'response_format': 'json_schema', 'schema_sha256': 'b' * 64}


def test_result_only_and_scripted_adapters_share_the_same_result_shape():
    class ResultOnly:
        name = 'scripted'
        def complete_result(self, messages):
            return SimpleNamespace(text='{"final":"done"}',
                                   as_dict=lambda: {'text': '{"final":"done"}', 'engine': self.name,
                                                    'input_tokens': None, 'output_tokens': None})

    class Scripted:
        name = 'scripted'
        def complete(self, messages):
            return '{"final":"done"}'

    result_only = generate_action(ResultOnly(), [], {})
    scripted = generate_action(Scripted(), [], {})
    assert result_only == scripted
    assert scripted.usage == {'engine': 'scripted', 'input_tokens': None, 'output_tokens': None}


def test_malformed_completion_fails_closed():
    class Engine:
        def complete_action_result(self, messages, schema):
            return SimpleNamespace(text=None, as_dict=lambda: {})

    with pytest.raises(TypeError, match='text'):
        generate_action(Engine(), [], {})


def test_both_agent_protocols_record_the_same_scripted_usage():
    from smaip.agents.evidence_task import TaskIntent, run_evidence_task
    from smaip.agents.open_loop import run_open_task
    from smaip.eval.contract import EvalConfig

    class Engine:
        name = 'scripted'
        def complete(self, messages):
            return '{"final":"done"}'

    class Library:
        def ids(self):
            return ['acme_analytics']
        def list_pages(self, vendor):
            return ['overview.md']

    engine = Engine()
    open_report = run_open_task('Research', vendor='acme_analytics', recipient='owner@example.com',
                                config=EvalConfig('action-generation', max_steps=1), engine=engine)
    evidence_report = run_evidence_task(
        TaskIntent('acme_analytics', 'owner@example.com', ('overview.md',), review_required=False),
        library=Library(), engine=engine, config=EvalConfig('action-generation', max_steps=1))
    expected = {'engine': 'scripted', 'input_tokens': None, 'output_tokens': None}
    assert next(event for event in open_report['events'] if event['type'] == 'model')['usage'] == expected
    assert next(event for event in evidence_report['events'] if event['type'] == 'model')['usage'] == expected
