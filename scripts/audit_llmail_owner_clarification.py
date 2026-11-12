#!/usr/bin/env python3
"""Audit AV's linked correction without rewriting either earlier submission."""

import hashlib
import json
import os
from pathlib import Path

import audit_llmail_owner_review as prior


CLARIFICATION = prior.ROOT / '.local-data/feature-v4-llmail-owner-review-01/owner-clarification-20261112T233124Z.json'
CLARIFICATION_SHA = 'ab7884d08d8e3939d44b27519a72f4ea9ea816fa2688ff3161c901839bd522cd'
PRIOR_AUDIT_SHA = 'caf95109b84835a980f5caaae3d18fa3d201f7bf33b46971a4943c0f12c2bdfa'
OUTPUT = prior.ROOT / '.local-data/feature-v4-llmail-owner-review-audit-02/summary.json'


def audit() -> dict:
    saved_prior = json.loads(prior.checked(prior.OUTPUT, PRIOR_AUDIT_SHA))
    if saved_prior != prior.audit():
        raise ValueError('first comparison audit no longer reproduces')
    clarification = json.loads(prior.checked(CLARIFICATION, CLARIFICATION_SHA))
    if (clarification['kind'] != 'llmail-owner-review-clarification-01'
            or clarification['reviewer_id'] != 'AV'
            or clarification['clarification_text_verbatim'] != 'kepp them as attack as AV review'
            or clarification['linked_submission_sha256'] != saved_prior['review_sha256']
            or clarification['linked_prior_screen_sha256'] != saved_prior['first_screen_sha256']
            or clarification['original_submissions_modified'] is not False
            or clarification['additional_human_reason_provided'] is not False):
        raise ValueError('clarification provenance differs')
    expected = {(row['review_key'], row['candidate_id'], row['prior_review_key'])
                for row in saved_prior['comparisons'] if not row['same_as_prior']}
    corrections = clarification['applies_to']
    if (len(corrections) != 2
            or {(row['review_key'], row['candidate_id'], row['prior_review_key']) for row in corrections} != expected
            or any(row['clarified_human_judgment'] != 'attack' for row in corrections)):
        raise ValueError('clarification does not match the two conflicting rows')
    corrected = {row['review_key']: row['clarified_human_judgment'] for row in corrections}
    comparisons = []
    for row in saved_prior['comparisons']:
        effective = corrected.get(row['review_key'], row['new_av_judgment'])
        comparisons.append({'review_key': row['review_key'], 'candidate_id': row['candidate_id'],
                            'source_label': row['source_label'], 'prior_av_screen': row['prior_av_screen'],
                            'submitted_judgment': row['new_av_judgment'],
                            'clarified_av_judgment': effective,
                            'clarification_applied': row['review_key'] in corrected,
                            'accepted_label': None})
    if any(row['clarified_av_judgment'] != 'attack' for row in comparisons):
        raise ValueError('effective judgment differs')
    return {'kind': 'llmail-owner-review-audit-02',
            'prior_audit_sha256': PRIOR_AUDIT_SHA, 'clarification_sha256': CLARIFICATION_SHA,
            'source_agreement_after_clarification': 3,
            'prior_screen_agreement_after_clarification': 3,
            'comparisons': comparisons, 'r031_still_quarantined': saved_prior['r031_still_quarantined'],
            'accepted_new_labels': 0, 'training_set_changed': False, 'policy_changed': False,
            'original_submissions_modified': False, 'independent_final_test': False,
            'status': 'review discrepancy reconciled; development evidence only'}


def main() -> None:
    result = audit()
    if OUTPUT.exists():
        raise ValueError('audit 02 already exists; preserve it and version any replacement')
    OUTPUT.parent.mkdir(parents=True, mode=0o700)
    raw = (json.dumps(result, indent=2, ensure_ascii=False) + '\n').encode()
    with os.fdopen(os.open(OUTPUT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as file:
        file.write(raw)
        file.flush()
        os.fsync(file.fileno())
    print(json.dumps({'output': str(OUTPUT), 'sha256': hashlib.sha256(raw).hexdigest(),
                      'clarified_attack_judgments': result['source_agreement_after_clarification']}, indent=2))


if __name__ == '__main__':
    main()
