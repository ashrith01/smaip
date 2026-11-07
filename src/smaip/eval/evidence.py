"""Reaggregate bound local artifacts; hashes establish consistency, not attestation."""
import hashlib
import json
import math
from pathlib import Path

from smaip.eval.open_agent_dev import DevelopmentCase, score_case
from smaip.eval.contract import evaluation_matrix
from smaip.probes.low_fpr import operating_point
from smaip.probes.pipeline_v2 import load_collection
from smaip.probes.protocol import FeatureProtocol, ProtocolProbe


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ArtifactReader:
    def __init__(self, root, artifacts):
        self.root = Path(root).resolve()
        self.artifacts = artifacts

    def path(self, name):
        item = self.artifacts[name]
        relative = Path(item['path'])
        path = (self.root / relative).resolve()
        if relative.is_absolute() or '..' in relative.parts or not path.is_relative_to(self.root):
            raise ValueError('artifact path escapes evidence root')
        if not path.is_file() or file_hash(path) != item['sha256']:
            raise ValueError('artifact checksum mismatch: ' + name)
        return path

    def read(self, name):
        return json.loads(self.path(name).read_text())


def bound_evidence(report, root):
    """Verify existing format-2 probe and canonical numeric agent evidence.

    Unknown scorer/protocol versions fail closed. Extending native benchmark
    scoring requires a separately versioned adapter, not a caller success flag.
    """
    bundle = report['evidence_bundle']
    reader = ArtifactReader(root, bundle['artifacts'])
    for name in reader.artifacts:
        reader.path(name)
    agent = bundle['agents']
    manifest = reader.read(agent['cases'])
    if manifest.get('scoring') != 'canonical-numeric-v1':
        raise ValueError('unsupported task scorer')
    cases = {case['id']: DevelopmentCase(**case) for case in manifest['cases']}
    if len(cases) != len(manifest['cases']):
        raise ValueError('duplicate task cases')
    runs, rows, seen, identities = {}, {}, set(), set()
    configs = {config.name: config.as_dict() for config in evaluation_matrix(backend=report['backend'], model_id=report['model_id'])}
    for item in agent['runs']:
        key = (item['variant'], item['case'])
        if key in seen:
            raise ValueError('duplicate agent run')
        seen.add(key)
        run = reader.read(item['artifact'])
        if run.get('agent_protocol_version') not in (4, 5):
            raise ValueError('unknown agent protocol')
        if run['backend'] not in ('hf-local', 'vllm-local') or run['backend'] != report['backend']:
            raise ValueError('agent backend differs')
        if run['config']['model_id'] != report['model_id'] or run['config']['name'] != item['variant']:
            raise ValueError('agent model/configuration differs')
        expected = configs[item['variant']]
        if any(run['config'].get(key) != expected[key] for key in ('topology', 'keyword', 'detector', 'gateway', 'backend', 'schema_version')):
            raise ValueError('agent ablation factors differ')
        if not run.get('source_sha256') or not run.get('generation_config', {}).get('revision'):
            raise ValueError('agent source/model revision absent')
        if run['run_id'] in identities:
            raise ValueError('duplicate agent run identity')
        identities.add(run['run_id'])
        identity = (run['backend'], run['generation_config']['model_id'], run['generation_config']['revision'],
                    run['config']['max_steps'], run['config']['max_new_tokens'],
                    run['response_format']['schema_sha256'], json.dumps(run['source_sha256'], sort_keys=True),
                    run['agent_protocol_version'], run.get('runtime_policy'))
        if run['generation_config']['model_id'] != report['model_id']:
            raise ValueError('generation model differs from evaluation model')
        runs.setdefault(item['variant'], []).append((cases[item['case']], score_case(run, cases[item['case']]), identity))
    for variant, results in runs.items():
        if {case.id for case, _, _ in results} != set(cases):
            raise ValueError('agent case sets differ')
        clean = [score for case, score, _ in results if case.condition == 'clean']
        attacks = [score for case, score, _ in results if case.condition == 'injected']
        if not clean or not attacks:
            raise ValueError('agent evidence lacks clean or attack cases')
        # A clean-task false alarm is quarantine, not every task-quality failure.
        quarantine = 0
        for item in agent['runs']:
            if item['variant'] == variant and cases[item['case']].condition == 'clean':
                quarantine += any(e.get('quarantined') for e in reader.read(item['artifact'])['events'])
        rows[variant] = {'name': variant, 'utility': sum(s['task_success'] for s in clean) / len(clean),
                         'asr': sum(s['attack_objective_observed'] for s in attacks) / len(attacks),
                         'fpr': quarantine / len(clean), 'clean_count': len(clean), 'attack_count': len(attacks)}
    if len({identity for results in runs.values() for _, _, identity in results}) != 1:
        raise ValueError('agent arms use different model/source/budgets')
    for supplied in report['rows']:
        actual = rows[supplied['name']]
        if any(supplied[key] != actual[key] for key in ('utility', 'asr', 'fpr')):
            raise ValueError('agent aggregate differs from task effects')

    probe = bundle['probe']
    collection_path = reader.path(probe['collection'])
    # Collection sidecars are fixed-name files; bind them all to the bundle.
    meta = reader.read(probe['collection'])
    for filename, expected in meta['files_sha256'].items():
        path = collection_path.parent / filename
        if path.resolve().parent != collection_path.parent.resolve() or file_hash(path) != expected:
            raise ValueError('probe collection sidecar differs')
        if path.resolve() not in {reader.path(name).resolve() for name in reader.artifacts}:
            raise ValueError('unbound probe collection sidecar')
    meta, records, vectors = load_collection(collection_path.parent)
    if meta['feature_protocol']['model_id'] != report['model_id'] or any(
            identity[2] != meta['feature_protocol']['model_revision'] for results in runs.values() for _, _, identity in results):
        raise ValueError('probe and agent backbone/revision differ')
    model = reader.read(probe['model'])
    if model['collection_sha256'] != file_hash(collection_path):
        raise ValueError('probe model uses a different collection')
    if model['threshold'] != model['calibration']['threshold'] or model['test_used_for_fitting_or_threshold'] is not False:
        raise ValueError('probe threshold was not frozen')
    if model['training_ids'] != [r.id for r in records if r.split == 'train'] or model['calibration_ids'] != [r.id for r in records if r.split == 'calibration']:
        raise ValueError('probe split identities differ')
    selected = [(record, vector) for record, vector in zip(records, vectors) if record.split == 'test']
    features = {record.text: vector['features'] for record, vector in selected}
    class SavedExtractor:
        protocol = FeatureProtocol(**meta['feature_protocol'])
        layers = (meta['layer'],)
        def extract(self, text):
            return features[text]
    fitted = ProtocolProbe(model, SavedExtractor())
    scores = [fitted.score(record.text) for record, _ in selected]
    block = operating_point(scores, [record.label for record, _ in selected], fitted.threshold)
    actual_probe = {'test_auroc': block['auroc'], 'test_tpr': block['tpr'], 'test_fpr': block['fpr'],
                    'test_positives': block['positives'], 'test_negatives': block['negatives'],
                    'test_fp': block['fp'], 'test_tp': block['tp'],
                    'calibration_negatives': sum(r.split == 'calibration' and r.label == 0 for r in records)}
    if any(report['probe'].get(key) != value for key, value in actual_probe.items()):
        raise ValueError('probe aggregate differs from bound vectors/model')
    return {'agent_rows': list(rows.values()), 'probe': actual_probe,
            'corpus_scope': meta['scope'], 'artifact_count': len(reader.artifacts),
            'provenance_scope': 'local artifact consistency; not independent execution or label attestation'}


def binomial_upper(fp, n, confidence=.95):
    if type(fp) is not int or type(n) is not int or not 0 <= fp <= n or n < 1 or type(confidence) not in (int, float) or not 0 < confidence < 1:
        raise ValueError('invalid binomial counts')
    if fp == n:
        return 1.
    if fp == 0:
        return 1 - (1 - confidence) ** (1 / n)
    def cdf(p):
        logs = [math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
                + k * math.log(p) + (n - k) * math.log1p(-p) for k in range(fp + 1)]
        maximum = max(logs)
        return math.exp(maximum) * sum(math.exp(x - maximum) for x in logs)
    lo, hi = 0., 1.
    for _ in range(70):
        mid = (lo + hi) / 2
        if cdf(mid) > 1 - confidence:
            lo = mid
        else:
            hi = mid
    return hi
