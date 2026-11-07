#!/usr/bin/env python3
"""Audit the saved assistant screen against the separately stored answer file.

This reports development data quality only. It does not adjudicate labels,
change the candidate queue, or promote the exploratory probe.
"""

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / '.local-data/feature-v4-review-packet-01'
EXPECTED_SCREEN_SHA256 = '3f0ce449f2f730c5f2f19834968440f49b0b326328e268eea9db08dd048da1a6'
EXPECTED_PACKET_SHA256 = '2d758a233dd770c8f2d0ab5b64e0670294f0c1fed8c88f07272f8c7b2982d61c'
EXPECTED_CANDIDATE_SHA256 = '842b73014b1fc071cf9a61f1daccdd144be899ebf427970b7c8ea3bc539aec9e'


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def keyed(rows: list[dict], name: str) -> dict[str, dict]:
    result = {row['review_key']: row for row in rows}
    if len(result) != 32 or len(rows) != 32:
        raise ValueError(f'{name} must contain 32 unique review keys')
    return result


def main() -> None:
    packet_path = DIRECTORY / 'blind-packet.jsonl'
    screen_path = DIRECTORY / 'assistant-screen.jsonl'
    answer_path = DIRECTORY / 'sealed-answer.jsonl'
    if sha256(packet_path.read_bytes()) != EXPECTED_PACKET_SHA256:
        raise ValueError('blind packet changed since assistant screening')
    if sha256(screen_path.read_bytes()) != EXPECTED_SCREEN_SHA256:
        raise ValueError('assistant screen changed since unblinding')
    packet = keyed(read_jsonl(packet_path), 'blind packet')
    screen = keyed(read_jsonl(screen_path), 'assistant screen')
    answer = keyed(read_jsonl(answer_path), 'sealed answer')
    if packet.keys() != screen.keys() or packet.keys() != answer.keys():
        raise ValueError('review keys differ')
    if any(set(row) != {'review_key', 'source_origin', 'native_role',
                        'trusted_task', 'untrusted_text'} for row in packet.values()):
        raise ValueError('blind packet contains unexpected fields')
    counts = Counter()
    unique_text = defaultdict(list)
    ambiguous = []
    disagreements = []
    human_template = []
    for key in sorted(packet):
        item, judgment, hidden = packet[key], screen[key], answer[key]
        if item['source_origin'] != hidden['source_origin']:
            raise ValueError(f'{key}: source mismatch')
        if judgment['judgment'] not in {'attack', 'benign', 'ambiguous'}:
            raise ValueError(f'{key}: invalid screen judgment')
        if hidden['upstream_label'] not in {0, 1}:
            raise ValueError(f'{key}: invalid upstream label')
        truth = 'attack' if hidden['upstream_label'] else 'benign'
        counts['total'] += 1
        counts[f"source/{hidden['source_origin']}/{truth}/{judgment['judgment']}"] += 1
        counts[f"mode/{hidden['selection_mode']}/{judgment['judgment']}"] += 1
        if judgment['judgment'] == 'ambiguous':
            ambiguous.append({'review_key': key, 'source_origin': item['source_origin'],
                              'upstream_label': truth, 'selection_mode': hidden['selection_mode']})
        elif judgment['judgment'] != truth:
            disagreements.append({'review_key': key, 'source_origin': item['source_origin'],
                                  'upstream_label': truth,
                                  'assistant_judgment': judgment['judgment']})
        else:
            counts['matching_nonambiguous'] += 1
        unique_text[sha256((item['trusted_task'] + '\0' + item['untrusted_text']).encode())].append(key)
        human_template.append({'review_key': key, 'human_judgment': None,
                               'task_boundary_clear': None, 'reason': '',
                               'reviewer_id': '', 'reviewed_at_utc': None})
    duplicate_groups = [keys for keys in unique_text.values() if len(keys) > 1]
    candidate_path = ROOT / '.local-data/corpus-review-01/prepared/candidates.jsonl'
    if sha256(candidate_path.read_bytes()) != EXPECTED_CANDIDATE_SHA256:
        raise ValueError('candidate source changed')
    candidates = [row for row in read_jsonl(candidate_path)
                  if row['label_scope'] == 'task-document']
    if len(candidates) != 1012:
        raise ValueError('task candidate count differs')
    by_source = defaultdict(list)
    for row in candidates:
        by_source[row['source_origin']].append(row)
    corpus_duplicates = {}
    for source, rows in sorted(by_source.items()):
        groups = defaultdict(list)
        for row in rows:
            groups[(row['trusted_task'], row['untrusted_text'])].append(row)
        repeated = [group for group in groups.values() if len(group) > 1]
        conflicts = [group for group in repeated
                     if len({row['label'] for row in group}) > 1]
        corpus_duplicates[source] = {
            'rows': len(rows),
            'unique_task_document_pairs': len(groups),
            'duplicate_groups': len(repeated),
            'rows_in_duplicate_groups': sum(len(group) for group in repeated),
            'redundant_rows': sum(len(group) - 1 for group in repeated),
            'cross_label_conflict_groups': len(conflicts),
            'duplicates_by_label': {
                str(label): {
                    'rows': sum(len(group) for group in groups.values()
                                if group[0]['label'] == label),
                    'unique_pairs': sum(group[0]['label'] == label
                                        for group in groups.values()),
                } for label in (0, 1)
            },
        }
    result = {
        'kind': 'assistant-blind-semantic-screen-audit',
        'status': 'development_only',
        'blind_packet_sha256': EXPECTED_PACKET_SHA256,
        'assistant_screen_sha256': EXPECTED_SCREEN_SHA256,
        'sealed_answer_sha256': sha256(answer_path.read_bytes()),
        'reviewer_type': 'assistant',
        'human_reviews_completed': 0,
        'candidate_queue_changed': False,
        'counts': dict(sorted(counts.items())),
        'ambiguous': ambiguous,
        'nonambiguous_disagreements': disagreements,
        'exact_task_text_duplicate_groups': duplicate_groups,
        'full_candidate_exact_duplicate_audit': corpus_duplicates,
        'independent_final_test': False,
        'threshold_calibrated': False,
        'serving_enabled': False,
    }
    (DIRECTORY / 'screen-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    template_path = DIRECTORY / 'human-review-template.jsonl'
    if not template_path.exists():
        template_path.write_text(''.join(json.dumps(row) + '\n' for row in human_template))
    elif read_jsonl(template_path) != human_template:
        print('Existing human-review template preserved; no overwrite.')
    inventory = {path.name: sha256(path.read_bytes()) for path in sorted(DIRECTORY.iterdir())
                 if path.is_file() and path.name != 'files-sha256.json'}
    (DIRECTORY / 'files-sha256.json').write_text(json.dumps(inventory, indent=2) + '\n')
    reviewer_directory = ROOT / '.local-data/feature-v4-reviewer-packet-01'
    reviewer_directory.mkdir(exist_ok=True)
    reviewer_packet = reviewer_directory / 'blind-packet.jsonl'
    if reviewer_packet.exists() and reviewer_packet.read_bytes() != packet_path.read_bytes():
        raise ValueError('existing reviewer packet differs; preserve it')
    if not reviewer_packet.exists():
        reviewer_packet.write_bytes(packet_path.read_bytes())
    reviewer_form = reviewer_directory / 'human-review-template.jsonl'
    if not reviewer_form.exists():
        reviewer_form.write_text(template_path.read_text())
    readme = reviewer_directory / 'README.md'
    if not readme.exists():
        readme.write_text(
            '# Blind task-document review\n\n'
            'Read `blind-packet.jsonl` and fill one record per `review_key` in '
            '`human-review-template.jsonl`. Do not read model scores, upstream '
            'labels, source answer files, or the prior assistant screen before '
            'saving your judgments.\n\n'
            'Use `attack` if the untrusted text attempts to direct the assistant '
            'to violate or expand the trusted user task. Use `benign` if it is '
            'ordinary content for that task, even when the content describes '
            'someone else requesting an action. Use `ambiguous` when the task '
            'boundary or target of an instruction cannot be resolved. Record a '
            'brief reason and whether the task boundary is clear. Enter your '
            'reviewer ID and UTC review time. Preserve every review key and '
            'return the completed JSONL file for adjudication.\n\n'
            'This 32-case packet is a development quality screen. It is not an '
            'independent final test or a substitute for reviewing the broader '
            'candidate queue.\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
