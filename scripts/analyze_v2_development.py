"""Audit the first returned V2 development training run without Qwen loads."""
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import tarfile
import tempfile

from smaip.probes import pipeline_v2 as pipeline
from smaip.probes.logistic import predict_proba, standardize, train_logistic
from smaip.probes.low_fpr import calibrate, evaluate_frozen


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    archive = Path('reports/probe-development-01.tar.gz')
    source = Path('reports/smaip-v2-training-dev-r1.tar.gz')
    destination = Path('reports/runs/probe-development-01')
    with tarfile.open(source) as tar:
        item = next(m for m in tar.getmembers() if m.name.endswith('/bundle-manifest.json'))
        manifest_bytes = tar.extractfile(item).read()
        manifest = json.loads(manifest_bytes)
        for name, expected in manifest['files'].items():
            if not (sha(tar.extractfile(manifest['prefix'] + '/' + name).read()) == expected):
                raise ValueError(name)
    sources = {name.removeprefix('src/smaip/'): expected for name, expected in manifest['files'].items()
               if name.startswith('src/smaip/') and name.endswith('.py')}
    # Numerical reference functions must match the actual run's frozen source.
    for name in ('probes/pipeline_v2.py', 'probes/logistic.py', 'probes/low_fpr.py',
                 'probes/protocol.py', 'probes/manifest.py'):
        if not (pipeline.digest(Path('src/smaip') / name) == sources[name]):
            raise ValueError(name)
    allowed = {'probes/fit.json', 'probes/linear.json', 'probes/activation.json',
               'evaluation/evaluation.json', 'evaluation/predictions.json',
               'collection/collection.json', 'collection/corpus.jsonl',
               'collection/provenance.json', 'collection/vectors.jsonl',
               'status.json', 'files-sha256.json', 'bundle-validation.json',
               'collect.log', 'fit.log', 'evaluate.log', 'gpu.txt', 'packages.txt'}
    prefix = 'reports/v2/probe-development-01/'
    raw = {}
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            if member.isdir():
                continue
            if not (member.isfile() and member.name.startswith(prefix) and (member.size < 10000000)):
                raise ValueError('Evidence check failed at analyze_v2_development.py:46')
            name = member.name.removeprefix(prefix)
            if not (name in allowed and name not in raw and ('..' not in PurePosixPath(name).parts)):
                raise ValueError(name)
            raw[name] = tar.extractfile(member).read()
    if not (set(raw) == allowed):
        raise ValueError('Evidence check failed at analyze_v2_development.py:50')
    read = lambda name: json.loads(raw[name])
    inventory = read('files-sha256.json')
    if not (set(inventory) == allowed - {'files-sha256.json'}):
        raise ValueError('Evidence check failed at analyze_v2_development.py:53')
    for name, expected in inventory.items():
        if not (sha(raw[name]) == expected):
            raise ValueError(name)
    if not (read('status.json') == {'exit_code': 0, 'status': 'completed', 'scope': 'development-only', 'fit_completed': True, 'evaluation_completed': True}):
        raise ValueError('Evidence check failed at analyze_v2_development.py:56')
    if not (read('bundle-validation.json') == {'base_commit': manifest['base_commit'], 'source_state': manifest['source_state'], 'manifest_sha256': sha(manifest_bytes), 'files_verified': len(manifest['files'])}):
        raise ValueError('Evidence check failed at analyze_v2_development.py:58')
    meta, fitted, evaluation = map(read, ('collection/collection.json', 'probes/fit.json', 'evaluation/evaluation.json'))
    for item in (meta, fitted, evaluation):
        if not (item['source_sha256'] == sources):
            raise ValueError('Evidence check failed at analyze_v2_development.py:63')
    if not (meta['layer'] == 18 and meta['dim'] == 2048):
        raise ValueError('Evidence check failed at analyze_v2_development.py:64')
    if not (meta['protocol_fingerprint'] == 'e84129151cabbe6ba45e017c52310146af4c3606433d6fb30a34465bfc35ebe0'):
        raise ValueError('Evidence check failed at analyze_v2_development.py:65')
    if not (raw['collection/corpus.jsonl'] == Path('data/v2/development-01.jsonl').read_bytes()):
        raise ValueError('Evidence check failed at analyze_v2_development.py:66')
    if not (raw['collection/provenance.json'] == Path('data/v2/development-01.provenance.json').read_bytes()):
        raise ValueError('Evidence check failed at analyze_v2_development.py:67')
    diagnostics = {}
    with tempfile.TemporaryDirectory(prefix='smaip-v2-evidence-audit-') as directory:
        root = Path(directory)
        for name, content in raw.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        checked_meta, records, rows = pipeline.load_collection(root / 'collection')
        if not (checked_meta == meta):
            raise ValueError('Evidence check failed at analyze_v2_development.py:76')
        replay = pipeline.evaluate(root / 'collection', root / 'probes', root / 'replay')
        # New unrelated modules can change the current tree inventory. The
        # reference numerical modules above must still match the frozen bundle.
        if not ({k: v for k, v in replay.items() if k != 'source_sha256'} == {k: v for k, v in evaluation.items() if k != 'source_sha256'}):
            raise ValueError('Evidence check failed at analyze_v2_development.py:80')
        if not ((root / 'replay/predictions.json').read_bytes() == raw['evaluation/predictions.json']):
            raise ValueError('Evidence check failed at analyze_v2_development.py:82')
        for filename, pool in (('linear.json', 'last'), ('activation.json', 'mean')):
            model = read('probes/' + filename)
            if not (model['format'] == 2 and model['fit_config'] == {'steps': 400, 'l2': 0.05, 'lr': 0.3}):
                raise ValueError('Evidence check failed at analyze_v2_development.py:85')
            if not (model['pooling'] == pool and model['layer'] == 18):
                raise ValueError('Evidence check failed at analyze_v2_development.py:86')
            if not (model['training_ids'] == [r.id for r in records if r.split == 'train']):
                raise ValueError('Evidence check failed at analyze_v2_development.py:87')
            if not (model['calibration_ids'] == [r.id for r in records if r.split == 'calibration']):
                raise ValueError('Evidence check failed at analyze_v2_development.py:88')
            train = [(r, v) for r, v in zip(records, rows) if r.split == 'train']
            train_x = [v['features'][pool]['18'] for _, v in train]
            train_y = [r.label for r, _ in train]
            scaled, mean, std = standardize(train_x)
            weights, bias = train_logistic(scaled, train_y, **model['fit_config'])
            errors = {}
            for key, expected in (('weights', weights), ('mean', mean), ('std', std), ('bias', [bias])):
                actual = [model[key]] if key == 'bias' else model[key]
                if not (len(actual) == len(expected)):
                    raise ValueError('Evidence check failed at analyze_v2_development.py:97')
                if not (all((math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10) for a, b in zip(actual, expected)))):
                    raise ValueError(key)
                errors[key] = max(abs(a - b) for a, b in zip(actual, expected))
            calibration_rows = [(r, v) for r, v in zip(records, rows) if r.split == 'calibration']
            x, _, _ = standardize([v['features'][pool]['18'] for _, v in calibration_rows], model['mean'], model['std'])
            scores = [predict_proba(vector, model['weights'], model['bias']) for vector in x]
            labels = [r.label for r, _ in calibration_rows]
            calibration = calibrate(scores, labels, max_fpr=0.01)
            if not (calibration == model['calibration'] and calibration['threshold'] == model['threshold']):
                raise ValueError('Evidence check failed at analyze_v2_development.py:105')
            highest_benign = max(((score, record.id) for score, (record, _) in zip(scores, calibration_rows)
                                  if not record.label))
            diagnostics[filename] = {'calibration': calibration, 'test': evaluation['metrics'][filename],
                                     'highest_benign_calibration': {'score': highest_benign[0], 'id': highest_benign[1]},
                                     'recomputed_fit_max_absolute_errors': errors}
    result = {'archive_sha256': sha(archive.read_bytes()), 'source_bundle_sha256': sha(source.read_bytes()),
              'verified_bundle_files': len(manifest['files']), 'verified_python_sources': len(sources),
              'documents': meta['manifest']['records'], 'vectors': len(rows) * 2,
              'finite_scalar_values': len(rows) * 2 * meta['dim'],
              'protocol_fingerprint': meta['protocol_fingerprint'], 'diagnostics': diagnostics,
              'recomputed_fits_match': True, 'recomputed_calibration_matches': True,
              'recomputed_test_predictions_and_metrics_match': True,
              'members_sha256': {name: sha(content) for name, content in raw.items()},
              'assessment': 'First real V2 development probes verified. Linear threshold catches no test attacks; mean pooling has one false positive and two misses. Independent low-FPR acceptance remains pending.'}
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in raw.items():
        path = destination / name
        if path.exists():
            if not (path.read_bytes() == content):
                raise ValueError('Existing evidence differs: ' + name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    pipeline.write_json(destination / 'validation.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'members_sha256'}, indent=2))


if __name__ == '__main__':
    main()
