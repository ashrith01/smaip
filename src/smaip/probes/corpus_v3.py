"""Review and split contracts for future task-conditioned experiments.

This is a data schema, not a format-2 feature protocol or a new trained model.
Raw external text and review checkpoints belong outside version control.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ROLES = ('fitting', 'selection', 'threshold-development', 'statistical-calibration', 'final', 'regression', 'diagnostic', 'unassigned')
TARGETS = {'fitting': {0: 128, 1: 128}, 'selection': {0: 128, 1: 128},
           'threshold-development': {0: 400, 1: 100}}


def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Candidate(Strict):
    schema_version: Literal[3] = 3
    id: str = Field(min_length=1)
    trusted_task: str | None
    task_origin: str = Field(min_length=1)
    untrusted_text: str = Field(min_length=1)
    source_origin: str = Field(min_length=1)
    source_revision: str = Field(pattern='^[a-f0-9]{40}$')
    source_url: str = Field(min_length=1)
    source_license: str = Field(min_length=1)
    source_row_id: str = Field(min_length=1)
    source_context_id: str = Field(min_length=1)
    pair_id: str | None = None
    template_id: str | None = None
    author_id: str | None = None
    generation_batch: str | None = None
    attack_family: str | None = None
    domain: str = Field(min_length=1)
    label: Literal[0, 1]
    label_origin: Literal['upstream-annotation', 'span-deletion-control', 'assistant-authored', 'human-adjudicated']
    label_scope: Literal['task-document', 'diagnostic-prompt'] = 'task-document'
    split_role: Literal['fitting', 'selection', 'threshold-development', 'statistical-calibration', 'final', 'regression', 'diagnostic', 'unassigned'] = 'unassigned'
    native_role: Literal['tool', 'email', 'user-prompt']
    transformation: str = Field(min_length=1)
    previously_observed: bool = False

    @model_validator(mode='before')
    @classmethod
    def integer_label(cls, values):
        if isinstance(values, dict) and type(values.get('label')) is not int:
            raise ValueError('label must be an integer, not a boolean')
        return values

    @model_validator(mode='after')
    def task_scope(self):
        if self.label_scope == 'task-document' and (not self.trusted_task or not self.trusted_task.strip()):
            raise ValueError('task/document labels need an explicit authorized task')
        if self.label_scope == 'diagnostic-prompt' and self.split_role != 'diagnostic':
            raise ValueError('prompt diagnostics cannot silently become deployment tool data')
        if self.previously_observed and self.split_role not in ('regression', 'diagnostic', 'unassigned'):
            raise ValueError('observed evaluation material is regression only')
        if self.label and not self.attack_family:
            raise ValueError('attack labels require a declared family')
        return self

    @property
    def fingerprint(self):
        return checksum(self.model_dump())

    def model_input(self):
        if self.label_scope != 'task-document':
            raise ValueError('diagnostic prompt has no trusted tool-task rendering')
        return {'trusted_task': self.trusted_task, 'untrusted_text': self.untrusted_text}


class Review(Strict):
    id: str = Field(min_length=1)
    candidate_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    reviewer_id: str = Field(min_length=1)
    reviewer_type: Literal['human', 'assistant']
    decision: Literal['accept', 'reject', 'ambiguous']
    label: Literal[0, 1] | None
    task_scope_verified: bool
    provenance_verified: bool
    note: str = Field(min_length=1)

    @model_validator(mode='before')
    @classmethod
    def integer_label(cls, values):
        if isinstance(values, dict) and values.get('label') is not None and type(values['label']) is not int:
            raise ValueError('review label must be an integer')
        return values


class SplitPolicy(Strict):
    schema_version: Literal[3] = 3
    experiment: Literal['in-distribution', 'source-held-out', 'family-held-out']
    # Context/pair/template connections are always indivisible. Human-team or
    # generation-batch grouping must be chosen explicitly, never fabricated.
    group_by_author: bool
    group_by_generation_batch: bool
    min_source_streams: int = Field(default=3, ge=2)
    require_human_review: bool = True
    scope: Literal['feasibility-only'] = 'feasibility-only'


def audit(records, reviews, policy):
    if not records or len({r.id for r in records}) != len(records):
        raise ValueError('nonempty unique candidate identities required')
    by_id = {r.id: r for r in records}
    if len({r.id for r in reviews}) != len(reviews):
        raise ValueError('one adjudicated review per candidate; resolve disagreements first')
    for review in reviews:
        if review.id not in by_id or review.candidate_sha256 != by_id[review.id].fingerprint:
            raise ValueError('review identity/hash differs from candidate')
        if review.decision == 'accept' and review.label != by_id[review.id].label:
            raise ValueError('accepted label differs; revise candidate and review the new hash')
    accepted = {r.id for r in reviews if by_id[r.id].label_scope == 'task-document' and r.decision == 'accept' and r.task_scope_verified and r.provenance_verified
                and (r.reviewer_type == 'human' or not policy.require_human_review)}
    missing_review = [r.id for r in records if r.label_scope == 'task-document' and r.id not in accepted]
    fields = ['source_context_id', 'pair_id', 'template_id']
    if policy.group_by_author:
        fields.append('author_id')
    if policy.group_by_generation_batch:
        fields.append('generation_batch')
    if policy.experiment == 'source-held-out':
        fields.append('source_origin')
    elif policy.experiment == 'family-held-out':
        fields.append('attack_family')
    seen = defaultdict(dict)
    counts = {role: {0: 0, 1: 0} for role in ROLES}
    # Each edge must stay within a role, so transitive connected lineages do too.
    for row in records:
        counts[row.split_role][row.label] += 1
        if row.split_role in ('diagnostic', 'unassigned'):
            continue
        for field in fields + ['normalized_text']:
            value = re.sub(r'\s+', ' ', row.untrusted_text.casefold()).strip() if field == 'normalized_text' else getattr(row, field)
            if value is None:
                continue
            key = value if field in ('normalized_text', 'source_origin', 'attack_family') else (row.source_origin, value)
            previous = seen[field].setdefault(key, row.split_role)
            if previous != row.split_role:
                raise ValueError(field + ' lineage crosses split roles')
    from smaip.probes.external_v2 import shingles, similar
    assigned = [(r, shingles(r.untrusted_text)) for r in records if r.split_role not in ('diagnostic', 'unassigned')]
    for i, (row, tokens) in enumerate(assigned):
        for other, reference in assigned[:i]:
            if row.split_role != other.split_role and similar(tokens, reference):
                raise ValueError('near-duplicate content crosses split roles')
    shortfalls = {role: {str(label): max(0, needed - counts[role][label]) for label, needed in labels.items()}
                  for role, labels in TARGETS.items()}
    streams = {r.source_origin for r in records if r.split_role in TARGETS and r.id in accepted}
    pending = []
    if missing_review:
        pending.append('unreviewed or unresolved task documents')
    if any(any(x.values()) for x in shortfalls.values()):
        pending.append('reviewed pilot split counts not ready')
    if len(streams) < policy.min_source_streams:
        pending.append('insufficient independent eligible source streams')
    if any(r.split_role == 'unassigned' for r in records):
        pending.append('candidate groups need reviewed split assignment')
    if any(r.split_role in ('statistical-calibration', 'final') for r in records):
        pending.append('this feasibility contract cannot certify statistical calibration or final release')
    # Unknown author/template provenance and semantic near duplicates remain
    # explicit review issues, never a mechanical independence assertion.
    return {'kind': 'corpus-v3-review-audit', 'status': 'pending' if pending else 'feasibility-ready',
            'schema_version': 3, 'records': len(records), 'counts': counts, 'pilot_shortfalls': shortfalls,
            'accepted_task_documents': len(accepted), 'human_review_count': sum(r.reviewer_type == 'human' for r in reviews),
            'missing_review_count': len(missing_review), 'eligible_source_streams': sorted(streams),
            'declared_source_streams': dict(Counter(r.source_origin for r in records)),
            'unknown_author_count': sum(r.author_id is None for r in records),
            'unknown_template_count': sum(r.template_id is None for r in records),
            'pending': pending, 'population_independence_verified': False,
            'corpus_sha256': checksum([r.model_dump() for r in records]),
            'reviews_sha256': checksum([r.model_dump() for r in reviews]), 'split_policy': policy.model_dump(),
            'note': 'Mechanical identity/lineage checks do not establish independent sampling or semantic label truth.'}


def load_rows(path, model):
    return [model.model_validate(json.loads(line)) for line in Path(path).read_text().splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', required=True)
    parser.add_argument('--reviews', required=True)
    parser.add_argument('--policy', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(load_rows(args.corpus, Candidate), load_rows(args.reviews, Review),
                   SplitPolicy.model_validate_json(Path(args.policy).read_text()))
    path = Path(args.output)
    with path.open('x') as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(result['status'])


if __name__ == '__main__':
    main()
