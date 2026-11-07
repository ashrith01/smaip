"""Audit external frozen-probe evidence from saved vectors; load no Qwen model."""
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import statistics
import tarfile
import tempfile

from smaip.probes import external_v2 as external
from smaip.probes.low_fpr import operating_point
from smaip.probes.pipeline_v2 import write_json
from smaip.probes.protocol import FeatureProtocol, ProtocolProbe


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    archive = Path('reports/external-frozen-01.tar.gz')
    bundle_path = Path('reports/smaip-v2-external-eval-r1.tar.gz')
    results = Path('.local-data/external-frozen-01/results')
    report_dir = Path('reports/runs/external-frozen-01')
    with tarfile.open(bundle_path) as tar:
        item = next(m for m in tar.getmembers() if m.name.endswith('/bundle-manifest.json'))
        manifest_bytes = tar.extractfile(item).read()
        manifest = json.loads(manifest_bytes)
        for name, expected in manifest['files'].items():
            if not (sha(tar.extractfile(manifest['prefix'] + '/' + name).read()) == expected):
                raise ValueError(name)
        expected_corpus = {name: tar.extractfile(manifest['prefix'] + '/external-data/prepared/' + name).read()
                           for name in ('corpus.jsonl', 'policy.json', 'UPSTREAM_README.md', 'ATTRIBUTION.txt')}
    sources = {name.removeprefix('src/smaip/'): expected for name, expected in manifest['files'].items()
               if name.startswith('src/smaip/') and name.endswith('.py')}
    for name in ('probes/external_v2.py', 'probes/protocol.py', 'probes/logistic.py', 'probes/low_fpr.py'):
        if not (external.digest(Path('src/smaip') / name) == sources[name]):
            raise ValueError(name)
    allowed = {'evaluate.log', 'evaluation/evaluation.json', 'evaluation/predictions.json',
               'evaluation/vectors.jsonl', 'gpu.txt', 'status.json', 'frozen-probes/fit.json',
               'frozen-probes/linear.json', 'frozen-probes/activation.json', 'files-sha256.json',
               'corpus/ATTRIBUTION.txt', 'corpus/UPSTREAM_README.md', 'corpus/corpus.jsonl',
               'corpus/policy.json', 'bundle-validation.json', 'packages.txt'}
    prefix = 'reports/v2/external-frozen-01/'
    raw = {}
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            if member.isdir():
                continue
            if not (member.isfile() and member.name.startswith(prefix) and (member.size < 80000000)):
                raise ValueError('Evidence check failed at analyze_external_v2.py:48')
            name = member.name.removeprefix(prefix)
            if not (name in allowed and name not in raw and ('..' not in PurePosixPath(name).parts)):
                raise ValueError(name)
            raw[name] = tar.extractfile(member).read()
    if not (set(raw) == allowed):
        raise ValueError('Evidence check failed at analyze_external_v2.py:52')
    read = lambda name: json.loads(raw[name])
    inventory = read('files-sha256.json')
    if not (set(inventory) == allowed - {'files-sha256.json'}):
        raise ValueError('Evidence check failed at analyze_external_v2.py:55')
    for name, expected in inventory.items():
        if not (sha(raw[name]) == expected):
            raise ValueError(name)
    if not (read('status.json') == {'exit_code': 0, 'status': 'completed', 'scope': 'external-pilot', 'training_performed': False, 'evaluation_completed': True}):
        raise ValueError('Evidence check failed at analyze_external_v2.py:58')
    if not (read('bundle-validation.json') == {'base_commit': manifest['base_commit'], 'source_state': manifest['source_state'], 'manifest_sha256': sha(manifest_bytes), 'files_verified': len(manifest['files'])}):
        raise ValueError('Evidence check failed at analyze_external_v2.py:60')
    for name, value in expected_corpus.items():
        if not (raw['corpus/' + name] == value):
            raise ValueError(name)
    evaluation = read('evaluation/evaluation.json')
    if not (evaluation['status'] == 'completed' and evaluation['scope'] == 'external-pilot'):
        raise ValueError('Evidence check failed at analyze_external_v2.py:66')
    if not (evaluation['source_sha256'] == sources):
        raise ValueError('Evidence check failed at analyze_external_v2.py:67')
    if not (evaluation['training_performed'] is evaluation['thresholds_changed'] is False):
        raise ValueError('Evidence check failed at analyze_external_v2.py:68')
    if not (evaluation['agent_attack_success_measured'] is evaluation['population_independence_verified'] is False):
        raise ValueError('Evidence check failed at analyze_external_v2.py:69')
    if not (evaluation['frozen_models_sha256'] == external.MODEL_HASHES):
        raise ValueError('Evidence check failed at analyze_external_v2.py:70')
    if not (evaluation['policy_sha256'] == sha(raw['corpus/policy.json'])):
        raise ValueError('Evidence check failed at analyze_external_v2.py:71')
    if not (evaluation['documents'] == 800 and evaluation['pairs'] == 400):
        raise ValueError('Evidence check failed at analyze_external_v2.py:72')
    if not (evaluation['token_budget_excluded_pairs'] == []):
        raise ValueError('Evidence check failed at analyze_external_v2.py:73')
    protocol = FeatureProtocol(**evaluation['feature_protocol'])
    if not (protocol.fingerprint == evaluation['protocol_fingerprint']):
        raise ValueError('Evidence check failed at analyze_external_v2.py:75')
    if not (evaluation['layer'] == 18 and evaluation['dim'] == 2048):
        raise ValueError('Evidence check failed at analyze_external_v2.py:76')
    results.mkdir(parents=True, exist_ok=True)
    for name, value in raw.items():
        path = results / name
        if path.exists():
            if not (path.read_bytes() == value):
                raise ValueError('Existing evidence differs: ' + name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
    policy, documents = external.load_prepared(results / 'corpus')
    with tempfile.TemporaryDirectory(prefix='smaip-external-preparation-replay-') as directory:
        replay = Path(directory) / 'prepared'
        source = Path('.local-data/external-frozen-01/source')
        external.prepare(source / 'train.jsonl', source / 'README.md', results / 'frozen-probes',
                         Path('data/v2/development-01.jsonl'), replay)
        for name, expected in expected_corpus.items():
            if not ((replay / name).read_bytes() == expected):
                raise ValueError(name)
    rows = [json.loads(line) for line in raw['evaluation/vectors.jsonl'].splitlines() if line.strip()]
    if not (len(rows) == len(documents) == 800):
        raise ValueError('Evidence check failed at analyze_external_v2.py:94')
    for row, document in zip(rows, documents):
        if not (row['id'] == document['id'] and row['text_sha256'] == document['text_sha256']):
            raise ValueError('Evidence check failed at analyze_external_v2.py:96')
        features = row['features']
        if not (type(features['token_count']) is int and 0 < features['token_count'] <= protocol.max_length):
            raise ValueError('Evidence check failed at analyze_external_v2.py:98')
        if not (len(features['rendered_sha256']) == 64):
            raise ValueError('Evidence check failed at analyze_external_v2.py:99')
        for pool in ('last', 'mean'):
            if not (set(features[pool]) == {'18'}):
                raise ValueError('Evidence check failed at analyze_external_v2.py:101')
            vector = features[pool]['18']
            if not (len(vector) == 2048 and all((type(x) in (int, float) and math.isfinite(x) for x in vector))):
                raise ValueError('Evidence check failed at analyze_external_v2.py:103')
    by_text = {document['text']: row['features'] for document, row in zip(documents, rows)}
    class SavedExtractor:
        layers = (18,)
        def extract(self, text):
            return by_text[text]
    extractor = SavedExtractor()
    extractor.protocol = protocol
    recorded = read('evaluation/predictions.json')
    if not (len(recorded) == len(documents) * 2):
        raise ValueError('Evidence check failed at analyze_external_v2.py:112')
    expected_predictions, probes, metrics, score_ranges, breakdowns = [], {}, {}, {}, {}
    for name, expected in external.MODEL_HASHES.items():
        if not (sha(raw['frozen-probes/' + name]) == expected):
            raise ValueError('Evidence check failed at analyze_external_v2.py:115')
        probes[name] = ProtocolProbe(read('frozen-probes/' + name), extractor)
    for document in documents:
        for name, probe in probes.items():
            score = probe.score(document['text'])
            expected_predictions.append({'probe': name, 'id': document['id'], 'pair_id': document['pair_id'],
                                         'domain': document['domain'], 'attack_category': document['attack_category'],
                                         'label': document['label'], 'score': score, 'threshold': probe.threshold,
                                         'predicted': int(score >= probe.threshold)})
    score_errors = []
    for expected, actual in zip(expected_predictions, recorded):
        if not ({k: v for k, v in expected.items() if k != 'score'} == {k: v for k, v in actual.items() if k != 'score'}):
            raise ValueError('Evidence check failed at analyze_external_v2.py:126')
        if not (math.isclose(expected['score'], actual['score'], rel_tol=1e-12, abs_tol=1e-15)):
            raise ValueError('Evidence check failed at analyze_external_v2.py:128')
        score_errors.append(abs(expected['score'] - actual['score']))
    for name, probe in probes.items():
        selected = [row for row in expected_predictions if row['probe'] == name]
        block = operating_point([r['score'] for r in selected], [r['label'] for r in selected], probe.threshold)
        block['zero_fp_one_sided_95_upper_if_independent'] = 1 - 0.05 ** (1 / block['negatives']) if block['fp'] == 0 else None
        block['population_fpr_claim_supported'] = False
        if not (block == evaluation['metrics'][name]):
            raise ValueError('Evidence check failed at analyze_external_v2.py:135')
        metrics[name] = block
        score_ranges[name] = {}
        for label in (0, 1):
            values = [row['score'] for row in selected if row['label'] == label]
            score_ranges[name][str(label)] = {'min': min(values), 'median': statistics.median(values), 'max': max(values)}
        breakdowns[name] = {domain: operating_point([r['score'] for r in selected if r['domain'] == domain],
                                                    [r['label'] for r in selected if r['domain'] == domain], probe.threshold)
                            for domain in sorted({row['domain'] for row in selected})}
    result = {'archive_sha256': sha(archive.read_bytes()), 'source_bundle_sha256': sha(bundle_path.read_bytes()),
              'verified_bundle_files': len(manifest['files']), 'verified_python_sources': len(sources),
              'verified_pairs': len(documents) // 2, 'verified_documents': len(documents),
              'verified_predictions': len(recorded), 'verified_vectors': len(rows) * 2,
              'finite_scalar_values': len(rows) * 2 * 2048,
              'preparation_replay_byte_identical': True, 'frozen_models_verified': True,
              'recomputed_classifications_and_metrics_exact': True,
              'recomputed_score_max_absolute_error': max(score_errors),
              'recomputed_score_nonzero_rounding_differences': sum(error > 0 for error in score_errors),
              'metrics': metrics,
              'score_ranges_by_label': score_ranges, 'by_domain': breakdowns,
              'flagged_documents': [row for row in recorded if row['predicted']],
              'raw_evidence_directory': str(results),
              'members_sha256': {name: sha(value) for name, value in raw.items()},
              'assessment': 'External transfer at the frozen operating points failed: linear catches 0/400 attacks, mean pooling 1/400 with 1/400 clean controls flagged. No population low-FPR or agent-ASR claim.'}
    report_dir.mkdir(parents=True, exist_ok=True)
    write_json(report_dir / 'validation.json', result)
    for name in ('evaluation/evaluation.json', 'evaluation/predictions.json', 'status.json', 'bundle-validation.json'):
        path = report_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if not (path.read_bytes() == raw[name]):
                raise ValueError('Existing evidence differs: ' + name)
        else:
            path.write_bytes(raw[name])
    print(json.dumps({k: v for k, v in result.items() if k not in {'members_sha256', 'by_domain'}}, indent=2))


if __name__ == '__main__':
    main()
