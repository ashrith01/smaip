#!/usr/bin/env python3
"""Build a second, answer-free V4 development review packet.

This is a human data-quality screen, not an independent evaluation set.
One previously reviewed row is included for an independent second judgment.
"""

from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '.local-data/corpus-review-01/prepared/candidates.jsonl'
FIRST_PACKET = ROOT / '.local-data/feature-v4-reviewer-packet-01/blind-packet.jsonl'
FIRST_ANSWERS = ROOT / '.local-data/feature-v4-review-packet-01/sealed-answer.jsonl'
REVIEW_OUT = ROOT / '.local-data/feature-v4-reviewer-packet-02'
SEALED_OUT = ROOT / '.local-data/feature-v4-review-packet-02'
SOURCE_SHA = '842b73014b1fc071cf9a61f1daccdd144be899ebf427970b7c8ea3bc539aec9e'
FIRST_PACKET_SHA = '2d758a233dd770c8f2d0ab5b64e0670294f0c1fed8c88f07272f8c7b2982d61c'
FIRST_ANSWERS_SHA = 'ba2a45a6078c289a9d45dbf60953b349b01f04c8affbe27180702c47ff8bd10e'
SEED = 'smaip-feature-v4-human-review-02-hash-only'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_checked(path: Path, expected: str) -> list[dict]:
    raw = path.read_bytes()
    if digest(raw) != expected:
        raise ValueError(f'{path.name}: input hash differs')
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def pair_key(row: dict) -> str:
    return digest(json.dumps([row['trusted_task'], row['untrusted_text']],
                             ensure_ascii=False, separators=(',', ':')).encode())


def write_private(path: Path, rows: list[dict]) -> None:
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
        file.flush()
        os.fsync(file.fileno())


def write_text_private(path: Path, value: str) -> None:
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as file:
        file.write(value)
        file.flush()
        os.fsync(file.fileno())


def build() -> None:
    if REVIEW_OUT.exists() or SEALED_OUT.exists():
        raise ValueError('packet 02 already exists; preserve it and version any replacement')
    candidates = read_checked(SOURCE, SOURCE_SHA)
    first_packet = read_checked(FIRST_PACKET, FIRST_PACKET_SHA)
    first_answers = read_checked(FIRST_ANSWERS, FIRST_ANSWERS_SHA)
    eligible = {row['id']: row for row in candidates if row['label_scope'] == 'task-document'}
    if len(eligible) != 1012 or len(first_packet) != len(first_answers) != 32:
        raise ValueError('candidate or first-packet count differs')
    old_ids = {row['id'] for row in first_answers}
    old_pairs = {pair_key(row) for row in first_packet}
    repeat = next(row for row in first_answers if row['review_key'] == 'R031')
    repeat_id = repeat['id']
    if repeat_id not in eligible or eligible[repeat_id]['label'] != 0:
        raise ValueError('R031 source identity or label differs')

    strata = defaultdict(list)
    for row in eligible.values():
        if row['id'] not in old_ids and pair_key(row) not in old_pairs:
            strata[(row['source_origin'], row['label'])].append(row)
    if len(strata) != 4:
        raise ValueError('expected two sources and two labels')

    selected = [eligible[repeat_id]]
    selected_pairs = {pair_key(selected[0])}
    for stratum in sorted(strata):
        need = 15 if stratum == (selected[0]['source_origin'], selected[0]['label']) else 16
        for row in sorted(strata[stratum], key=lambda r: digest(f"{SEED}|{r['id']}".encode())):
            key = pair_key(row)
            if key in selected_pairs:
                continue
            selected.append(row)
            selected_pairs.add(key)
            need -= 1
            if need == 0:
                break
        if need:
            raise ValueError(f'not enough distinct pairs in {stratum}')
    if len(selected) != 64 or len({row['id'] for row in selected}) != 64:
        raise ValueError('selection count or uniqueness differs')
    if Counter((row['source_origin'], row['label']) for row in selected) != Counter({key: 16 for key in strata}):
        raise ValueError('selection balance differs')
    selected.sort(key=lambda row: digest(f"{SEED}|shuffle|{row['id']}".encode()))

    blind, answer, template = [], [], []
    for index, row in enumerate(selected, 1):
        key = f'V2-{index:03d}'
        blind.append({k: row[k] for k in ('source_origin', 'native_role', 'trusted_task', 'untrusted_text')}
                     | {'review_key': key})
        answer.append({'review_key': key, 'candidate_id': row['id'], 'upstream_label': row['label'],
                       'source_origin': row['source_origin'], 'source_context_id': row['source_context_id'],
                       'pair_id': row['pair_id'], 'template_id': row['template_id'],
                       'author_id': row['author_id'], 'generation_batch': row['generation_batch'],
                       'pair_sha256': pair_key(row), 'prior_review_key': 'R031' if row['id'] == repeat_id else None})
        template.append({'review_key': key, 'human_judgment': None, 'task_boundary_clear': None,
                         'reason': '', 'reviewer_id': '', 'reviewed_at_utc': None})

    REVIEW_OUT.mkdir(mode=0o700, parents=True)
    SEALED_OUT.mkdir(mode=0o700, parents=True)
    write_private(REVIEW_OUT / 'blind-packet.jsonl', blind)
    write_private(REVIEW_OUT / 'human-review-template.jsonl', template)
    write_text_private(REVIEW_OUT / 'README.md',
        '# Feature V4 second reviewer packet\n\n'
        'Review all 64 task/document pairs without opening other packet directories, '
        'source labels, model scores, or prior reviews. One case is a blinded repeat '
        'for independent second judgment. Use a reviewer other than AV.\n\n'
        'Use `attack` when untrusted text attempts to redirect the assistant beyond '
        'the trusted user task; use `benign` for ordinary task content, including '
        'a request addressed to someone else; use `ambiguous` when the target or '
        'boundary cannot be resolved. Record a reason, task-boundary clarity, '
        'reviewer ID, and UTC time for every case. Do not guess the upstream label.\n\n'
        'This is a development data-quality screen, not calibration or final test data.\n')
    write_private(SEALED_OUT / 'sealed-answer.jsonl', answer)
    manifest = {'kind': 'development-human-review-02', 'candidate_source_sha256': SOURCE_SHA,
                'first_packet_sha256': FIRST_PACKET_SHA, 'first_answers_sha256': FIRST_ANSWERS_SHA,
                'selection_seed': SEED, 'total': 64, 'fresh_pairs': 63,
                'repeat_candidate_id': repeat_id,
                'blind_packet_sha256': digest((REVIEW_OUT / 'blind-packet.jsonl').read_bytes()),
                'sealed_answer_sha256': digest((SEALED_OUT / 'sealed-answer.jsonl').read_bytes()),
                'independent_test': False, 'calibration_eligible': False}
    write_text_private(SEALED_OUT / 'manifest.json', json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'review_packet': str(REVIEW_OUT), 'cases': 64, 'fresh_pairs': 63,
                      'repeat_blinded': True, 'answer_file_separate': True}, indent=2))


if __name__ == '__main__':
    build()
