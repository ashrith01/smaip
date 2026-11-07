"""Synthetic numeric fixtures test split isolation; they are not GPU evidence."""
import hashlib
import json
from pathlib import Path

import pytest

from smaip.probes import pipeline_v2 as pipeline
from smaip.probes.manifest import load_manifest
from smaip.probes.protocol import FeatureProtocol


CORPUS = Path(__file__).resolve().parents[1] / 'data/v2/development-01.jsonl'
PROVENANCE = CORPUS.with_name('development-01.provenance.json')


def collection(folder, *, change_test=False, change_calibration=False):
    folder.mkdir()
    records, manifest, review = pipeline.read_corpus(CORPUS, PROVENANCE)
    (folder / 'corpus.jsonl').write_bytes(CORPUS.read_bytes())
    pipeline.write_json(folder / 'provenance.json', review)
    protocol = FeatureProtocol(pipeline.MODEL, pipeline.REVISION, pipeline.REVISION, 'a' * 64)
    rows = []
    for i, record in enumerate(records):
        value = (1 if record.label else -1) * (2 + i / 100)
        if change_test and record.split == 'test':
            value = -value * 100
        if change_calibration and record.split == 'calibration' and not record.label:
            value = 100
        vector = [value, value * 0.25]
        rows.append({'id': record.id, 'text_sha256': hashlib.sha256(record.text.encode()).hexdigest(),
                     'features': {'token_count': 4, 'rendered_sha256': 'b' * 64,
                                  'last': {'18': vector}, 'mean': {'18': [v * 0.5 for v in vector]}}})
    (folder / 'vectors.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    meta = {'status': 'completed', 'kind': 'v2-feature-collection', 'scope': 'development-only',
            'feature_protocol': protocol.as_dict(), 'protocol_fingerprint': protocol.fingerprint,
            'layer': 18, 'dim': 2, 'manifest': manifest,
            'files_sha256': {name: pipeline.digest(folder / name) for name in ('corpus.jsonl', 'provenance.json', 'vectors.jsonl')}}
    pipeline.write_json(folder / 'collection.json', meta)
    return folder


def test_fit_isolates_test_data_and_evaluation_uses_frozen_models(tmp_path):
    first = collection(tmp_path / 'first')
    second = collection(tmp_path / 'second', change_test=True)
    pipeline.fit(first, tmp_path / 'models-a', steps=60)
    pipeline.fit(second, tmp_path / 'models-b', steps=60)
    for name in ('linear.json', 'activation.json'):
        a = json.loads((tmp_path / 'models-a' / name).read_text())
        b = json.loads((tmp_path / 'models-b' / name).read_text())
        for key in ('weights', 'bias', 'mean', 'std', 'threshold', 'calibration'):
            assert a[key] == b[key], key
        assert a['format'] == 2 and not a['test_used_for_fitting_or_threshold']
        assert not a['calibration']['low_fpr_evidence_sufficient']
    before = {p.name: p.read_bytes() for p in (tmp_path / 'models-a').iterdir()}
    report = pipeline.evaluate(first, tmp_path / 'models-a', tmp_path / 'evaluation')
    assert report['metrics']['linear.json']['tpr'] == 1
    assert report['metrics']['linear.json']['fpr'] == 0
    assert report['metrics']['linear.json']['threshold_source'] == 'independent-calibration'
    assert not report['independent_accuracy_claim']
    assert before == {p.name: p.read_bytes() for p in (tmp_path / 'models-a').iterdir()}
    with pytest.raises(FileExistsError):
        pipeline.fit(first, tmp_path / 'models-a')


def test_calibration_changes_threshold_but_not_train_moments_or_weights(tmp_path):
    first = collection(tmp_path / 'first')
    second = collection(tmp_path / 'second', change_calibration=True)
    pipeline.fit(first, tmp_path / 'models-a', steps=60)
    pipeline.fit(second, tmp_path / 'models-b', steps=60)
    a = json.loads((tmp_path / 'models-a/linear.json').read_text())
    b = json.loads((tmp_path / 'models-b/linear.json').read_text())
    for key in ('weights', 'bias', 'mean', 'std'):
        assert a[key] == b[key]
    assert a['threshold'] != b['threshold']
    records, _ = load_manifest(CORPUS)
    train_values = [(1 if row.label else -1) * (2 + i / 100)
                    for i, row in enumerate(records) if row.split == 'train']
    assert a['mean'][0] == pytest.approx(sum(train_values) / len(train_values))


def test_tampered_vectors_and_frozen_models_are_rejected(tmp_path):
    source = collection(tmp_path / 'features')
    pipeline.fit(source, tmp_path / 'models', steps=20)
    model = tmp_path / 'models/linear.json'
    model.write_text(model.read_text() + ' ')
    with pytest.raises(ValueError, match='checksum differs'):
        pipeline.evaluate(source, tmp_path / 'models', tmp_path / 'evaluation')
    (source / 'vectors.jsonl').write_text('{}\n')
    with pytest.raises(ValueError, match='checksum mismatch'):
        pipeline.fit(source, tmp_path / 'new-models')


def test_partial_or_nonfinite_collection_cannot_be_fitted(tmp_path):
    source = collection(tmp_path / 'features')
    vector_path = source / 'vectors.jsonl'
    rows = [json.loads(line) for line in vector_path.read_text().splitlines()]
    rows[0]['features']['last']['18'][0] = float('nan')
    vector_path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    meta_path = source / 'collection.json'
    meta = json.loads(meta_path.read_text())
    meta['files_sha256']['vectors.jsonl'] = pipeline.digest(vector_path)
    pipeline.write_json(meta_path, meta)
    with pytest.raises(ValueError, match='Invalid vector'):
        pipeline.fit(source, tmp_path / 'models')
    meta['status'] = 'partial'
    pipeline.write_json(meta_path, meta)
    with pytest.raises(ValueError, match='Incomplete'):
        pipeline.fit(source, tmp_path / 'other-models')
