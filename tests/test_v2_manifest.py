from dataclasses import replace
import pytest
from smaip.probes.manifest import DocumentRecord, validate_manifest


def corpus():
    rows = []
    for index, split in enumerate(('train', 'calibration', 'test')):
        for label in (0, 1):
            rows.append(DocumentRecord(f'{split}-{label}', f'unique source {split} label {label}', label, split,
                                       f'group-{index}-{label}', f'source-{index}-{label}', f'family-{index}' if label else None))
    return rows


def test_manifest_checks_disjoint_sources_families_and_duplicates():
    rows = corpus()
    assert validate_manifest(rows)['group_source_family_disjoint']
    assert not validate_manifest(rows)['sample_size_screen_passed']
    with pytest.raises(ValueError, match='group_id crosses'):
        validate_manifest(rows[:2] + [replace(rows[2], group_id=rows[0].group_id)] + rows[3:])
    with pytest.raises(ValueError, match='attack_family crosses'):
        validate_manifest(rows[:3] + [replace(rows[3], attack_family=rows[1].attack_family)] + rows[4:])
    with pytest.raises(ValueError, match='normalized_text crosses'):
        validate_manifest(rows[:2] + [replace(rows[2], text=rows[0].text.upper() + '  ')] + rows[3:])
    with pytest.raises(ValueError, match='document labels'):
        replace(rows[0], label_scope='vendor')
