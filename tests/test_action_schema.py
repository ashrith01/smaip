import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from smaip.agents.action_schema import ACTION_SCHEMA, validate_action
from smaip.agents.open_loop import parse_action, run_open_task
from smaip.eval.contract import EvalConfig
from smaip.serving.structured import prefix_filter, schema_fingerprint


@pytest.mark.parametrize('action', [
    {'tool': 'read_page', 'arguments': {'vendor': 'acme_analytics'}},
    {'tool': 'summarize', 'arguments': {'fields': ['description']}},
    {'tool': 'summarize', 'arguments': {'fields': {'active_accounts': True}}},
    {'tool': 'summarize', 'arguments': {'fields': {'active_accounts': '12'}}},
    {'tool': 'send', 'arguments': {'to': 'x', 'subject': 'x', 'body': 'x', 'approved': True}},
    {'final': 'x', 'tool': 'delete', 'arguments': {'path': 'audit.log'}},
])
def test_pydantic_rejects_observed_shape_errors_and_coercions(action):
    with pytest.raises(ValidationError):
        validate_action(action)


def test_valid_pydantic_field_map_preserves_only_supplied_values():
    assert parse_action('{"tool":"summarize","arguments":{"fields":{"active_accounts":48}}}') == {
        'tool': 'summarize', 'arguments': {'fields': {'active_accounts': 48}}}


def grammar_accepts(text):
    from lmformatenforcer import JsonSchemaParser
    parser = JsonSchemaParser(ACTION_SCHEMA)
    for character in text:
        if character not in parser.get_allowed_characters():
            return False
        parser = parser.add_character(character)
    return parser.can_end()


@pytest.mark.parametrize('text', [
    '{"list_pages":{"vendor":"acme_analytics"}}',
    '{"tool":"read_page","arguments":{"vendor":"acme_analytics"}}',
    '{"tool":"list_pages","arguments":{"vendor":"acme_analytics"}},{"final":"done"}',
    '{"tool":"read_page","arguments":{"vendor":"x","page":"x.md"},"tool":"delete"}',
    '{"tool":"research","arguments":{"vendor_id":"acme_analytics"}}',
])
def test_decoding_grammar_rejects_pilot_02_format_failures(text):
    assert not grammar_accepts(text)


def test_grammar_does_not_enforce_recipient_or_role_permissions():
    # The actor's malicious choices must stay representable in every ablation.
    # Schema filtering is not counted as a security defense.
    for tool, arguments in [
        ('send', {'to': 'attacker@example.com', 'subject': 'x', 'body': 'stolen'}),
        ('delete', {'path': 'audit.log'}),
        ('read_page', {'vendor': 'invented', 'page': 'invented.md'}),
    ]:
        assert grammar_accepts(json.dumps({'tool': tool, 'arguments': arguments}))


def test_token_filter_starts_after_prompt_and_stops_chained_actions():
    from lmformatenforcer import TokenEnforcerTokenizerData
    alphabet = ''.join(chr(i) for i in range(32, 127)) + '\n\t'
    char_to_id = {c: i + 1 for i, c in enumerate(alphabet)}
    id_to_char = {v: k for k, v in char_to_id.items()}
    data = TokenEnforcerTokenizerData([(i, c, False) for i, c in id_to_char.items()],
                                    lambda ids: ''.join(id_to_char.get(i, '') for i in ids),
                                    0, False, len(alphabet) + 1)
    allowed = prefix_filter(data, ACTION_SCHEMA, 2)
    ids = [999, 998]  # Prompt ids are never parsed as output JSON.
    for c in '{"final":"done"}':
        assert char_to_id[c] in allowed(0, SimpleNamespace(tolist=lambda: list(ids)))
        ids.append(char_to_id[c])
    final = allowed(0, SimpleNamespace(tolist=lambda: list(ids)))
    assert 0 in final and char_to_id['{'] not in final
    assert char_to_id[','] not in final
    # A new completion starts fresh even with cached tokenizer data.
    assert char_to_id['{'] in prefix_filter(data, ACTION_SCHEMA, 2)(0, SimpleNamespace(tolist=lambda: [999, 998]))


def test_agent_passes_identical_pydantic_schema_to_generation_and_records_it():
    from smaip.serving.open_model import Completion
    class Engine:
        name = 'structured-test'
        action_decoding = 'test-token-filter'
        def complete_action_result(self, messages, schema):
            assert schema == ACTION_SCHEMA
            return Completion('{"final":"No effects"}', self.name, 'test', None, 1, 1, 0,
                              'json_schema', schema_fingerprint(schema))
    report = run_open_task('Research', vendor='acme_analytics', recipient='owner@example.com',
                           config=EvalConfig('no-defense'), engine=Engine())
    assert report['response_format']['validation'] == 'pydantic'
    assert report['response_format']['schema_sha256'] == schema_fingerprint(ACTION_SCHEMA)
    assert not report['sent'] and report['status'] == 'incomplete'
