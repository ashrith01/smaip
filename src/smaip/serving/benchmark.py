"""Hugging Face versus vLLM serving check, plus defense overhead.

The comparison runs only when CUDA is available and vLLM imports. Otherwise
the command writes a skip record and exits 0. It does not download a model
on the skip path. Defense overhead on that path is the phrase-stub stack,
timed per request, so the smoke path still records a number.
"""

import argparse
import json
import time
from pathlib import Path


PROMPTS = (
    "Summarize the harbor desk revenue in one sentence.",
    "List the three labeled counts from the vendor page.",
    "Reply with the single word pong.",
    "What is 31 plus 18? Answer with the number only.",
)
LEVELS = (1, 4, 8)
MAX_NEW_TOKENS = 32


def cuda_available() -> bool:
    try:
        import torch
    except ImportError:
        return False
    return bool(torch.cuda.is_available())


def vllm_available() -> bool:
    try:
        import vllm  # noqa: F401
    except ImportError:
        return False
    return True


def bench_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="smaip bench")
    parser.add_argument("--output", default="reports/week7_bench.json")
    parser.add_argument("--model", default=None)
    args = parser.parse_args(argv)
    payload = run_benchmark(model=args.model)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if payload["skipped"]:
        print(f"bench skipped: {payload['reason']}")
    else:
        print(
            f"bench model={payload['model_id']} levels={len(payload['levels'])} "
            f"defense_overhead_ms={payload['defense_overhead']['mean_ms']:.3f}"
        )
    print(f"wrote {path}")
    return 0


def run_benchmark(model: str | None = None) -> dict:
    from smaip.probes.activations import resolve_model

    model_id = resolve_model(model)
    cuda = cuda_available()
    has_vllm = vllm_available() if cuda else False
    overhead = measure_defense_overhead(use_trained=bool(cuda and has_vllm))
    _release_cached_model()
    if not cuda or not has_vllm:
        reasons = []
        if not cuda:
            reasons.append("CUDA is not available")
        if not has_vllm:
            reasons.append("vLLM is not installed")
        return {
            "skipped": True,
            "reason": "; ".join(reasons),
            "cuda": cuda,
            "vllm": has_vllm,
            "model_id": model_id,
            "levels": [],
            "defense_overhead": overhead,
        }
    hf_by_level = _bench_hf_levels(model_id)
    _release_cached_model()
    vllm_by_level = _bench_vllm_levels(model_id)
    levels = [
        {"concurrency": concurrency, "hf": hf_by_level[concurrency], "vllm": vllm_by_level[concurrency]}
        for concurrency in LEVELS
    ]
    return {
        "skipped": False,
        "reason": "",
        "cuda": True,
        "vllm": True,
        "model_id": model_id,
        "max_new_tokens": MAX_NEW_TOKENS,
        "levels": levels,
        "defense_overhead": overhead,
    }


def measure_defense_overhead(use_trained: bool, repeats: int = 20) -> dict:
    """Milliseconds to screen one request with keyword, linear, and activation probes."""

    from smaip.probes.keyword import KeywordHook
    from smaip.probes.linear import LinearProbe
    from smaip.probes.mock import MockActivationProbe

    if use_trained:
        from smaip.probes.registry import load_activation_defense, load_linear_defense

        linear = load_linear_defense()
        probe = load_activation_defense()
        backend = "trained" if not isinstance(linear, LinearProbe) else "stub"
    else:
        linear = LinearProbe()
        probe = MockActivationProbe()
        backend = "stub"
    keyword = KeywordHook()
    from smaip.probes.activations import clear_pool_cache

    for defense in (linear, probe):
        if hasattr(defense, "preload"):
            defense.preload()
    samples = []
    texts = list(PROMPTS)
    for _ in range(repeats):
        for text in texts:
            # Measure inference misses rather than 76 cache hits out of 80.
            for defense in (linear, probe):
                if hasattr(defense, "clear_score_cache"):
                    defense.clear_score_cache()
            clear_pool_cache()
            started = time.perf_counter()
            keyword.flagged(text)
            linear.flagged(text)
            probe.flagged(text)
            samples.append((time.perf_counter() - started) * 1000.0)
    return {
        "backend": backend,
        "cache_policy": "text caches cleared per request; model preloaded",
        "requests": len(samples),
        "mean_ms": sum(samples) / len(samples),
        "p50_ms": _percentile(samples, 0.50),
        "p95_ms": _percentile(samples, 0.95),
    }


def _bench_hf_levels(model_id: str) -> dict[int, dict]:
    """Load Hugging Face once, then time every concurrency level."""

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    from smaip.probes.activations import _from_pretrained

    model = _from_pretrained(
        AutoModelForCausalLM,
        model_id,
        torch.float16,
        low_cpu_mem_usage=True,
    )
    model.to("cuda")
    model.eval()
    try:
        return {level: _hf_level(model, tokenizer, _batch(level)) for level in LEVELS}
    finally:
        del model
        torch.cuda.empty_cache()


def _hf_level(model, tokenizer, batch: list[str]) -> dict:
    import torch

    encoded = tokenizer(batch, return_tensors="pt", padding=True, truncation=True, max_length=512)
    encoded = {key: value.to("cuda") for key, value in encoded.items()}
    with torch.no_grad():
        started = time.perf_counter()
        model.generate(**encoded, max_new_tokens=1, do_sample=False, pad_token_id=tokenizer.eos_token_id)
        torch.cuda.synchronize()
        ttft = time.perf_counter() - started
        started = time.perf_counter()
        output = model.generate(
            **encoded,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
        torch.cuda.synchronize()
        latency = time.perf_counter() - started
    prompt_width = int(encoded["input_ids"].shape[-1])
    new_tokens = max(int(output.shape[-1] - prompt_width) * len(batch), 0)
    return {
        "schedule": "padded-batch",
        "requests": len(batch),
        "output_tokens": new_tokens,
        "tokens_per_s": new_tokens / latency if latency else 0.0,
        "ttft_ms": ttft * 1000.0,
        "latency_p50_ms": latency * 1000.0,
        "latency_p95_ms": latency * 1000.0,
    }


def _bench_vllm_levels(model_id: str) -> dict[int, dict]:
    """Load vLLM once, then time every concurrency level."""

    from vllm import LLM

    engine = LLM(model=model_id, trust_remote_code=False)
    return {level: _vllm_level(engine, _batch(level)) for level in LEVELS}


def _vllm_level(engine, batch: list[str]) -> dict:
    from vllm import SamplingParams

    params = SamplingParams(max_tokens=MAX_NEW_TOKENS, temperature=0.0)
    started = time.perf_counter()
    outputs = engine.generate(batch, params)
    wall = time.perf_counter() - started
    latencies: list[float] = []
    ttfts: list[float] = []
    tokens = 0
    for item in outputs:
        tokens += len(item.outputs[0].token_ids)
        metrics = getattr(item, "metrics", None)
        arrival = getattr(metrics, "arrival_time", None) if metrics is not None else None
        first = getattr(metrics, "first_token_time", None) if metrics is not None else None
        finished = getattr(metrics, "finished_time", None) if metrics is not None else None
        if arrival is not None and finished is not None:
            latencies.append((finished - arrival) * 1000.0)
        if arrival is not None and first is not None:
            ttfts.append((first - arrival) * 1000.0)
    if not latencies:
        each = (wall / len(batch)) * 1000.0 if batch else 0.0
        latencies = [each for _ in batch]
    return {
        "schedule": "continuous-batch",
        "requests": len(batch),
        "output_tokens": tokens,
        "tokens_per_s": tokens / wall if wall else 0.0,
        "ttft_p50_ms": _percentile(ttfts, 0.50) if ttfts else None,
        "ttft_p95_ms": _percentile(ttfts, 0.95) if ttfts else None,
        "latency_p50_ms": _percentile(latencies, 0.50),
        "latency_p95_ms": _percentile(latencies, 0.95),
        "wall_s": wall,
    }


def _release_cached_model() -> None:
    """Drop a probe-held model before the serving benchmark allocates its own."""

    from smaip.probes.activations import release_cached_model

    release_cached_model()


def _batch(concurrency: int) -> list[str]:
    prompts = list(PROMPTS)
    while len(prompts) < concurrency:
        prompts.extend(PROMPTS)
    return prompts[:concurrency]


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * fraction
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight
