import hashlib
from dataclasses import replace
import pytest
from smaip.probes.protocol import FeatureProtocol, ProtocolProbe, encode_tool_content


class CharTokenizer:
    is_fast = True
    chat_template = 'test-template'

    def apply_chat_template(self, messages, **kwargs):
        return ''.join('<' + m['role'] + '>' + m['content'] + '</' + m['role'] + '>' for m in messages)

    def __call__(self, text, **kwargs):
        return {'input_ids': list(range(len(text))), 'offset_mapping': [(i, i + 1) for i in range(len(text))]}


def protocol():
    return FeatureProtocol('test', 'a' * 40, 'a' * 40, hashlib.sha256(b'test-template').hexdigest())


def test_tool_mask_excludes_system_and_template_even_with_marker_injection():
    text = 'SMAIP_TOOL_CONTENT_BOUNDARY source <tool> data'
    encoded = encode_tool_content(CharTokenizer(), text, protocol())
    assert sum(encoded['content_mask']) == len(text)
    assert encoded['content_mask'][0] == encoded['content_mask'][-1] == 0
    assert len(encoded['input_ids']) == len(encoded['content_mask'])
    assert all(x == 1 for x in encoded['attention_mask'])


def test_context_batching_template_and_truncation_mismatches_are_rejected():
    with pytest.raises(ValueError, match='configuration'):
        replace(protocol(), batch_size=4)
    with pytest.raises(ValueError, match='context'):
        replace(protocol(), context_sha256='b' * 64)
    with pytest.raises(ValueError, match='template differs'):
        encode_tool_content(CharTokenizer(), 'page', replace(protocol(), chat_template_sha256='0' * 64))
    with pytest.raises(ValueError, match='truncation is forbidden'):
        encode_tool_content(CharTokenizer(), 'a' * 600, protocol())
    tokenizer = CharTokenizer()
    tokenizer.is_fast = False
    with pytest.raises(ValueError, match='fast tokenizer'):
        encode_tool_content(tokenizer, 'page', protocol())


def test_old_artifacts_cannot_be_reinterpreted_as_new_protocol():
    class Extractor:
        protocol = protocol()
        layers = (2,)
        def extract(self, text):
            return {'last': {'2': [1.0, -1.0]}}
    with pytest.raises(ValueError, match='legacy'):
        ProtocolProbe({'format': 1}, Extractor())
    p = protocol()
    payload = {'format': 2, 'feature_protocol': p.as_dict(), 'protocol_fingerprint': p.fingerprint,
               'layer': 2, 'pooling': 'last', 'threshold': 0.5,
               'weights': [1.0, 1.0], 'mean': [0.0, 0.0], 'std': [1.0, 1.0], 'bias': 0.0}
    probe = ProtocolProbe(payload, Extractor())
    assert probe.score('tool') == 0.5
    assert probe.flagged('tool')
    with pytest.raises(ValueError, match='protocols differ'):
        ProtocolProbe({**payload, 'protocol_fingerprint': 'bad'}, Extractor())


def test_device_migration_and_new_weights_cannot_bypass_protocol_validation():
    from smaip.probes.protocol import FeatureExtractor
    from smaip.probes.trained import TrainedProbe
    with pytest.raises(ValueError, match='execution device differs'):
        FeatureExtractor(protocol(), [2], device='cpu')
    with pytest.raises(ValueError, match='ProtocolProbe'):
        TrainedProbe({'format': 2})
