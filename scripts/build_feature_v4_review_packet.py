#!/usr/bin/env python3
"""Prepare a blinded, local-only 32-case semantic review packet.

The packet is development evidence. It cannot turn observed candidates into
independent final data or claim human review. Scores/labels stay in a separate
ignored answer file until the screen is completed.
"""

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '.local-data/corpus-review-01/prepared/candidates.jsonl'
PREDICTIONS = ROOT / '.local-data/exploratory-fit-v4-02/predictions.jsonl'
OUTPUT = ROOT / '.local-data/feature-v4-review-packet-01'
SEED = 'smaip-feature-v4-blind-review-01-random-plus-score-tail'
SOURCE_SHA = '842b73014b1fc071cf9a61f1daccdd144be899ebf427970b7c8ea3bc539aec9e'


def sha(value):
    return hashlib.sha256(value).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def build():
    if OUTPUT.exists():
        raise ValueError('preserve existing packet; version a new selection')
    if sha(SOURCE.read_bytes()) != SOURCE_SHA:
        raise ValueError('candidate source changed')
    candidates = [json.loads(line) for line in SOURCE.read_text().splitlines() if line.strip()]
    candidates = {r['id']: r for r in candidates if r['label_scope'] == 'task-document'}
    if len(candidates) != 1012:
        raise ValueError('task candidate count differs')
    predictions = [json.loads(line) for line in PREDICTIONS.read_text().splitlines() if line.strip()]
    predictions = [r for r in predictions if r['feature'] == 'content_mean/18']
    if len(predictions) != 1012 or len({r['id'] for r in predictions}) != 1012:
        raise ValueError('selected-feature prediction count differs')
    prediction_sha = sha(PREDICTIONS.read_bytes())
    strata = defaultdict(list)
    for row in predictions:
        original = candidates[row['id']]
        if original['source_origin'] != row['source'] or original['label'] != row['label']:
            raise ValueError('prediction/candidate labels or source differ')
        strata[(row['source'], row['label'])].append(row)
    if len(strata) != 4:
        raise ValueError('expected two sources by two labels')
    selected, answer = [], []
    for (source, label), rows in sorted(strata.items()):
        # Four score-tail cases stress the apparent margin. Four disjoint
        # hash-selected cases protect against looking only where the model is
        # uncertain. The reviewer sees neither label nor score/mode.
        tail = sorted(rows, key=lambda r: (r['score'], r['id']), reverse=(label == 0))[:4]
        used = {r['id'] for r in tail}
        remainder = sorted((r for r in rows if r['id'] not in used),
                           key=lambda r: sha((SEED + r['id']).encode()))[:4]
        for mode, subset in (('score-tail', tail), ('hash-random', remainder)):
            for row in subset:
                original = candidates[row['id']]
                selected.append({'id': original['id'],
                    'source_origin': original['source_origin'],
                    'native_role': original['native_role'],
                    'trusted_task': original['trusted_task'],
                    'untrusted_text': original['untrusted_text']})
                answer.append({'id': original['id'], 'upstream_label': label,
                               'model_score': row['score'], 'selection_mode': mode,
                               'source_origin': source, 'attack_family': original['attack_family'],
                               'candidate_sha256': sha(json.dumps(original, sort_keys=True,
                                   separators=(',', ':'), ensure_ascii=False).encode()),
                               'source_row_id': original['source_row_id'],
                               'source_context_id': original['source_context_id'],
                               'source_license': original['source_license'],
                               'source_url': original['source_url'],
                               'task_origin': original['task_origin'],
                               'transformation': original['transformation']})
    if len(selected) != 32 or len({r['id'] for r in selected}) != 32:
        raise ValueError('sample count differs')
    order = sorted(range(32), key=lambda i: sha((SEED + selected[i]['id'] + 'shuffle').encode()))
    selected = [selected[i] for i in order]
    answer = [answer[i] for i in order]
    for index, (row, hidden) in enumerate(zip(selected, answer), 1):
        key = f'R{index:03d}'
        row['review_key'] = key
        del row['id']
        hidden['review_key'] = key
    OUTPUT.mkdir(parents=True)
    (OUTPUT / 'blind-packet.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in selected))
    (OUTPUT / 'sealed-answer.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in answer))
    (OUTPUT / 'assistant-screen.jsonl').write_text('')
    write(OUTPUT / 'manifest.json', {'kind': 'development-blind-label-screen',
        'candidate_source_sha256': SOURCE_SHA, 'prediction_source_sha256': prediction_sha,
        'selection_seed': SEED, 'total': len(selected),
        'stratum_counts': {str(key): 8 for key in strata},
        'selection': '4 score-tail plus 4 hash-random per source/label; packet order reshuffled',
        'packet_has_upstream_labels': False, 'packet_has_model_scores': False,
        'assistant_review_count': 0, 'human_review_count': 0,
        'independent_test': False, 'calibration_eligible': False})
    write(OUTPUT / 'files-sha256.json', {p.name: sha(p.read_bytes()) for p in sorted(OUTPUT.iterdir())
                                         if p.is_file() and p.name != 'files-sha256.json'})
    print(json.dumps({'packet': str(OUTPUT / 'blind-packet.jsonl'),
                      'cases': len(selected), 'answer_file_separate': True,
                      'human_review_count': 0, 'independent_test': False}, indent=2))


if __name__ == '__main__':
    build()
