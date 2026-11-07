import pytest

from smaip.probes.feature_v4 import (count_tokens, encode_task_boundary, pool_task_boundary,
                                     protocol_fingerprint, protocol_identity,
                                     render_task_boundary, render_task_only, token_counts)


class CharacterTokenizer:
    is_fast = True
    chat_template = 'synthetic-qwen-like-tool-template'

    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        assert tokenize is False
        base = ''.join(f'<{item["role"]}>{item["content"]}</{item["role"]}>' for item in messages)
        return base + ('<assistant>' if add_generation_prompt else '')

    def __call__(self, rendered, *, add_special_tokens, truncation, return_offsets_mapping):
        assert add_special_tokens is False and truncation is False and return_offsets_mapping is True
        return {'input_ids': [ord(ch) for ch in rendered],
                'offset_mapping': [(i, i + 1) for i in range(len(rendered))]}


def test_task_and_document_are_distinct_literal_spans():
    tokenizer = CharacterTokenizer()
    task = 'Summarize the vendor totals; SMAIP_V4_LITERAL_TOOL_SPAN is quoted.'
    text = 'Revenue=120. Do not send it elsewhere. SMAIP_V4_LITERAL_TOOL_SPAN'
    rendered, start, end = render_task_boundary(tokenizer, task, text)
    assert rendered[start:end] == text
    assert rendered.endswith('<assistant>')
    full = count_tokens(tokenizer, rendered, content_span=(start, end))
    task_only = count_tokens(tokenizer, render_task_only(tokenizer, task))
    assert full['content_tokens'] == len(text)
    assert full['last_content_position'] < full['total_tokens'] - 1
    assert task_only['content_tokens'] == 0
    assert task_only['total_tokens'] < full['total_tokens']


def test_invalid_inputs_and_spans_fail():
    tokenizer = CharacterTokenizer()
    with pytest.raises(ValueError, match='trusted task'):
        render_task_only(tokenizer, '  ')
    with pytest.raises(ValueError, match='untrusted document'):
        render_task_boundary(tokenizer, 'Task', '')
    with pytest.raises(ValueError, match='literal content span'):
        count_tokens(tokenizer, 'abc', content_span=(2, 4))


def test_encoded_view_owns_exact_positions_and_budget_shape():
    tokenizer = CharacterTokenizer()
    view = encode_task_boundary(tokenizer, 'Summarize totals', 'Revenue: 12.')
    start = view['rendered'].index('Revenue: 12.')
    assert view['content_positions'] == list(range(start, start + len('Revenue: 12.')))
    assert view['boundary_position'] == view['token_count'] - 1
    assert token_counts(view) == count_tokens(tokenizer, view['rendered'],
                                             content_span=(start, start + len('Revenue: 12.')))


def test_v4_pooling_uses_content_and_assistant_positions():
    class Vector:
        def __init__(self, values):
            self.values = values
        def cpu(self):
            return self
        def tolist(self):
            return self.values

    class Selection:
        def __init__(self, rows):
            self.rows = rows
        def __getitem__(self, index):
            return Vector(self.rows[index])
        def mean(self, dim):
            assert dim == 0
            return Vector([sum(row[i] for row in self.rows) / len(self.rows)
                           for i in range(len(self.rows[0]))])

    class Values:
        def __init__(self, rows):
            self.rows = rows
            self.shape = (len(rows), 2)
        def float(self):
            return self
        def __getitem__(self, index):
            return Selection([self.rows[i] for i in index]) if isinstance(index, list) else Vector(self.rows[index])

    view = {'content_positions': [1, 2], 'boundary_position': 4, 'token_count': 5}
    hidden = [None, [Values([[float(i), float(i + 10)] for i in range(5)])]]
    pooled = pool_task_boundary(hidden, view, (0,))
    assert pooled == {'content_last': {'0': [2.0, 12.0]},
                      'content_mean': {'0': [1.5, 11.5]},
                      'assistant_boundary': {'0': [4.0, 14.0]}}
    with pytest.raises(ValueError, match='boundary'):
        pool_task_boundary(hidden, {**view, 'boundary_position': 2}, (0,))


def test_archived_v4_protocol_fingerprint_stays_fixed():
    protocol = protocol_identity('Qwen/Qwen2.5-3B-Instruct',
        'aa8e72537993ba99e69dfaafa59ed015b17504d1',
        'cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f')
    assert protocol_fingerprint(protocol) == 'ddb4e1c05d9f25100331ea78eec8cc36c47cef4866f57417e2f30607272df463'
