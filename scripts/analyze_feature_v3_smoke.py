#!/usr/bin/env python3
"""Audit a returned feature-v3 smoke archive against its exact source bundle."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import tarfile


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def fail(message):
    raise ValueError(message)


def members(archive):
    with tarfile.open(archive, 'r:gz') as tar:
        regular = {}
        for item in tar.getmembers():
            path = Path(item.name)
            if path.is_absolute() or '..' in path.parts or item.issym() or item.islnk():
                fail('unsafe archive member')
            if item.isfile():
                if item.name in regular:
                    fail('duplicate archive member')
                regular[item.name] = tar.extractfile(item).read()
            elif not item.isdir():
                fail('unsupported archive member')
        return regular


def check_vector(values, dim, context):
    if len(values) != dim or any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
        fail('invalid vector: ' + context)


def analyze(source_archive, result_archive):
    source = members(source_archive)
    result = members(result_archive)
    source_roots = {Path(name).parts[0] for name in source}
    result_roots = {Path(name).parts[0] for name in result}
    if len(source_roots) != 1 or len(result_roots) != 1:
        fail('expected one root in each archive')
    source_root, result_root = source_roots.pop(), result_roots.pop()
    def get(files, root, name):
        try:
            return files[f'{root}/{name}']
        except KeyError:
            fail('missing archive member: ' + name)
    manifest_bytes = get(source, source_root, 'bundle-manifest.json')
    manifest = json.loads(manifest_bytes)
    if manifest.get('kind') != 'feature-v3-development-smoke-source':
        fail('wrong source kind')
    if manifest.get('development_only') is not True or manifest.get('training_performed') is not False:
        fail('unexpected source scope')
    if {name: sha(get(source, source_root, name)) for name in manifest['files']} != manifest['files']:
        fail('source inventory differs')
    inputs = [json.loads(line) for line in get(source, source_root, 'inputs.jsonl').splitlines() if line.strip()]
    if len(inputs) != 32 or [row['id'] for row in inputs] != manifest['input_ids']:
        fail('source inputs differ')
    input_by_id = {r['id']: r for r in inputs}
    inventory = json.loads(get(result, result_root, 'files-sha256.json'))
    actual = {Path(name).name: sha(payload) for name, payload in result.items()
              if Path(name).parts[0] == result_root and Path(name).name != 'files-sha256.json'}
    if actual != inventory:
        fail('returned file inventory differs')
    summary = json.loads(get(result, result_root, 'summary.json'))
    if summary.get('status') != 'completed' or summary.get('kind') != 'feature-v3-development-smoke':
        fail('GPU smoke did not complete')
    if summary.get('source_manifest_sha256') != sha(manifest_bytes) or summary.get('documents') != 32:
        fail('source binding or document count differs')
    if summary.get('training_performed') is not False or summary.get('threshold_selected') is not False or summary.get('detector_quality_measured') is not False:
        fail('unexpected training/evaluation claim')
    protocol = json.loads(get(result, result_root, 'protocol.json'))
    if protocol.get('source_manifest_sha256') != sha(manifest_bytes) or protocol.get('protocol_fingerprint') != summary['protocol_fingerprint']:
        fail('feature protocol binding differs')
    if protocol['protocol']['protocol_version'] != 3 or protocol['protocol']['model_revision'] != manifest['model_revision']:
        fail('wrong feature protocol/model revision')
    if protocol['layers'] != [6, 18, 30] or summary['layers'] != [6, 18, 30]:
        fail('unexpected layer sweep')
    rows = [json.loads(line) for line in get(result, result_root, 'vectors.jsonl').splitlines() if line.strip()]
    if len(rows) != 32 or set(r['id'] for r in rows) != set(input_by_id):
        fail('feature rows differ from inputs')
    dim = summary['hidden_size']
    if type(dim) is not int or dim <= 0:
        fail('invalid hidden dimension')
    stable = 0
    for row in rows:
        source_row = input_by_id[row['id']]
        if row['text_sha256'] != source_row['text_sha256'] or row['protocol_fingerprint'] != summary['protocol_fingerprint']:
            fail('feature identity/protocol differs')
        rendering = row['rendering']
        base, boundary = rendering['baseline'], rendering['boundary']
        for view in (base, boundary):
            if not (len(view['input_ids']) == view['token_count'] == len(view['content_mask'])):
                fail('token accounting differs')
            if view['content_positions'] != [i for i, flag in enumerate(view['content_mask']) if flag]:
                fail('content positions differ from mask')
        if boundary['boundary_position'] != boundary['token_count'] - 1 or boundary['boundary_token_id'] != boundary['input_ids'][-1]:
            fail('boundary position/token differs')
        if boundary['boundary_neighbor_ids'] != boundary['input_ids'][-min(8, boundary['token_count']):]:
            fail('boundary neighbors differ')
        prefix = boundary['input_ids'][:base['token_count']] == base['input_ids']
        if prefix != rendering['prefix_token_ids_stable']:
            fail('prefix comparison differs')
        stable += prefix
        for pool in ('content_last', 'content_mean'):
            for layer in ('6', '18', '30'):
                check_vector(row['baseline_features'][pool][layer], dim, row['id'])
                check_vector(row['boundary_features'][pool][layer], dim, row['id'])
        for layer in ('6', '18', '30'):
            check_vector(row['boundary_features']['assistant_boundary'][layer], dim, row['id'])
    if summary['totals']['prefix_stable'] != stable or summary['totals']['prefix_unstable'] != 32 - stable:
        fail('prefix totals differ')
    if summary['totals']['forwards'] != 65:
        fail('expected 32 two-view forwards plus one repeatability forward')
    comparisons = json.loads(get(result, result_root, 'comparisons.json'))
    if len(comparisons) != 32 or [r['id'] for r in comparisons] != [r['id'] for r in rows]:
        fail('comparison records differ')
    scientific = (stable == 32 and summary['totals']['causal_prefix_above_tolerance'] == 0
                  and not summary['repeatability_above_tolerance'])
    if summary['scientific_smoke_pass'] != scientific:
        fail('scientific smoke decision differs from diagnostics')
    return {'kind': 'feature-v3-smoke-audit', 'status': 'verified',
            'scientific_smoke_pass': scientific, 'documents': 32, 'forwards': 65,
            'prefix_stable_documents': stable, 'layers': [6, 18, 30],
            'hidden_size': dim, 'source_bundle_sha256': sha(Path(source_archive).read_bytes()),
            'returned_archive_sha256': sha(Path(result_archive).read_bytes()),
            'protocol_fingerprint': summary['protocol_fingerprint'],
            'training_performed': False, 'detector_quality_measured': False,
            'note': 'This verifies feature provenance, dimensions and renderer diagnostics; it does not estimate detector quality.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.bundle, args.archive)
    with args.output.open('x') as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
