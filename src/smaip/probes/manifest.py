"""Frozen V2 document labels and disjoint source/family/group membership."""
from dataclasses import asdict, dataclass
import hashlib
import json
import re


@dataclass(frozen=True)
class DocumentRecord:
    id: str
    text: str
    label: int
    split: str
    group_id: str
    source_id: str
    attack_family: str | None = None
    label_scope: str = 'document'

    def __post_init__(self):
        if not all(isinstance(value, str) and value.strip() for value in (self.id, self.text, self.group_id, self.source_id)):
            raise ValueError('document identity, text, source and group are required')
        if type(self.label) is not int or self.label not in (0, 1) or self.split not in {'train', 'calibration', 'test'} or self.label_scope != 'document':
            raise ValueError('V2 requires explicit document labels and train/calibration/test splits')
        if self.label == 1 and (not isinstance(self.attack_family, str) or not self.attack_family.strip()):
            raise ValueError('positive documents require an attack family')


def validate_manifest(records):
    if not records or len({row.id for row in records}) != len(records):
        raise ValueError('manifest must be nonempty with unique document IDs')
    memberships = {'group_id': {}, 'source_id': {}, 'attack_family': {}, 'normalized_text': {}}
    counts = {split: {'positive': 0, 'negative': 0} for split in ('train', 'calibration', 'test')}
    for row in records:
        counts[row.split]['positive' if row.label else 'negative'] += 1
        values = {'group_id': row.group_id, 'source_id': row.source_id,
                  'normalized_text': re.sub(r'\s+', ' ', row.text.casefold()).strip()}
        if row.label:
            values['attack_family'] = row.attack_family
        for field, value in values.items():
            previous = memberships[field].setdefault(value, row.split)
            if previous != row.split:
                raise ValueError(f'{field} crosses splits; manifest is not independent')
    if any(not value['positive'] or not value['negative'] for value in counts.values()):
        raise ValueError('every split must contain both document labels')
    canonical = [asdict(row) for row in sorted(records, key=lambda row: row.id)]
    return {'schema_version': 2, 'records': len(records), 'counts': counts,
            'manifest_sha256': hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest(),
            'group_source_family_disjoint': True,
            'sample_size_screen_passed': all(counts[split]['negative'] >= 299 for split in ('calibration', 'test')),
            'note': 'This validates declared groups and normalized exact duplicates; label correctness, near-duplicates and statistical independence still need review.'}


def load_manifest(path):
    records = [DocumentRecord(**json.loads(line)) for line in path.read_text().splitlines() if line.strip()]
    return records, validate_manifest(records)
