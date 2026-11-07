#!/usr/bin/env python3
"""Validate the focused V3 numerical-prefix diagnostic archive."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import tarfile


SOURCE_SHA256 = '28cab08911171840e1f066c725dd23a788e6a9c64a132ec53bba22a5b3a21f94'
PARENT_SHA256 = '850528f73d92d370728e48f0e824751e59e52ecb4bcb1d9ebda2fd7f9a4a6266'
EXPECTED_IDS = ['dev01-test-1-05', 'dev01-test-1-06', 'dev01-calibration-0-01']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def analyze(archive_path, source_path, parent_path):
    if sha(source_path) != SOURCE_SHA256 or sha(parent_path) != PARENT_SHA256:
        raise ValueError('source or original smoke archive differs')
    with tarfile.open(archive_path, 'r:gz') as tar:
        files = {}
        for member in tar.getmembers():
            path = Path(member.name)
            if path.is_absolute() or '..' in path.parts or member.issym() or member.islnk():
                raise ValueError('unsafe archive member')
            if member.isfile():
                if member.name in files:
                    raise ValueError('duplicate archive member')
                files[member.name] = tar.extractfile(member).read()
            elif not member.isdir():
                raise ValueError('unsupported archive member')
    root = 'feature-v3-prefix-diagnostic-01/'
    if set(files) != {root + name for name in ('model.log', 'summary.json', 'comparisons.json', 'files-sha256.json')}:
        raise ValueError('unexpected diagnostic archive inventory')
    inventory = json.loads(files[root + 'files-sha256.json'])
    if inventory != {name: hashlib.sha256(files[root + name]).hexdigest()
                     for name in ('model.log', 'summary.json', 'comparisons.json')}:
        raise ValueError('result inventory differs')
    summary = json.loads(files[root + 'summary.json'])
    rows = json.loads(files[root + 'comparisons.json'])
    if (summary['status'] != 'completed' or summary['kind'] != 'feature-v3-prefix-diagnostic' or
            summary['source_bundle_sha256'] != SOURCE_SHA256 or
            summary['parent_archive_sha256'] != PARENT_SHA256 or
            summary['target_ids'] != EXPECTED_IDS or summary['forwards'] != 9 or
            summary['training_performed'] is not False or summary['detector_quality_measured'] is not False):
        raise ValueError('diagnostic source, scope or execution differs')
    if len(rows) != 3 or [r['id'] for r in rows] != EXPECTED_IDS:
        raise ValueError('comparison identities differ')
    replay, same_length = [], []
    for row in rows:
        if row['control_tokens'] != row['boundary_tokens'] or row['baseline_tokens'] >= row['boundary_tokens']:
            raise ValueError('invalid sequence-length control')
        for name in ('replay_baseline', 'replay_boundary', 'length_change_baseline_vs_boundary',
                     'same_length_changed_suffix_boundary_vs_control'):
            group = row[name]
            if set(group) != {f'{pool}/{layer}' for pool in ('content_last', 'content_mean')
                              for layer in (6, 18, 30)}:
                raise ValueError('incomplete layer/pool comparisons')
            if any(not math.isfinite(v['max_abs']) or v['max_abs'] < 0 or
                   not math.isfinite(v['max_abs_over_vector_scale']) or
                   v['different_coordinates'] < 0 for v in group.values()):
                raise ValueError('invalid comparison statistics')
        replay.extend(v['max_abs'] for group in ('replay_baseline', 'replay_boundary')
                      for v in row[group].values())
        same_length.extend(v['max_abs'] for v in row['same_length_changed_suffix_boundary_vs_control'].values())
    if (summary['max_replay_abs_difference'] != max(replay) or
            summary['max_same_length_changed_suffix_abs_difference'] != max(same_length) or
            summary['shape_effect_supported'] != (max(replay) <= .02 and max(same_length) <= .02)):
        raise ValueError('diagnostic conclusion differs from saved comparisons')
    return {'status': 'verified', 'kind': 'feature-v3-prefix-diagnostic-audit',
            'shape_effect_supported': summary['shape_effect_supported'],
            'max_replay_abs_difference': max(replay),
            'max_same_length_changed_suffix_abs_difference': max(same_length),
            'source_bundle_sha256': SOURCE_SHA256, 'parent_archive_sha256': PARENT_SHA256,
            'returned_archive_sha256': sha(archive_path),
            'original_smoke_scientific_pass': False, 'training_performed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.archive, args.source, args.parent)
    with args.output.open('x') as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
