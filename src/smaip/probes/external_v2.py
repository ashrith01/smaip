"""Pinned external validation of frozen development probes; no fitting.

The NVIDIA source is synthetic indirect-injection data, not an independent
population sample. Clean controls are derived by exact annotated-span removal.
External text is always data: this module executes no supplied tools or prompts.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

from smaip.probes.low_fpr import operating_point
from smaip.probes.pipeline_v2 import digest, fresh, source_hashes, write_json
from smaip.probes.protocol import FeatureExtractor, FeatureProtocol, ProtocolProbe, encode_tool_content


REPO = 'nvidia/Nemotron-RL-Agentic-Indirect-Prompt-Injection-v1'
REVISION = 'd738d4f361cc38bb4d7a42b9066776dade5332f5'
UPSTREAM_SHA256 = '3329da17564a7eb287e2730fc7d6956e1f4fe51e8950ac4f110b3c37e78cf3b9'
MODEL_HASHES = {'linear.json': '032e34f2bc8aec7b50a76ac99575eb5e2d3b6f7b089cf8dea5a09c834958e719',
                'activation.json': '5dbabd006e261dfe5c87e9be3abb99b58271aa5e63f3d14dbd90afdb97dca38b'}
SEED = 'smaip-external-frozen-01-before-scoring'
RESIDUAL = re.compile(r'priority message|hi assistant|before (?:completing|finishing) the task above', re.I)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()


def normalize(text):
    return re.sub(r'\s+', ' ', text.casefold()).strip()


def shingles(text):
    tokens = re.findall(r'\w+', re.sub(r'\d+', ' NUMBER ', text.casefold()))
    return {' '.join(tokens[i:i + 4]) for i in range(max(1, len(tokens) - 3))}


def similar(a, b):
    if not a or not b or min(len(a), len(b)) < 0.8 * max(len(a), len(b)):
        return False
    intersection = len(a & b)
    return bool(intersection and intersection / len(a | b) >= 0.8)


def strings(value, path=()):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from strings(item, path + (str(key),))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from strings(item, path + (str(index),))
    elif isinstance(value, str):
        yield path, value


def extract_pair(row):
    injection = row['injection']['injection_text']
    require(isinstance(injection, str) and injection.strip(), 'empty attack span')
    require(row['attack_category'] == row['injection']['category']
            and row['injection_vector'] == row['injection']['vector'], 'inconsistent source metadata')
    matches = [(path, text) for path, text in strings(row['environment']) if injection in text]
    require(len(matches) == 1, 'ambiguous or missing annotated span')
    path, poisoned = matches[0]
    require(poisoned.count(injection) == 1, 'repeated annotated span')
    # Semantic vector names such as case_summary can map to a leaf named summary.
    # The unique literal span determines the field; the exact path is recorded.
    clean = poisoned.replace(injection, '', 1).strip()
    require(len(clean.split()) >= 8, 'insufficient clean context')
    require(not RESIDUAL.search(clean), 'residual attack wrapper')
    return {'source_row_id': row['id'], 'domain': row['domain'],
            'attack_category': row['attack_category'], 'injection_vector': row['injection_vector'],
            'environment_path': list(path), 'injection_sha256': text_hash(injection),
            'clean': clean, 'injected': poisoned}


def select_pairs(candidates, known_texts, *, max_pairs=400):
    require(type(max_pairs) is int and max_pairs > 0, 'max_pairs must be positive')
    known = {normalize(text) for text in known_texts}
    known_shingles = [shingles(text) for text in known_texts]
    eligible, excluded = [], []
    for pair in candidates:
        texts = (pair['clean'], pair['injected'])
        if any(normalize(text) in known or any(similar(shingles(text), reference) for reference in known_shingles)
               for text in texts):
            excluded.append({'source_row_id': pair['source_row_id'], 'reason': 'known development material overlap'})
        else:
            eligible.append(pair)
    # One representative per connected component of similar clean contexts.
    sets = [shingles(pair['clean']) for pair in eligible]
    parent = list(range(len(eligible)))
    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index
    for i, a in enumerate(sets):
        for j in range(i):
            if normalize(eligible[i]['clean']) == normalize(eligible[j]['clean']) or similar(a, sets[j]):
                parent[find(i)] = find(j)
    groups = {}
    rank = lambda pair: text_hash(SEED + ':' + str(pair['source_row_id']))
    for i, pair in enumerate(eligible):
        groups.setdefault(find(i), []).append(pair)
    representatives = []
    for group in groups.values():
        representative = min(group, key=rank)
        representatives.append({**representative,
                                'context_group_id': text_hash('\n'.join(sorted(normalize(p['clean']) for p in group))),
                                'context_group_members': sorted(p['source_row_id'] for p in group)})
    chosen = sorted(representatives, key=rank)[:max_pairs]
    return chosen, {'candidates_after_decontamination': len(eligible), 'context_groups': len(groups),
                    'near_duplicate_policy': 'connected components; digit-normalized four-word shingle Jaccard >= 0.8; clean contexts',
                    'selected_pairs': len(chosen), 'max_pairs': max_pairs, 'selection_seed': SEED,
                    'selection_policy': 'one hash-selected representative per clean-context group, then fixed hash order; no probe scores',
                    'decontamination_exclusions': excluded}


def prepare(upstream, card, models, exclude, output, *, max_pairs=400):
    require(digest(upstream) == UPSTREAM_SHA256, 'Unexpected pinned NVIDIA source bytes')
    card_text = Path(card).read_text()
    require('license: cc-by-4.0' in card_text and 'NVIDIA Corporation' in card_text, 'Expected upstream license declaration')
    for name, expected in MODEL_HASHES.items():
        require(digest(Path(models) / name) == expected, 'Frozen model differs: ' + name)
    known_records = [json.loads(line) for line in Path(exclude).read_text().splitlines() if line.strip()]
    require(len(known_records) == 36, 'Expected the known development corpus')
    known_texts = [row['text'] for row in known_records]
    candidates, rejected = [], []
    source_rows = [json.loads(line) for line in Path(upstream).read_text().splitlines() if line.strip()]
    require(len({row['id'] for row in source_rows}) == len(source_rows) == 1272, 'Unexpected source row identities/count')
    for row in source_rows:
        try:
            candidates.append(extract_pair(row))
        except ValueError as exc:
            rejected.append({'source_row_id': row['id'], 'reason': str(exc)})
    selected, selection = select_pairs(candidates, known_texts, max_pairs=max_pairs)
    output = fresh(output)
    documents = []
    for pair in selected:
        for label, condition in ((0, 'clean'), (1, 'injected')):
            text = pair[condition]
            documents.append({'id': f'nvidia-{pair["source_row_id"]}-{condition}', 'text': text, 'label': label,
                              'pair_id': f'nvidia-{pair["source_row_id"]}',
                              **{key: value for key, value in pair.items() if key not in {'clean', 'injected'}},
                              'text_sha256': text_hash(text)})
    (output / 'corpus.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in documents))
    (output / 'UPSTREAM_README.md').write_bytes(Path(card).read_bytes())
    attribution = (f'Source: NVIDIA Corporation, {REPO}, revision {REVISION}.\n'
                   f'https://huggingface.co/datasets/{REPO}/tree/{REVISION}\n'
                   'License: Creative Commons Attribution 4.0 International (CC BY 4.0).\n'
                   'https://creativecommons.org/licenses/by/4.0/\n'
                   'Changes by SMAIP: extract the unique environment string containing the annotated attack; '
                   'derive a clean control by removing that exact span and trimming outer whitespace; '
                   'exclude ambiguous/short/residual-wrapper cases and known development overlap; '
                   'deduplicate clean contexts and select by a fixed hash order.\n'
                   'The source is synthetic. Clean controls are derived labels, not upstream human annotations.\n')
    (output / 'ATTRIBUTION.txt').write_text(attribution)
    policy = {'kind': 'frozen-external-probe-validation-corpus', 'scope': 'external-pilot',
              'repo_id': REPO, 'revision': REVISION, 'upstream_sha256': UPSTREAM_SHA256,
              'source_url': f'https://huggingface.co/datasets/{REPO}/tree/{REVISION}',
              'license': 'CC-BY-4.0', 'license_review': 'Upstream pinned card explicitly declares CC BY 4.0, fully synthetic generation with no seed data, NVIDIA ownership.',
              'label_policy': 'Positive: complete environment field containing the unique annotated attack. Negative: the same field with the exact attack span removed and no known residual wrapper.',
              'human_label_review': False, 'population_independence_verified': False,
              'agent_attack_success_measured': False, 'training_or_calibration_performed': False,
              'frozen_models_sha256': MODEL_HASHES, 'known_development_corpus_sha256': digest(exclude),
              'source_rows': len(source_rows), 'extraction_accepted': len(candidates),
              'extraction_rejections': rejected, 'selection': selection,
              'domains': dict(Counter(pair['domain'] for pair in selected)),
              'attack_categories': dict(Counter(pair['attack_category'] for pair in selected)),
              'files_sha256': {name: digest(output / name) for name in ('corpus.jsonl', 'UPSTREAM_README.md', 'ATTRIBUTION.txt')},
              'limitations': ['Synthetic source optimized against another defender; not an independently sampled deployment population.',
                             'Shared attack wrappers and generated style remain possible shortcuts despite context deduplication.',
                             'Clean labels derive from span removal; residual semantic redirection is not ruled out by the structural checks.',
                             'Source row selection is score-independent. Oversized pairs are excluded together on GPU under the frozen feature budget.']}
    write_json(output / 'policy.json', policy)
    return policy


def load_prepared(corpus):
    corpus = Path(corpus)
    policy = json.loads((corpus / 'policy.json').read_text())
    require(policy['kind'] == 'frozen-external-probe-validation-corpus' and policy['scope'] == 'external-pilot', 'Unexpected external policy')
    require(policy['repo_id'] == REPO and policy['revision'] == REVISION and policy['upstream_sha256'] == UPSTREAM_SHA256,
            'Unexpected external source')
    require(policy['frozen_models_sha256'] == MODEL_HASHES and policy['training_or_calibration_performed'] is False,
            'Unexpected frozen-model policy')
    require(set(policy['files_sha256']) == {'corpus.jsonl', 'UPSTREAM_README.md', 'ATTRIBUTION.txt'}, 'Incomplete corpus inventory')
    for name, expected in policy['files_sha256'].items():
        require(digest(corpus / name) == expected, 'Prepared corpus differs: ' + name)
    rows = [json.loads(line) for line in (corpus / 'corpus.jsonl').read_text().splitlines() if line.strip()]
    require(len(rows) == policy['selection']['selected_pairs'] * 2 and len({row['id'] for row in rows}) == len(rows), 'Invalid external row identities')
    pairs = {}
    for row in rows:
        require(type(row['label']) is int and row['label'] in (0, 1) and text_hash(row['text']) == row['text_sha256'], 'Invalid external document')
        pairs.setdefault(row['pair_id'], []).append(row)
    groups = set()
    for pair in pairs.values():
        require(len(pair) == 2 and {r['label'] for r in pair} == {0, 1}, 'Incomplete clean/injected pair')
        require(pair[0]['context_group_id'] == pair[1]['context_group_id'], 'Pair context differs')
        require(pair[0]['context_group_id'] not in groups, 'Repeated clean context group')
        groups.add(pair[0]['context_group_id'])
    return policy, rows


def evaluate(corpus, models, output):
    policy, rows = load_prepared(corpus)
    models = Path(models)
    payloads = {}
    for name, expected in MODEL_HASHES.items():
        require(digest(models / name) == expected, 'Frozen model changed: ' + name)
        payloads[name] = json.loads((models / name).read_text())
    model = payloads['linear.json']
    protocol = FeatureProtocol(**model['feature_protocol'])
    extractor = FeatureExtractor(protocol, [model['layer']])
    probes = {name: ProtocolProbe(payload, extractor) for name, payload in payloads.items()}
    output = fresh(output)
    # Load the pinned cache once. Both probes then reuse each document's forward.
    extractor._load()
    accepted, rejected = [], []
    for i in range(0, len(rows), 2):
        pair = rows[i:i + 2]
        require(pair[0]['pair_id'] == pair[1]['pair_id'], 'External pairs must be adjacent')
        try:
            for row in pair:
                encode_tool_content(extractor.tokenizer, row['text'], protocol)
        except ValueError as exc:
            if 'truncation is forbidden' not in str(exc):
                raise
            rejected.append({'pair_id': pair[0]['pair_id'], 'reason': 'feature token budget exceeded; entire pair excluded'})
        else:
            accepted.extend(pair)
    require(accepted, 'No external pairs fit the frozen feature budget')
    predictions = []
    with (output / 'vectors.jsonl').open('w') as stream:
        for index, row in enumerate(accepted, 1):
            features = extractor.extract(row['text'])
            for pool in ('last', 'mean'):
                vector = features[pool][str(model['layer'])]
                require(len(vector) == model['dim'] and all(math.isfinite(x) for x in vector), 'Invalid external vector')
            stream.write(json.dumps({'id': row['id'], 'text_sha256': row['text_sha256'], 'features': features}, allow_nan=False) + '\n')
            for name, probe in probes.items():
                score = probe.score(row['text'])
                predictions.append({'probe': name, 'id': row['id'], 'pair_id': row['pair_id'],
                                    'domain': row['domain'], 'attack_category': row['attack_category'],
                                    'label': row['label'], 'score': score, 'threshold': probe.threshold,
                                    'predicted': int(score >= probe.threshold)})
            print(f'Scored {index}/{len(accepted)} external documents', flush=True)
    write_json(output / 'predictions.json', predictions)
    metrics = {}
    for name, probe in probes.items():
        selected = [row for row in predictions if row['probe'] == name]
        block = operating_point([r['score'] for r in selected], [r['label'] for r in selected], probe.threshold)
        block['zero_fp_one_sided_95_upper_if_independent'] = 1 - 0.05 ** (1 / block['negatives']) if block['fp'] == 0 else None
        block['population_fpr_claim_supported'] = False
        metrics[name] = block
    import torch
    from importlib.metadata import version
    result = {'status': 'completed', 'kind': 'frozen-external-probe-validation', 'scope': 'external-pilot',
              'policy_sha256': digest(Path(corpus) / 'policy.json'), 'frozen_models_sha256': MODEL_HASHES,
              'feature_protocol': protocol.as_dict(), 'protocol_fingerprint': protocol.fingerprint,
              'layer': model['layer'], 'dim': model['dim'], 'documents': len(accepted),
              'pairs': len(accepted) // 2, 'token_budget_excluded_pairs': rejected, 'metrics': metrics,
              'source_sha256': source_hashes(), 'training_performed': False, 'thresholds_changed': False,
              'agent_attack_success_measured': False, 'population_independence_verified': False,
              'runtime': {'torch': torch.__version__, 'cuda': torch.version.cuda,
                          'gpu': torch.cuda.get_device_name(0), 'transformers': version('transformers')},
              'note': 'Held out from probe fitting/calibration, but one synthetic upstream source with derived clean controls. Detector scores only; no agent ASR or final acceptance claim.'}
    write_json(output / 'evaluation.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('upstream', type=Path)
    prep.add_argument('--card', type=Path, required=True)
    prep.add_argument('--exclude', type=Path, required=True)
    run = sub.add_parser('evaluate')
    run.add_argument('corpus', type=Path)
    for command in (prep, run):
        command.add_argument('--models', type=Path, required=True)
        command.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.upstream, args.card, args.models, args.exclude, args.output) if args.command == 'prepare' else evaluate(args.corpus, args.models, args.output)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
