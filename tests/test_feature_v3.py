import hashlib

import pytest

from smaip.probes.feature_v3 import FeatureProtocolV3, encode_views, render_boundary


class CharacterTokenizer:
    is_fast = True
    chat_template = 'synthetic-character-chat-template-v1'

    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        assert tokenize is False
        parts = ''.join(f'<{m["role"]}>{m["content"]}</{m["role"]}>' for m in messages)
        return parts + ('<assistant>' if add_generation_prompt else '')

    def __call__(self, text, *, add_special_tokens, truncation, return_offsets_mapping):
        assert add_special_tokens is False and truncation is False and return_offsets_mapping is True
        return {'input_ids': [ord(ch) for ch in text],
                'offset_mapping': [(i, i + 1) for i in range(len(text))]}


def protocol(**changes):
    return FeatureProtocolV3(**{**dict(model_id='Qwen/Qwen2.5-3B-Instruct',
        model_revision='a' * 40, tokenizer_revision='a' * 40,
        chat_template_sha256=hashlib.sha256(CharacterTokenizer.chat_template.encode()).hexdigest()), **changes})


def test_boundary_is_a_real_suffix_after_literal_tool_content():
    tokenizer = CharacterTokenizer()
    text = 'Quoted <tool> and SMAIP_TOOL_CONTENT_BOUNDARY are plain data.'
    base, full, start, end = render_boundary(tokenizer, text)
    assert full == base + '<assistant>'
    assert base[start:end] == text
    encoded = encode_views(tokenizer, text, protocol())
    assert encoded['prefix_token_ids_stable'] is True
    assert encoded['baseline']['content_positions'] == encoded['boundary']['content_positions']
    assert encoded['boundary']['boundary_position'] == len(full) - 1
    assert encoded['boundary']['boundary_token_id'] == ord('>')
    assert encoded['boundary']['boundary_neighbor_ids'] == [ord(ch) for ch in full[-8:]]
    assert len(encoded['boundary']['content_positions']) == len(text)


def test_overlength_and_template_drift_fail_without_truncation():
    tokenizer = CharacterTokenizer()
    with pytest.raises(ValueError, match='chat template differs'):
        encode_views(tokenizer, 'text', protocol(chat_template_sha256='0' * 64))
    with pytest.raises(ValueError, match='truncation is forbidden'):
        encode_views(tokenizer, 'x' * 600, protocol())
    with pytest.raises(ValueError, match='unsupported development feature configuration'):
        protocol(protocol_version=2)


def test_fingerprint_changes_with_rendering_contract():
    current = protocol()
    assert current.protocol_version == 3
    assert current.fingerprint != hashlib.sha256(b'').hexdigest()
    assert current.fingerprint != protocol(max_length=1024).fingerprint
