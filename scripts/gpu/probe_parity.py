"""Compare saved-probe inference with batch-1/batch-4 feature collection.

This diagnostic never fits weights or thresholds. GPU is the normal path;
--backend mock is only for local pipeline testing with mock probe artifacts.
"""
import argparse
from contextlib import contextmanager
import gzip
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import time

from smaip.probes import activations
from smaip.probes.dataset import prepare_records
from smaip.probes.logistic import metric_block, predict_proba, standardize
from smaip.probes.trained import TrainedProbe


KINDS = ("linear", "activation")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@contextmanager
def setting(name, value):
    old = os.environ.get(name)
    os.environ[name] = str(value)
    try:
        yield
    finally:
        if old is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = old


def compare(reference, candidate, thresholds, tolerance):
    """Report all operating-point changes even if numeric differences are tiny."""
    assert set(reference) == set(candidate), "condition record sets differ"
    result = {kind: {"max_abs_score_delta": 0.0, "score_tolerance_exceeded": [], "decision_flips": []} for kind in KINDS}
    for record_id in sorted(reference):
        for kind in KINDS:
            a, b = reference[record_id][kind], candidate[record_id][kind]
            assert math.isfinite(a) and math.isfinite(b) and 0 <= a <= 1 and 0 <= b <= 1
            delta = abs(a - b)
            result[kind]["max_abs_score_delta"] = max(result[kind]["max_abs_score_delta"], delta)
            if delta > tolerance:
                result[kind]["score_tolerance_exceeded"].append(record_id)
            if (a >= thresholds[kind]) != (b >= thresholds[kind]):
                result[kind]["decision_flips"].append({"id": record_id, "reference": a, "candidate": b, "threshold": thresholds[kind]})
    return result


def runtime_info():
    result = {"python": platform.python_version()}
    for name in ("torch", "transformers", "huggingface-hub", "langgraph", "smaip"):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = None
    return result


def token_details(model_id, device, records, batch_size):
    model, tokenizer = activations._load_hf(model_id, device, "float16")
    details = {}
    for start in range(0, len(records), batch_size):
        chunk = records[start:start + batch_size]
        rendered = [activations._render(tokenizer, record.text) for record in chunk]
        encoded = tokenizer(rendered, truncation=True, padding=True, max_length=activations._max_length())
        for index, record in enumerate(chunk):
            ids, mask = encoded['input_ids'][index], encoded['attention_mask'][index]
            unpadded = [token for token, keep in zip(ids, mask) if keep]
            full_length = len(tokenizer(rendered[index], truncation=False)['input_ids'])
            details[record.id] = {"input_ids": ids, "attention_mask": mask, "nonpadding_input_ids": unpadded,
                                  "rendered_sha256": hashlib.sha256(rendered[index].encode()).hexdigest(),
                                  "untruncated_tokens": full_length, "was_truncated": full_length > len(unpadded)}
    metadata = {
        "model_config": model.config.to_dict(),
        "model_dtype": str(model.dtype),
        "attention_implementation": getattr(model.config, '_attn_implementation', None),
        "padding_side": tokenizer.padding_side,
        "pad_token_id": tokenizer.pad_token_id,
        "eos_token_id": tokenizer.eos_token_id,
        "chat_template": tokenizer.chat_template,
    }
    return details, metadata


def diagnose(*, artifacts, output, backend="hf", device="cuda", subset="full", repeats=2, score_tolerance=0.001):
    if repeats < 2 or score_tolerance < 0 or not math.isfinite(score_tolerance):
        raise ValueError("use at least two repeats and a finite nonnegative score tolerance")
    if backend == 'hf' and device != 'cuda':
        raise ValueError("use CUDA for parity with the original fp16 GPU run")
    artifacts = Path(artifacts)
    paths = {kind: artifacts / (kind + '.json') for kind in KINDS}
    payloads = {kind: json.loads(path.read_text()) for kind, path in paths.items()}
    before = {kind: sha(path) for kind, path in paths.items()}
    assert all(payloads[k]['backend'] == backend for k in KINDS), "artifact backend does not match requested backend"
    assert payloads['linear']['model_id'] == payloads['activation']['model_id']
    if backend == 'hf':
        assert all(payloads[k]['device'] == 'cuda' for k in KINDS), 'expected original CUDA-trained artifacts'
    original_id = payloads['linear']['model_id']
    thresholds = {kind: payloads[kind]['threshold'] for kind in KINDS}
    records = prepare_records(subset)
    layers = sorted({payloads[kind]['layer'] for kind in KINDS})
    snapshot_metadata = {}
    if backend == 'hf':
        # Resolve ONLY the already-cached snapshot, then load by immutable local
        # snapshot path for all conditions. Nothing downloads or updates a ref.
        from huggingface_hub import snapshot_download
        snapshot = Path(snapshot_download(original_id, local_files_only=True))
        model_id = str(snapshot)
        snapshot_metadata = {"path": str(snapshot), "commit_directory": snapshot.name,
                             "config_tokenizer_hashes": {p.name: sha(p) for p in snapshot.iterdir()
                                                          if p.is_file() and (p.name.endswith('.json') or p.name in ('merges.txt', 'vocab.txt'))}}
    else:
        model_id = original_id
        device = 'cpu'
    # Only in-memory copies reference the pinned snapshot. On-disk probes stay immutable.
    probes = {kind: TrainedProbe({**payload, "model_id": model_id}) for kind, payload in payloads.items()}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = [{"id": record.id, "label": record.label, "split": record.split,
                 "text_sha256": hashlib.sha256(record.text.encode()).hexdigest()} for record in records]
    metadata = {"backend": backend, "model_id": original_id, "device": device,
                "subset": subset, "repeats": repeats, "max_length": activations._max_length(),
                "score_tolerance": score_tolerance,
                "acceptance_rule": "Exact nonpadding token/render match; no decision flips; all score differences <= tolerance across serving, batch sizes and repeats. Tolerance is an engineering diagnostic, not a guarantee of detector quality.",
                "probe_sha256": before, "thresholds": thresholds, "runtime": runtime_info(),
                "snapshot": snapshot_metadata, "records": manifest,
                "script_sha256": sha(__file__),
                "source_sha256": {str(p.relative_to(Path(activations.__file__).parents[1])): sha(p)
                                  for p in Path(activations.__file__).parents[1].rglob('*.py')}}
    if backend == 'hf':
        import torch
        metadata['gpu'] = [{"name": torch.cuda.get_device_name(i), "capability": torch.cuda.get_device_capability(i),
                            "total_memory": torch.cuda.get_device_properties(i).total_memory}
                           for i in range(torch.cuda.device_count())]
        metadata['torch_cuda_version'] = torch.version.cuda
        metadata['deterministic_algorithms_enabled'] = torch.are_deterministic_algorithms_enabled()
        metadata['allow_tf32'] = torch.backends.cuda.matmul.allow_tf32
        single_tokens, model_meta = token_details(model_id, device, records, 1)
        batch_tokens, _ = token_details(model_id, device, records, 4)
        metadata['feature_configuration'] = model_meta
        metadata['token_mismatches'] = [key for key in single_tokens
                                       if (single_tokens[key]['nonpadding_input_ids'], single_tokens[key]['rendered_sha256']) !=
                                       (batch_tokens[key]['nonpadding_input_ids'], batch_tokens[key]['rendered_sha256'])]
        (output / 'tokens.json').write_text(json.dumps({'batch1': single_tokens, 'batch4': batch_tokens}, indent=2) + '\n')
    else:
        metadata['token_mismatches'] = []
        metadata['note'] = 'Mock pipeline smoke only; no Qwen or GPU was used.'
    conditions = {}
    feature_reference = {}
    vector_deltas = {}
    with gzip.open(output / 'vectors.jsonl.gz', 'wt', encoding='utf-8') as vector_file:
        with setting('SMAIP_PROBE_DEVICE', device):
            for repeat in range(repeats):
                for mode in ('serving', 'batch1', 'batch4'):
                    name = f'{mode}_repeat{repeat + 1}'
                    print(f'Running {name}: {len(records)} records, selected layers {layers}', flush=True)
                    activations.clear_pool_cache()
                    for probe in probes.values():
                        probe.clear_score_cache()
                    started = time.perf_counter()
                    scores = {}
                    if mode == 'serving':
                        for record in records:
                            scores[record.id] = {kind: probes[kind].score(record.text) for kind in KINDS}
                            vectors = {kind: activations.embed_text(record.text, model_id=model_id, layer=payloads[kind]['layer'],
                                                                    pooling=payloads[kind]['pooling'], backend=backend,
                                                                    device=device, dtype_name=probes[kind].embedding_dtype()) for kind in KINDS}
                            _save_vectors(vector_file, name, record.id, vectors, feature_reference, vector_deltas)
                    else:
                        with setting('SMAIP_PROBE_BATCH', 1 if mode == 'batch1' else 4):
                            collected = activations.collect(records, model_id=model_id, backend=backend, device=device, layers=layers)
                        for record in collected:
                            vectors = {kind: record['layers'][payloads[kind]['pooling']][str(payloads[kind]['layer'])] for kind in KINDS}
                            scores[record['id']] = {}
                            for kind in KINDS:
                                payload = payloads[kind]
                                scaled, _, _ = standardize([vectors[kind]], payload['mean'], payload['std'])
                                scores[record['id']][kind] = predict_proba(scaled[0], payload['weights'], payload['bias'])
                            _save_vectors(vector_file, name, record['id'], vectors, feature_reference, vector_deltas)
                    conditions[name] = {"scores": scores, "elapsed_seconds": time.perf_counter() - started}
    reference = conditions['serving_repeat1']['scores']
    comparisons = {name: compare(reference, value['scores'], thresholds, score_tolerance) for name, value in conditions.items()}
    split_metrics = {}
    by_id = {record.id: record for record in records}
    for name, value in conditions.items():
        split_metrics[name] = {}
        for kind in KINDS:
            split_metrics[name][kind] = {}
            for split in ('train', 'val', 'test'):
                ids = [record_id for record_id in value['scores'] if by_id[record_id].split == split]
                split_metrics[name][kind][split] = metric_block([value['scores'][key][kind] for key in ids], [by_id[key].label for key in ids], thresholds[kind])
    prior_comparison = None
    prior_path = Path('reports/week7_rescore.json')
    if backend == 'hf' and prior_path.is_file():
        prior = json.loads(prior_path.read_text())
        assert (prior['model_id'], prior['backend']) == (original_id, backend), 'prior rescore model differs'
        assert all(prior['probe_sha256'][kind + '.json'] == before[kind] for kind in KINDS), 'prior rescore probes differ'
        prior_scores = {row['id']: {kind: row[kind] for kind in KINDS} for row in prior['document_scores']}
        prior_comparison = compare(prior_scores, reference, thresholds, score_tolerance)
        metadata['prior_rescore_sha256'] = sha(prior_path)
        metadata['prior_runtime'] = prior.get('runtime')
    comparisons_to_check = list(comparisons.values()) + ([prior_comparison] if prior_comparison is not None else [])
    needs_review = bool(metadata['token_mismatches']) or any(
        block['decision_flips'] or block['score_tolerance_exceeded']
        for comparison in comparisons_to_check for block in comparison.values())
    assert before == {kind: sha(path) for kind, path in paths.items()}, 'probe file changed during diagnostic'
    report = {"status": 'needs_review' if needs_review else 'parity_screen_passed', "metadata": metadata,
              "conditions": conditions, "comparisons_to_serving_repeat1": comparisons,
              "comparison_of_serving_to_prior_rescore": prior_comparison,
              "max_abs_vector_deltas": vector_deltas, "split_metrics": split_metrics,
              "note": 'Diagnostic only. No fitting or threshold changes. Passing parity does not validate data independence or generalization.'}
    (output / 'parity.json').write_text(json.dumps(report, indent=2) + '\n')
    lines = ['# Saved-probe feature parity diagnostic', '', f"Status: **{report['status']}**. Backend `{backend}`; device `{device}`.", '',
             metadata['acceptance_rule'], '', 'Probe hashes verified unchanged. No retraining or threshold fitting occurred.', '',
             '| Condition | Probe | Max absolute score difference | Decision flips | Scores beyond tolerance |',
             '| --- | --- | ---: | ---: | ---: |']
    for name, comparison in comparisons.items():
        for kind, block in comparison.items():
            lines.append(f"| {name} | {kind} | {block['max_abs_score_delta']:.8f} | {len(block['decision_flips'])} | {len(block['score_tolerance_exceeded'])} |")
    if prior_comparison is not None:
        for kind, block in prior_comparison.items():
            lines.append(f"| Prior rescore vs new serving | {kind} | {block['max_abs_score_delta']:.8f} | {len(block['decision_flips'])} | {len(block['score_tolerance_exceeded'])} |")
    lines += ['', f"Nonpadding token/render mismatches: {len(metadata['token_mismatches'])}.", '', report['note'], '']
    (output / 'RESULTS.md').write_text('\n'.join(lines))
    print(f"Completed: {report['status']}; results in {output}", flush=True)
    return report


def _save_vectors(handle, condition, record_id, vectors, reference, deltas):
    for kind, vector in vectors.items():
        assert vector and all(math.isfinite(value) for value in vector)
        key = (record_id, kind)
        if condition == 'serving_repeat1':
            reference[key] = vector
        assert len(vector) == len(reference[key])
        delta = max(abs(a - b) for a, b in zip(reference[key], vector))
        deltas.setdefault(condition, {}).setdefault(kind, 0.0)
        deltas[condition][kind] = max(deltas[condition][kind], delta)
    handle.write(json.dumps({'condition': condition, 'id': record_id, 'vectors': vectors}) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', default='artifacts/probes')
    parser.add_argument('--output', default='reports/week7-parity')
    parser.add_argument('--backend', choices=['hf', 'mock'], default='hf')
    parser.add_argument('--device', choices=['cuda', 'cpu'], default='cuda')
    parser.add_argument('--subset', choices=['full', 'tiny'], default='full')
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--score-tolerance', type=float, default=0.001)
    args = parser.parse_args()
    with setting('SMAIP_PROBE_MAX_LENGTH', 512):
        diagnose(artifacts=args.artifacts, output=args.output, backend=args.backend, device=args.device,
                 subset=args.subset, repeats=args.repeats, score_tolerance=args.score_tolerance)


if __name__ == '__main__':
    main()
