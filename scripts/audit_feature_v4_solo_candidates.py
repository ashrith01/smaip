#!/usr/bin/env python3
"""Audit pinned V4 task/document candidates without accepting source labels.

Writes a new ignored, versioned manifest and summary. It neither changes the
candidate queue nor creates human review records or an accepted split.
"""

from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from smaip.probes.corpus_v3 import Candidate  # noqa: E402
from smaip.probes.external_v2 import shingles, similar  # noqa: E402


SOURCE = ROOT / '.local-data/corpus-review-01/prepared/candidates.jsonl'
INVENTORY = ROOT / '.local-data/corpus-review-01/prepared/source-inventory.json'
INVENTORY_SHA = '630dd62f955753ee53346f181bbdd911dfd608ce72ea7eb70d0900933ea461dc'
FIRST_PACKET = ROOT / '.local-data/feature-v4-reviewer-packet-01/blind-packet.jsonl'
FIRST_ANSWERS = ROOT / '.local-data/feature-v4-review-packet-01/sealed-answer.jsonl'
HUMAN_SCREEN = ROOT / '.local-data/feature-v4-reviewer-packet-01/human-review-submission-20261107T060208Z-0b349d.jsonl'
OUTPUT = ROOT / '.local-data/feature-v4-solo-audit-01'
EXPECTED = {
    SOURCE: '842b73014b1fc071cf9a61f1daccdd144be899ebf427970b7c8ea3bc539aec9e',
    FIRST_PACKET: '2d758a233dd770c8f2d0ab5b64e0670294f0c1fed8c88f07272f8c7b2982d61c',
    FIRST_ANSWERS: 'ba2a45a6078c289a9d45dbf60953b349b01f04c8affbe27180702c47ff8bd10e',
    HUMAN_SCREEN: '708d74fb9bfd0560746db9b39e2d2dd3a7a1d8ff58f0865df74bde0c28121824',
}
SOURCE_LICENSES = {
    'nvidia/Nemotron-RL-Agentic-Indirect-Prompt-Injection-v1': 'CC-BY-4.0',
    'microsoft/llmail-inject-challenge': 'MIT',
}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def checked(path: Path) -> bytes:
    raw = path.read_bytes()
    if sha(raw) != EXPECTED[path]:
        raise ValueError(f'input hash differs: {path}')
    return raw


def jsonl(raw: bytes) -> list[dict]:
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def pair_digest(row: Candidate | dict) -> str:
    task = row.trusted_task if isinstance(row, Candidate) else row['trusted_task']
    text = row.untrusted_text if isinstance(row, Candidate) else row['untrusted_text']
    return sha(json.dumps([task, text], ensure_ascii=False, separators=(',', ':')).encode())


class Groups:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, i: int, j: int) -> bool:
        a, b = self.find(i), self.find(j)
        if a == b:
            return False
        self.parent[b] = a
        return True

    def ids(self, rows: list[Candidate]) -> tuple[dict[str, str], list[int]]:
        components = defaultdict(list)
        for i, row in enumerate(rows):
            components[self.find(i)].append(row.id)
        names = {root: sha('|'.join(sorted(ids)).encode())[:16] for root, ids in components.items()}
        return {row.id: names[self.find(i)] for i, row in enumerate(rows)}, sorted(
            (len(ids) for ids in components.values()), reverse=True)


def private_write(path: Path, value: bytes) -> None:
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as file:
        file.write(value)
        file.flush()
        os.fsync(file.fileno())


def audit() -> None:
    if OUTPUT.exists():
        raise ValueError('audit 01 already exists; preserve it and version any replacement')
    source_raw = checked(SOURCE)
    source_rows = jsonl(source_raw)
    rows = [Candidate.model_validate(row) for row in source_rows if row['label_scope'] == 'task-document']
    if len(source_rows) != 1351 or len(rows) != 1012 or len({row.id for row in rows}) != 1012:
        raise ValueError('candidate counts or identities differ')
    by_id = {row.id: row for row in rows}
    inventory_raw = INVENTORY.read_bytes()
    if sha(inventory_raw) != INVENTORY_SHA:
        raise ValueError('source inventory hash differs')
    inventory = json.loads(inventory_raw)
    revisions = inventory['source_revisions']
    if set(revisions) != set(SOURCE_LICENSES) | {'leolee99/NotInject'}:
        raise ValueError('source inventory differs')
    for row in rows:
        if (row.source_origin not in SOURCE_LICENSES or
                row.source_license != SOURCE_LICENSES[row.source_origin] or
                row.source_revision != revisions[row.source_origin] or
                row.source_revision not in row.source_url):
            raise ValueError(f'source declaration differs: {row.id}')
        if row.split_role != 'unassigned' or row.previously_observed:
            raise ValueError(f'candidate role/history differs: {row.id}')
    # Verify the saved upstream files used for these two sources. This verifies
    # local bytes, not current remote licensing or semantic label correctness.
    verified_files = []
    for name, expected in sorted(inventory['files'].items()):
        if '/sources/llmail/' in name or '/external-frozen-01/source/' in name:
            if Path(name).is_absolute() or '..' in Path(name).parts:
                raise ValueError(f'invalid inventory path: {name}')
            path = ROOT / name
            if sha(path.read_bytes()) != expected:
                raise ValueError(f'inventory file hash differs: {name}')
            verified_files.append(name)

    blind = jsonl(checked(FIRST_PACKET))
    sealed = jsonl(checked(FIRST_ANSWERS))
    human = jsonl(checked(HUMAN_SCREEN))
    if not (len(blind) == len(sealed) == len(human) == 32):
        raise ValueError('first review count differs')
    screened = {}
    quarantine = set()
    for b, a, h in zip(blind, sealed, human):
        if b['review_key'] != a['review_key'] or a['review_key'] != h['review_key']:
            raise ValueError('first review order differs')
        row = by_id[a['id']]
        if (pair_digest(b) != pair_digest(row) or row.fingerprint != a['candidate_sha256'] or
                row.label != a['upstream_label'] or h['human_judgment'] not in ('attack', 'benign', 'ambiguous')):
            raise ValueError(f'first review binding differs: {a["review_key"]}')
        screened[row.id] = h['human_judgment']
        if a['review_key'] == 'R031':
            if row.id != 'nvidia-12-clean' or h['human_judgment'] != 'attack' or row.label != 0:
                raise ValueError('R031 quarantine identity differs')
            quarantine.add(row.id)
    if len(screened) != 32 or quarantine != {'nvidia-12-clean'}:
        raise ValueError('human screen or quarantine differs')

    exact = defaultdict(list)
    for row in rows:
        exact[pair_digest(row)].append(row)
    conflict_groups = {key for key, members in exact.items()
                       if len({row.label for row in members}) > 1}
    for key in conflict_groups:
        quarantine.update(row.id for row in exact[key])
    canonical = {key: min(row.id for row in members) for key, members in exact.items()}

    metadata = Groups(len(rows))
    seen = {}
    for field in ('source_context_id', 'pair_id', 'template_id', 'author_id', 'generation_batch'):
        for i, row in enumerate(rows):
            value = getattr(row, field)
            if value is None:
                continue
            key = (row.source_origin, field, value)
            if key in seen:
                metadata.union(i, seen[key])
            else:
                seen[key] = i
    seen = {}
    for i, row in enumerate(rows):
        key = pair_digest(row)
        if key in seen:
            metadata.union(i, seen[key])
        else:
            seen[key] = i
    metadata_ids, metadata_sizes = metadata.ids(rows)

    # Keep a conservative diagnostic of near-copy connectivity separate from
    # declared metadata linkage; it can overconnect repetitive short texts.
    near = Groups(len(rows))
    near.parent = metadata.parent.copy()
    shingles_by_row = [shingles(row.untrusted_text) for row in rows]
    near_edges = 0
    for i, tokens in enumerate(shingles_by_row):
        for j in range(i):
            if near.find(i) != near.find(j) and similar(tokens, shingles_by_row[j]):
                near_edges += int(near.union(i, j))
    near_ids, near_sizes = near.ids(rows)

    manifest = []
    for row in sorted(rows, key=lambda item: item.id):
        key = pair_digest(row)
        status = ('quarantined' if row.id in quarantine else
                  'duplicate_reference' if canonical[key] != row.id else
                  'source_label_development_only')
        manifest.append({
            'candidate_id': row.id, 'candidate_sha256': row.fingerprint,
            'source_origin': row.source_origin, 'source_revision': row.source_revision,
            'source_license_declaration': row.source_license, 'source_row_id': row.source_row_id,
            'source_context_id': row.source_context_id, 'pair_id': row.pair_id,
            'template_id': row.template_id, 'author_id': row.author_id,
            'generation_batch': row.generation_batch, 'native_role': row.native_role,
            'source_label': row.label, 'source_label_origin': row.label_origin,
            'av_screen_judgment': screened.get(row.id),
            'av_screen_is_approval': False, 'accepted_label': None,
            'task_scope_verified': False, 'provenance_verified': False,
            'pair_sha256': key, 'exact_pair_representative': canonical[key],
            'exact_pair_size': len(exact[key]),
            'metadata_component': metadata_ids[row.id],
            'near_connected_component': near_ids[row.id],
            'status': status,
            'quarantine_reasons': (['AV/source label disagreement: R031'] if row.id == 'nvidia-12-clean' else
                                   ['exact pair has conflicting source labels'] if key in conflict_groups else []),
            'split_role': 'unassigned',
        })
    summary = {
        'kind': 'feature-v4-solo-mechanical-audit-01',
        'candidate_source_sha256': sha(source_raw), 'source_inventory_sha256': sha(inventory_raw),
        'first_packet_sha256': EXPECTED[FIRST_PACKET],
        'first_sealed_answer_sha256': EXPECTED[FIRST_ANSWERS],
        'av_screen_sha256': EXPECTED[HUMAN_SCREEN],
        'task_document_rows': len(rows), 'separate_prompt_diagnostics': len(source_rows) - len(rows),
        'source_label_counts': dict(Counter(str(row.label) for row in rows)),
        'av_screened_rows': len(screened), 'accepted_rows': 0,
        'exact_unique_pairs': len(exact),
        'exact_duplicate_groups': sum(len(group) > 1 for group in exact.values()),
        'exact_redundant_rows': sum(len(group) - 1 for group in exact.values()),
        'exact_label_conflict_groups': len(conflict_groups),
        'quarantined_rows': len(quarantine), 'quarantined_ids': sorted(quarantine),
        'metadata_components': len(metadata_sizes), 'metadata_largest': metadata_sizes[:5],
        'near_connected_components': len(near_sizes), 'near_largest': near_sizes[:5],
        'additional_near_links': near_edges,
        'source_inventory_files_hash_verified': verified_files,
        'status_counts': dict(Counter(row['status'] for row in manifest)),
        'all_splits_unassigned': True, 'human_review_complete': False,
        'independent_test': False, 'calibration_eligible': False, 'serving_enabled': False,
        'limitations': [
            'Schema and hash checks do not establish semantic task/label correctness.',
            'Pinned local source bytes and declared licenses are not a current remote license recheck.',
            'Near-copy linkage is a conservative heuristic, not population independence.',
            'AV screen judgments are not full candidate approvals; no accepted labels or splits are created.',
        ],
    }
    OUTPUT.mkdir(mode=0o700, parents=True)
    manifest_path = OUTPUT / 'candidate-manifest.jsonl'
    manifest_bytes = ''.join(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n'
                             for row in manifest).encode()
    private_write(manifest_path, manifest_bytes)
    summary['manifest_sha256'] = sha(manifest_bytes)
    private_write(OUTPUT / 'summary.json', (json.dumps(summary, indent=2, ensure_ascii=False) + '\n').encode())
    print(json.dumps({'output': str(OUTPUT), 'rows': len(rows),
                      'unique_pairs': len(exact), 'quarantined_rows': len(quarantine),
                      'accepted_rows': 0, 'manifest_sha256': summary['manifest_sha256']}, indent=2))


if __name__ == '__main__':
    audit()
