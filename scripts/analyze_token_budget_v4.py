#!/usr/bin/env python3
"""Audit exact-source tokenizer-budget results without treating rows as reviewed."""

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import tarfile


BUDGETS = (512, 1024, 2048, 4096)
VIEWS = ('inspection_boundary', 'task_boundary', 'task_only_boundary')


def sha(value):
    return hashlib.sha256(value).hexdigest()


def files(archive):
    with tarfile.open(archive, 'r:gz') as tar:
        result = {}
        for member in tar.getmembers():
            path = Path(member.name)
            if path.is_absolute() or '..' in path.parts or member.issym() or member.islnk():
                raise ValueError('unsafe archive member')
            if member.isfile():
                if member.name in result:
                    raise ValueError('duplicate archive member')
                result[member.name] = tar.extractfile(member).read()
            elif not member.isdir():
                raise ValueError('unsupported archive member')
        return result


def distribution(values):
    values = sorted(values)
    return {'min': values[0], 'median': values[(len(values) - 1) // 2],
            'p95': values[int(.95 * (len(values) - 1))], 'max': values[-1],
            'above_budget': {str(b): sum(value > b for value in values) for b in BUDGETS}}


def summarize(rows):
    return {view: distribution([row['views'][view]['total_tokens'] for row in rows]) for view in VIEWS}


def analyze(bundle_path, archive_path):
    source, result = files(bundle_path), files(archive_path)
    source_roots = {Path(name).parts[0] for name in source}
    result_roots = {Path(name).parts[0] for name in result}
    if len(source_roots) != 1 or len(result_roots) != 1:
        raise ValueError('expected one archive root')
    sr, rr = source_roots.pop(), result_roots.pop()
    def get(collection, root, name):
        try:
            return collection[root + '/' + name]
        except KeyError:
            raise ValueError('missing archive member: ' + name) from None
    manifest_bytes = get(source, sr, 'bundle-manifest.json')
    manifest = json.loads(manifest_bytes)
    if (manifest['kind'] != 'feature-v4-token-budget-source' or
            manifest['candidate_reviewed'] is not False or manifest['labels_exported'] is not False or
            manifest['training_performed'] is not False):
        raise ValueError('wrong source scope')
    if {name: sha(get(source, sr, name)) for name in manifest['files']} != manifest['files']:
        raise ValueError('source file inventory differs')
    inputs = [json.loads(line) for line in get(source, sr, 'inputs.jsonl').splitlines() if line.strip()]
    if len(inputs) != 1012 or [r['id'] for r in inputs] != manifest['input_ids']:
        raise ValueError('candidate IDs differ')
    by_id = {r['id']: r for r in inputs}
    if len(by_id) != 1012 or any('label' in r for r in inputs):
        raise ValueError('duplicate input or exported label')
    inventory = json.loads(get(result, rr, 'files-sha256.json'))
    actual = {Path(name).name: sha(value) for name, value in result.items()
              if Path(name).parts[0] == rr and Path(name).name != 'files-sha256.json'}
    if actual != inventory:
        raise ValueError('returned file inventory differs')
    summary = json.loads(get(result, rr, 'summary.json'))
    if (summary.get('status') != 'completed' or summary.get('kind') != 'feature-v4-token-budget' or
            summary.get('candidate_count') != 1012 or
            summary.get('candidate_corpus_sha256') != manifest['candidate_corpus_sha256'] or
            summary.get('source_manifest_sha256') != sha(manifest_bytes) or
            summary.get('model_revision') != manifest['model_revision'] or
            summary.get('model_loaded') is not False or
            summary.get('training_performed') is not False or
            summary.get('threshold_selected') is not False or
            summary.get('detector_quality_measured') is not False):
        raise ValueError('unexpected tokenizer result scope')
    rows = [json.loads(line) for line in get(result, rr, 'token-counts.jsonl').splitlines() if line.strip()]
    if len(rows) != 1012 or [r['id'] for r in rows] != manifest['input_ids']:
        raise ValueError('token row identities differ')
    groups = defaultdict(list)
    for row in rows:
        original = by_id[row['id']]
        if (row['source_origin'] != original['source_origin'] or
                row['native_role'] != original['native_role'] or
                row['task_sha256'] != original['task_sha256'] or
                row['text_sha256'] != original['text_sha256']):
            raise ValueError('token row provenance differs')
        if set(row['views']) != set(VIEWS):
            raise ValueError('missing tokenizer view')
        for view in VIEWS:
            value = row['views'][view]
            if (type(value['total_tokens']) is not int or value['total_tokens'] <= 0 or
                    type(value['content_tokens']) is not int or value['content_tokens'] < 0 or
                    value['content_tokens'] > value['total_tokens'] or
                    type(value['final_token_id']) is not int or value['final_token_id'] < 0):
                raise ValueError('invalid token accounting')
            if view == 'task_only_boundary':
                if value['content_tokens'] != 0 or value['last_content_position'] is not None:
                    raise ValueError('task-only view includes tool content')
            elif (value['content_tokens'] == 0 or type(value['last_content_position']) is not int or
                  value['last_content_position'] >= value['total_tokens'] - 1):
                raise ValueError('no separated literal tool span')
        groups[row['source_origin']].append(row)
    if (summary['eligible_task_stream_count'] != len(groups) or
            summary['by_source_counts'] != {k: len(v) for k, v in groups.items()} or
            summary['overall'] != summarize(rows) or
            summary['by_source'] != {k: summarize(v) for k, v in groups.items()}):
        raise ValueError('reported token distributions differ')
    return {'status': 'verified', 'kind': 'feature-v4-token-budget-audit',
            'candidate_count': 1012, 'eligible_task_stream_count': len(groups),
            'source_bundle_sha256': sha(Path(bundle_path).read_bytes()),
            'returned_archive_sha256': sha(Path(archive_path).read_bytes()),
            'overall': summary['overall'], 'by_source': summary['by_source'],
            'candidate_reviewed': False, 'model_loaded': False,
            'training_performed': False,
            'note': 'Tokenizer coverage only; no label review or detector quality conclusion.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.bundle, args.archive)
    with args.output.open('x') as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
