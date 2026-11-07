"""V2 collection, train-only fitting, calibration and frozen test evaluation.

Each stage writes a fresh directory. Layer and hyperparameters are fixed before
collection; there is no test-driven layer sweep or implicit V1 artifact reuse.
"""
import argparse
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import platform

from smaip.probes.logistic import predict_proba, standardize, train_logistic
from smaip.probes.low_fpr import calibrate, evaluate_frozen
from smaip.probes.manifest import load_manifest
from smaip.probes.protocol import FeatureExtractor, FeatureProtocol, ProtocolProbe


MODEL = 'Qwen/Qwen2.5-3B-Instruct'
REVISION = 'aa8e72537993ba99e69dfaafa59ed015b17504d1'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def fresh(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    return path


def source_hashes():
    root = Path(__file__).resolve().parents[1]
    return {str(p.relative_to(root)): digest(p) for p in sorted(root.rglob('*.py'))}


def read_corpus(corpus, provenance):
    records, manifest = load_manifest(Path(corpus))
    review = json.loads(Path(provenance).read_text())
    require(review.get('corpus_sha256') == digest(corpus), 'Corpus differs from provenance record')
    require(review.get('scope') == 'development-only', 'This initial pipeline requires a development-only corpus')
    require(review.get('third_party_material') is False and review.get('label_review'),
            'Original-corpus provenance and label review are required')
    return records, manifest, review


def collect(corpus, provenance, output, *, layer=18):
    records, manifest, review = read_corpus(corpus, provenance)
    require(type(layer) is int and layer >= 0, 'Layer must be nonnegative')
    output = fresh(output)
    # An incomplete collection remains incomplete and cannot be fitted.
    import torch
    from huggingface_hub import snapshot_download
    from transformers import AutoConfig, AutoTokenizer
    require(torch.cuda.is_available(), 'V2 collection requires CUDA; no mock or CPU fallback')
    snapshot = snapshot_download(MODEL, revision=REVISION, local_files_only=True)
    tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True, use_fast=True)
    config = AutoConfig.from_pretrained(snapshot, local_files_only=True)
    require(layer < config.num_hidden_layers, 'Layer outside pinned model')
    require(isinstance(tokenizer.chat_template, str), 'An explicit chat template is required')
    protocol = FeatureProtocol(MODEL, REVISION, REVISION,
                               hashlib.sha256(tokenizer.chat_template.encode()).hexdigest())
    extractor = FeatureExtractor(protocol, [layer])
    (output / 'corpus.jsonl').write_bytes(Path(corpus).read_bytes())
    write_json(output / 'provenance.json', review)
    with (output / 'vectors.jsonl').open('w') as stream:
        for index, record in enumerate(records, 1):
            features = extractor.extract(record.text)
            for pool in ('last', 'mean'):
                vector = features[pool][str(layer)]
                require(len(vector) == config.hidden_size and all(math.isfinite(x) for x in vector),
                        'Invalid feature vector: ' + record.id)
            row = {'id': record.id, 'text_sha256': hashlib.sha256(record.text.encode()).hexdigest(),
                   'features': features}
            stream.write(json.dumps(row, allow_nan=False) + '\n')
            stream.flush()
            print(f'Collected {index}/{len(records)}: {record.id}', flush=True)
    payload = {'status': 'completed', 'kind': 'v2-feature-collection',
               'scope': review['scope'], 'feature_protocol': protocol.as_dict(),
               'protocol_fingerprint': protocol.fingerprint, 'layer': layer,
               'dim': config.hidden_size, 'manifest': manifest,
               'files_sha256': {name: digest(output / name) for name in ('corpus.jsonl', 'provenance.json', 'vectors.jsonl')},
               'source_sha256': source_hashes(),
               'runtime': {'python': platform.python_version(), 'torch': torch.__version__,
                           'cuda': torch.version.cuda, 'gpu': torch.cuda.get_device_name(0),
                           'model_dtype': str(extractor.model.dtype),
                           'transformers': version('transformers')},
               'training_performed': False}
    write_json(output / 'collection.json', payload)
    return payload


def load_collection(folder):
    folder = Path(folder)
    meta = json.loads((folder / 'collection.json').read_text())
    require(meta['status'] == 'completed' and meta['kind'] == 'v2-feature-collection', 'Incomplete collection')
    require(meta['scope'] == 'development-only', 'Unexpected evidence scope')
    require(set(meta['files_sha256']) == {'corpus.jsonl', 'provenance.json', 'vectors.jsonl'}, 'Incomplete collection inventory')
    for name, expected in meta['files_sha256'].items():
        require(digest(folder / name) == expected, 'Collection checksum mismatch: ' + name)
    records, manifest, review = read_corpus(folder / 'corpus.jsonl', folder / 'provenance.json')
    require(manifest == meta['manifest'] and review['scope'] == meta['scope'], 'Corpus manifest differs')
    protocol = FeatureProtocol(**meta['feature_protocol'])
    require(protocol.fingerprint == meta['protocol_fingerprint'], 'Feature protocol fingerprint differs')
    require(protocol.model_id == MODEL and protocol.model_revision == protocol.tokenizer_revision == REVISION,
            'Unexpected model revision')
    require(protocol.execution_device == 'cuda' and protocol.dtype == 'float16', 'Unexpected feature precision/device')
    require(type(meta['layer']) is int and meta['layer'] >= 0 and type(meta['dim']) is int and meta['dim'] > 0,
            'Invalid layer or vector dimension')
    rows = [json.loads(line) for line in (folder / 'vectors.jsonl').read_text().splitlines() if line.strip()]
    require(len(rows) == len(records), 'Feature row count differs')
    for row, record in zip(rows, records):
        require(row['id'] == record.id and row['text_sha256'] == hashlib.sha256(record.text.encode()).hexdigest(),
                'Feature identity differs from corpus')
        require(type(row['features']['token_count']) is int and 0 < row['features']['token_count'] <= protocol.max_length,
                'Invalid selected token count')
        for pool in ('last', 'mean'):
            require(set(row['features'][pool]) == {str(meta['layer'])}, 'Feature layer differs')
            vector = row['features'][pool][str(meta['layer'])]
            require(len(vector) == meta['dim'] and all(type(x) in (float, int) and math.isfinite(x) for x in vector),
                    'Invalid vector dimensions or values')
    return meta, records, rows


def fit(collection, output, *, steps=400, l2=0.05, lr=0.3, max_fpr=0.01):
    require(type(steps) is int and steps > 0 and math.isfinite(l2) and l2 >= 0
            and math.isfinite(lr) and lr > 0 and math.isfinite(max_fpr) and 0 <= max_fpr < 1,
            'Invalid fitting hyperparameters')
    meta, records, rows = load_collection(collection)
    output = fresh(output)
    models = {}
    for pool, filename in (('last', 'linear.json'), ('mean', 'activation.json')):
        matrix = lambda split: ([row['features'][pool][str(meta['layer'])]
                                 for record, row in zip(records, rows) if record.split == split],
                                [record.label for record in records if record.split == split])
        train_x, train_y = matrix('train')
        calibration_x, calibration_y = matrix('calibration')
        scaled, mean, std = standardize(train_x)
        weights, bias = train_logistic(scaled, train_y, steps=steps, l2=l2, lr=lr)
        require(all(math.isfinite(x) for x in weights + mean + std + [bias]), 'Nonfinite fitted parameters')
        calibration_scaled, _, _ = standardize(calibration_x, mean, std)
        scores = [predict_proba(row, weights, bias) for row in calibration_scaled]
        calibration = calibrate(scores, calibration_y, max_fpr=max_fpr)
        model = {'format': 2, 'kind': 'linear' if pool == 'last' else 'activation',
                 'scope': meta['scope'], 'feature_protocol': meta['feature_protocol'],
                 'protocol_fingerprint': meta['protocol_fingerprint'], 'layer': meta['layer'],
                 'pooling': pool, 'dim': meta['dim'], 'weights': weights, 'bias': bias,
                 'mean': mean, 'std': std, 'threshold': calibration['threshold'],
                 'calibration': calibration, 'manifest_sha256': meta['manifest']['manifest_sha256'],
                 'collection_sha256': digest(Path(collection) / 'collection.json'),
                 'fit_config': {'steps': steps, 'l2': l2, 'lr': lr},
                 'training_ids': [record.id for record in records if record.split == 'train'],
                 'calibration_ids': [record.id for record in records if record.split == 'calibration'],
                 'layer_selection': 'fixed before collection; no sweep',
                 'test_used_for_fitting_or_threshold': False}
        write_json(output / filename, model)
        models[filename] = digest(output / filename)
    payload = {'status': 'completed', 'kind': 'v2-probe-fit', 'scope': meta['scope'],
               'models_sha256': models, 'collection_sha256': digest(Path(collection) / 'collection.json'),
               'source_sha256': source_hashes(), 'test_used_for_fitting_or_threshold': False,
               'independent_accuracy_claim': False}
    write_json(output / 'fit.json', payload)
    return payload


def evaluate(collection, models, output):
    meta, records, rows = load_collection(collection)
    models = Path(models)
    fitted = json.loads((models / 'fit.json').read_text())
    require(fitted['status'] == 'completed' and fitted['kind'] == 'v2-probe-fit', 'Incomplete fitted artifact')
    require(fitted['scope'] == meta['scope'] and fitted['test_used_for_fitting_or_threshold'] is False,
            'Unexpected fit policy')
    require(set(fitted['models_sha256']) == {'linear.json', 'activation.json'}, 'Missing probe artifact')
    require(fitted['collection_sha256'] == digest(Path(collection) / 'collection.json'), 'Fit uses a different collection')
    output = fresh(output)
    test = [(record, row) for record, row in zip(records, rows) if record.split == 'test']
    metrics, predictions = {}, []
    for name, expected in fitted['models_sha256'].items():
        path = models / name
        require(digest(path) == expected, 'Fitted model checksum differs: ' + name)
        model = json.loads(path.read_text())
        require(model['manifest_sha256'] == meta['manifest']['manifest_sha256']
                and model['collection_sha256'] == fitted['collection_sha256'], 'Model corpus differs')
        require(model['test_used_for_fitting_or_threshold'] is False
                and model['threshold'] == model['calibration']['threshold'], 'Frozen threshold differs')
        require(model['layer'] == meta['layer'], 'Model layer differs')
        by_text = {record.text: row['features'] for record, row in test}
        class SavedExtractor:
            protocol = FeatureProtocol(**meta['feature_protocol'])
            layers = (meta['layer'],)
            def extract(self, text):
                return by_text[text]
        probe = ProtocolProbe(model, SavedExtractor())
        scores = [probe.score(record.text) for record, _ in test]
        labels = [record.label for record, _ in test]
        metrics[name] = evaluate_frozen(scores, labels, model['calibration'])
        for (record, _), score in zip(test, scores):
            predictions.append({'probe': name, 'id': record.id, 'label': record.label,
                                'score': score, 'predicted': int(score >= probe.threshold)})
    write_json(output / 'predictions.json', predictions)
    payload = {'status': 'completed', 'kind': 'v2-frozen-test-evaluation',
               'scope': meta['scope'], 'metrics': metrics,
               'collection_sha256': fitted['collection_sha256'], 'fit_sha256': digest(models / 'fit.json'),
               'source_sha256': source_hashes(), 'manifest': meta['manifest'],
               'test_used_for_fitting_or_threshold': False, 'independent_accuracy_claim': False,
               'note': 'Development corpus only. Held-out split metrics are diagnostic; no population 1%-FPR or independent benchmark claim.'}
    write_json(output / 'evaluation.json', payload)
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    collect_parser = sub.add_parser('collect')
    collect_parser.add_argument('corpus', type=Path)
    collect_parser.add_argument('--provenance', type=Path, required=True)
    collect_parser.add_argument('--layer', type=int, default=18)
    for name in ('fit', 'evaluate'):
        cmd = sub.add_parser(name)
        cmd.add_argument('collection', type=Path)
        if name == 'evaluate':
            cmd.add_argument('--models', type=Path, required=True)
    for cmd in (collect_parser, sub.choices['fit'], sub.choices['evaluate']):
        cmd.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'collect':
        result = collect(args.corpus, args.provenance, args.output, layer=args.layer)
    elif args.command == 'fit':
        result = fit(args.collection, args.output)
    else:
        result = evaluate(args.collection, args.models, args.output)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
