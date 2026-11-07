#!/usr/bin/env python3
"""Build a bounded, UNREVIEWED candidate queue from pinned local snapshots.

No network requests, model calls, fitting, automatic label approval or split
assignment. External text stays in an ignored output directory. Requires
pyarrow only for decoding the three tiny NotInject Parquet snapshots.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from smaip.probes.corpus_v3 import Candidate, SplitPolicy, audit
from smaip.probes.external_v2 import (REPO, REVISION, UPSTREAM_SHA256, extract_pair, select_pairs,
                                     normalize, text_hash, load_prepared)


LLMAIL = 'microsoft/llmail-inject-challenge'
LLMAIL_REVISION = '1063bdf01ec8762b812d5e06ee768a06faa5a6f7'
NOTINJECT = 'leolee99/NotInject'
NOTINJECT_REVISION = '847ae76cf8fea5ed325429e569ae8cfef022d2e0'
SEED = 'smaip-corpus-review-01-no-model-scores'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def pinned_source(root, repo, revision):
    meta = json.loads((root / 'hub-metadata.json').read_text())
    if meta['sha'] != revision or meta['id'] != repo or meta['cardData']['license'] != 'mit':
        raise ValueError('source revision/license metadata differs')
    if 'license: mit' not in (root / 'README.md').read_text():
        raise ValueError('pinned source card must explicitly declare MIT')


def prepare(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    repo_root = Path(__file__).resolve().parents[1]
    if not output.resolve().is_relative_to((repo_root / '.local-data').resolve()):
        raise ValueError('external review output must stay under ignored .local-data')
    if output.exists():
        raise ValueError('fresh output directory required')
    nvidia = repo_root / '.local-data/external-frozen-01'
    upstream = nvidia / 'source/train.jsonl'
    if sha(upstream) != UPSTREAM_SHA256:
        raise ValueError('NVIDIA source changed')
    _, consumed = load_prepared(nvidia / 'prepared')
    consumed_groups = {row['context_group_id'] for row in consumed}
    known = [json.loads(line)['text'] for line in (repo_root / 'data/v2/development-01.jsonl').read_text().splitlines()]
    raw = [json.loads(line) for line in upstream.read_text().splitlines()]
    raw_by_id = {r['id']: r for r in raw}
    pairs, rejections = [], []
    for row in raw:
        try:
            pairs.append(extract_pair(row))
        except ValueError as exc:
            rejections.append({'id': row['id'], 'reason': str(exc)})
    # Reconstruct the original connected components BEFORE excluding consumed
    # groups, so a different representative cannot reintroduce a used context.
    representatives, grouping = select_pairs(pairs, known, max_pairs=10000)
    remaining = [p for p in representatives if p['context_group_id'] not in consumed_groups]
    remaining.sort(key=lambda p: text_hash(SEED + str(p['source_row_id'])))
    if len(remaining) < 453:
        raise ValueError('insufficient unused NVIDIA contexts; do not pad')
    rows = []
    for index, pair in enumerate(remaining[:453]):
        source = raw_by_id[pair['source_row_id']]
        messages = source['responses_create_params']['input']
        if any(m['role'] not in ('system', 'user') or not isinstance(m['content'], str) for m in messages):
            raise ValueError('unsupported upstream authorized task format')
        task = '\n\n'.join(m['role'].upper() + ': ' + m['content'] for m in messages)
        for label, condition in [(0, 'clean')] + ([(1, 'injected')] if index < 228 else []):
            rows.append(Candidate(id=f'nvidia-{pair["source_row_id"]}-{condition}', trusted_task=task,
                task_origin='Pinned upstream responses_create_params.input system/user messages',
                untrusted_text=pair[condition], source_origin=REPO, source_revision=REVISION,
                source_url=f'https://huggingface.co/datasets/{REPO}/tree/{REVISION}', source_license='CC-BY-4.0',
                source_row_id=str(pair['source_row_id']), source_context_id=pair['context_group_id'],
                pair_id='nvidia-' + str(pair['source_row_id']), attack_family=pair['attack_category'] if label else None,
                domain=pair['domain'], label=label, label_origin='upstream-annotation' if label else 'span-deletion-control',
                native_role='tool', transformation='Exact environment string at ' + json.dumps(pair['environment_path']) +
                ('; remove unique annotated injection span and trim' if not label else '; no text modification')))
    llmail, notinject = root / 'llmail', root / 'notinject'
    pinned_source(llmail, LLMAIL, LLMAIL_REVISION)
    pinned_source(notinject, NOTINJECT, NOTINJECT_REVISION)
    system = json.loads((llmail / 'data/system_prompt.json').read_text())['email_client']
    scenarios = json.loads((llmail / 'data/scenarios.json').read_text())
    prefix = json.loads((llmail / 'prefix-policy.json').read_text())
    raw_lines = (llmail / 'data/raw_submissions_phase2.prefix.jsonl').read_bytes()
    if prefix['revision'] != LLMAIL_REVISION or len(raw_lines) != prefix['bytes_saved'] or len(raw_lines) > 8388608:
        raise ValueError('LLMail bounded-prefix inventory differs')
    annotations = json.loads((llmail / 'data/labelled_unique_submissions_phase2.json').read_text())
    teams, seen = defaultdict(list), set()
    for line in raw_lines.splitlines():
        item = json.loads(line)
        text = 'Subject of the email: ' + item['subject'] + '.   Body: ' + item['body']
        # Failure to compromise a target is NEVER used as a benign label.
        if normalize(text) in seen or annotations.get(text, {}).get('attack_attempt') != 'True':
            continue
        if not item['scenario'].startswith(('level1', 'level2')):
            raise ValueError('unmapped native LLMail scenario')
        seen.add(normalize(text))
        teams[item['team_id']].append((text, item))
    for items in teams.values():
        items.sort(key=lambda item: text_hash(SEED + item[0]))
    selected = []
    while len(selected) < 128 and any(teams.values()):
        for team in sorted(teams):
            if teams[team] and len(selected) < 128:
                selected.append(teams[team].pop(0))
    if len(selected) != 128:
        raise ValueError('insufficient annotated human attacks in bounded prefix')
    for text, item in selected:
        scenario = 'scenario_' + item['scenario'][5]
        rows.append(Candidate(id='llmail-' + item['RowKey'], trusted_task=system + '\nUSER: ' + scenarios[scenario]['user_query'],
            task_origin='Pinned native email-client system prompt and scenario user query; projected to one email',
            untrusted_text=text, source_origin=LLMAIL, source_revision=LLMAIL_REVISION,
            source_url=f'https://huggingface.co/datasets/{LLMAIL}/tree/{LLMAIL_REVISION}', source_license='MIT',
            source_row_id=item['RowKey'], source_context_id=scenario, author_id=item['team_id'],
            attack_family='unauthorized-email-send', domain='email', label=1, label_origin='upstream-annotation', native_role='email',
            transformation='Reconstruct exact annotated Subject/Body string; match positive attack_attempt; preserve raw team/scenario; single-email projection'))
    benign = json.loads((llmail / 'data/emails_for_fp_tests.json').read_text())
    if len(benign) != 203:
        raise ValueError('unexpected LLMail benign source count')
    for index, text in enumerate(benign):
        rows.append(Candidate(id=f'llmail-benign-{index}', trusted_task=system + '\nUSER: ' + scenarios['scenario_1']['user_query'],
            task_origin='Curator assignment of upstream summarize-emails query to one upstream FP-test email; review needed',
            untrusted_text=text, source_origin=LLMAIL, source_revision=LLMAIL_REVISION,
            source_url=f'https://huggingface.co/datasets/{LLMAIL}/tree/{LLMAIL_REVISION}', source_license='MIT',
            source_row_id=f'emails_for_fp_tests:{index}', source_context_id='benign-' + text_hash(normalize(text)),
            domain='email', label=0, label_origin='upstream-annotation', native_role='email',
            transformation='Unmodified FP-test email; explicit task assignment is an adaptation'))
    import pyarrow.parquet as pq
    for subset in ('one', 'two', 'three'):
        prompts = pq.read_table(notinject / f'data/NotInject_{subset}-00000-of-00001.parquet').to_pylist()
        if len(prompts) != 113:
            raise ValueError('unexpected NotInject diagnostic count')
        for index, item in enumerate(prompts):
            rows.append(Candidate(id=f'notinject-{subset}-{index}', trusted_task=None,
                task_origin='Native benign user prompt; no tool-result task invented', untrusted_text=item['prompt'],
                source_origin=NOTINJECT, source_revision=NOTINJECT_REVISION,
                source_url=f'https://huggingface.co/datasets/{NOTINJECT}/tree/{NOTINJECT_REVISION}', source_license='MIT',
                source_row_id=f'{subset}:{index}', source_context_id=text_hash(normalize(item['prompt'])),
                domain=item['category'], label=0, label_origin='upstream-annotation',
                label_scope='diagnostic-prompt', split_role='diagnostic', native_role='user-prompt',
                transformation='Unmodified prompt; preserve diagnostic scope, not representative calibration'))
    if len(rows) != 1351:
        raise ValueError('candidate accounting differs')
    policy = SplitPolicy(experiment='in-distribution', group_by_author=True, group_by_generation_batch=False)
    result = audit(rows, [], policy)
    output.mkdir(parents=True)
    (output / 'candidates.jsonl').write_text(''.join(json.dumps(r.model_dump(), ensure_ascii=False) + '\n' for r in rows))
    (output / 'review-queue.jsonl').write_text(''.join(json.dumps({'id': r.id, 'candidate_sha256': r.fingerprint,
        'proposed_label': r.label, 'status': 'unreviewed', 'reviewer': None}) + '\n' for r in rows))
    (output / 'reviews.jsonl').write_text('')
    write(output / 'split-policy.json', policy.model_dump())
    write(output / 'audit.json', result)
    source_paths = [p for p in root.rglob('*') if p.is_file()] + [upstream, nvidia / 'source/README.md',
                    nvidia / 'prepared/policy.json', nvidia / 'prepared/corpus.jsonl', repo_root / 'data/v2/development-01.jsonl']
    write(output / 'source-inventory.json', {'files': {str(p.relative_to(repo_root)): sha(p) for p in sorted(source_paths)},
        'source_revisions': {REPO: REVISION, LLMAIL: LLMAIL_REVISION, NOTINJECT: NOTINJECT_REVISION},
        'nvidia_consumed_context_groups_excluded': len(consumed_groups), 'nvidia_remaining_groups': len(remaining),
        'nvidia_extraction_rejections': rejections, 'nvidia_group_policy': grouping['near_duplicate_policy'],
        'llmail_sampling': prefix, 'human_label_review': False, 'training_performed': False,
        'limitations': ['Two eligible tool/email source streams; three required before pilot readiness.',
            'All task documents need label, task, license and lineage review and group-wise split assignment.',
            'LLMail selection uses a bounded contiguous prefix and five available teams; not a representative population.',
            'NVIDIA controls are synthetic span deletions. NotInject is a separate prompt diagnostic.',
            'Template lineage and generation batches are not provided; do not infer independence from unknown fields.']})
    (output / 'ATTRIBUTION.md').write_text('# Candidate source attribution\n\n' +
        f'- NVIDIA Corporation, {REPO} at {REVISION}, CC BY 4.0. Changes: environment-field extraction, exact attack-span removal for controls, group selection.\n' +
        f'- Microsoft and LLMail-Inject authors, {LLMAIL} at {LLMAIL_REVISION}, MIT. Changes: bounded selection, reconstructed Subject/Body strings and single-email task projection.\n' +
        f'- NotInject/InjecGuard authors, {NOTINJECT} at {NOTINJECT_REVISION}, MIT. Unmodified prompts retained as diagnostics.\n\n' +
        'Pinned upstream cards and metadata are retained in ../sources. This queue has no human-approved labels.\n')
    print(json.dumps({'records': len(rows), 'task_candidates': 1012, 'diagnostics': 339, 'status': result['status']}))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    prepare(args.sources, args.output)
