#!/usr/bin/env python3
"""Compare the immutable LLMail owner review with source and earlier AV screen."""

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import review_llmail_misses as packet  # noqa: E402

REVIEW = ROOT / '.local-data/feature-v4-llmail-owner-review-01/owner-review-20261112T232627Z-9fb7bb.json'
REVIEW_SHA = '538bb85cb1b431b483a69cc69901cff4325c6561b05720298f4d7d3f444bdd5b'
FIRST_ANSWER = ROOT / '.local-data/feature-v4-review-packet-01/sealed-answer.jsonl'
FIRST_SCREEN = ROOT / '.local-data/feature-v4-reviewer-packet-01/human-review-submission-20261107T060208Z-0b349d.jsonl'
FIRST_ANSWER_SHA = 'ba2a45a6078c289a9d45dbf60953b349b01f04c8affbe27180702c47ff8bd10e'
FIRST_SCREEN_SHA = '708d74fb9bfd0560746db9b39e2d2dd3a7a1d8ff58f0865df74bde0c28121824'
MANIFEST = ROOT / '.local-data/feature-v4-solo-audit-01/candidate-manifest.jsonl'
MANIFEST_SHA = '8952a310a6e47663c15416909dbe20a9385939429c4410afafb396dd6785b7ae'
OUTPUT = ROOT / '.local-data/feature-v4-llmail-owner-review-audit-01/summary.json'


def checked(path: Path, expected: str) -> bytes:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f'input hash differs: {path}')
    return raw


def read_jsonl(raw: bytes) -> list[dict]:
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def audit() -> dict:
    rows, packet_sha, provenance = packet.load_packet()
    review = json.loads(checked(REVIEW, REVIEW_SHA))
    if (review['kind'] != 'llmail-missed-case-owner-review-01'
            or review['packet_sha256'] != packet_sha or review['provenance'] != provenance
            or review['reviewer_id'] != 'AV' or len(review['answers']) != 3):
        raise ValueError('owner review packet binding differs')
    # Run the same field checks used by the form without rewriting the saved review.
    payload = {'packet_sha256': review['packet_sha256'], 'reviewer_id': review['reviewer_id'],
               'answers': [{'review_key': a['review_key'], 'label': a['human_judgment'],
                            'boundary_clear': a['task_boundary_clear'], 'reason': a['reason']}
                           for a in review['answers']]}
    packet.validate(payload, rows, packet_sha, provenance)
    if any(a['candidate_id'] != row['candidate_id'] for a, row in zip(review['answers'], rows)):
        raise ValueError('owner review case identity differs')

    earlier = read_jsonl(checked(FIRST_ANSWER, FIRST_ANSWER_SHA))
    earlier_screen = read_jsonl(checked(FIRST_SCREEN, FIRST_SCREEN_SHA))
    if len(earlier) != len(earlier_screen) or len(earlier) != 32:
        raise ValueError('earlier AV screen length differs')
    previous = {}
    for sealed, human in zip(earlier, earlier_screen):
        if sealed['review_key'] != human['review_key']:
            raise ValueError('earlier AV screen alignment differs')
        previous[sealed['id']] = (sealed, human)
    manifest = {row['candidate_id']: row for row in read_jsonl(checked(MANIFEST, MANIFEST_SHA))}
    comparisons = []
    for answer in review['answers']:
        candidate_id = answer['candidate_id']
        old, old_human = previous[candidate_id]
        candidate = manifest[candidate_id]
        if (old['upstream_label'] != 1 or candidate['source_label'] != 1
                or old_human['human_judgment'] != 'attack'
                or candidate['av_screen_judgment'] != 'attack'
                or candidate['candidate_sha256'] != old['candidate_sha256']
                or candidate['accepted_label'] is not None
                or candidate['split_role'] != 'unassigned'):
            raise ValueError(f'prior review or manifest differs: {candidate_id}')
        comparisons.append({'review_key': answer['review_key'], 'candidate_id': candidate_id,
                            'prior_review_key': old['review_key'], 'source_label': 'attack',
                            'prior_av_screen': old_human['human_judgment'],
                            'new_av_judgment': answer['human_judgment'],
                            'task_boundary_clear': answer['task_boundary_clear'],
                            'same_as_prior': answer['human_judgment'] == old_human['human_judgment'],
                            'same_as_source': answer['human_judgment'] == 'attack',
                            'metadata_component': candidate['metadata_component'],
                            'exact_pair_size': candidate['exact_pair_size'],
                            'accepted_label': None})
    r031 = next(row for row in manifest.values() if row['candidate_id'] == 'nvidia-12-clean')
    if (r031['status'] != 'quarantined' or r031['accepted_label'] is not None
            or r031['split_role'] != 'unassigned'):
        raise ValueError('R031 quarantine changed')
    if len({row['metadata_component'] for row in comparisons}) != 1:
        raise ValueError('missed cases no longer share lineage component')
    return {'kind': 'llmail-owner-review-audit-01', 'review_sha256': REVIEW_SHA,
            'packet_sha256': packet_sha, 'first_screen_sha256': FIRST_SCREEN_SHA,
            'candidate_manifest_sha256': MANIFEST_SHA,
            'reviewed_cases': len(comparisons),
            'source_agreement': sum(row['same_as_source'] for row in comparisons),
            'source_disagreement': sum(not row['same_as_source'] for row in comparisons),
            'prior_av_agreement': sum(row['same_as_prior'] for row in comparisons),
            'prior_av_disagreement': sum(not row['same_as_prior'] for row in comparisons),
            'new_judgment_counts': dict(Counter(row['new_av_judgment'] for row in comparisons)),
            'comparisons': comparisons, 'r031_still_quarantined': True,
            'original_sources_and_models_changed': False,
            'accepted_new_labels': 0, 'independent_final_test': False,
            'status': 'two conflicting cases require adjudication or exclusion'}


def main() -> None:
    result = audit()
    if OUTPUT.exists():
        raise ValueError('audit 01 already exists; preserve it and version any replacement')
    OUTPUT.parent.mkdir(parents=True, mode=0o700)
    raw = (json.dumps(result, indent=2, ensure_ascii=False) + '\n').encode()
    with os.fdopen(os.open(OUTPUT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as file:
        file.write(raw)
        file.flush()
        os.fsync(file.fileno())
    print(json.dumps({'output': str(OUTPUT), 'sha256': hashlib.sha256(raw).hexdigest(),
                      'source_disagreement': result['source_disagreement'],
                      'prior_av_disagreement': result['prior_av_disagreement']}, indent=2))


if __name__ == '__main__':
    main()
