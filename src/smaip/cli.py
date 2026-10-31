"""Command line for the SMAIP mock stack."""

import argparse

from smaip.eval.harness import eval_main
from smaip.eval.week3 import week3_main
from smaip.eval.week4 import week4_main
from smaip.eval.week5 import week5_main
from smaip.eval.week6 import week6_main
from smaip.eval.week7 import rescore_main, week7_main
from smaip.serving.benchmark import bench_main


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    import logging
    import os

    import uvicorn

    from smaip.serving.app import create_app

    level_name = os.environ.get("SMAIP_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(message)s")
    uvicorn.run(create_app(), host=host, port=port, log_level=level_name.lower())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="smaip")
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve_parser = sub.add_parser("serve", help="run the mock-default API on localhost")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    eval_parser = sub.add_parser("eval", help="run the Week 1 ablation harness")
    eval_parser.add_argument("--output", default="reports/week1_eval.json")
    week3_parser = sub.add_parser("week3", help="run the Week 3 task suite")
    week3_parser.add_argument("--output", default="reports/week3_eval.json")
    week4_parser = sub.add_parser("week4", help="run the Week 4 task suite")
    week4_parser.add_argument("--output", default="reports/week4_eval.json")
    week5_parser = sub.add_parser("week5", help="run the Week 5 attack suite")
    week5_parser.add_argument("--output", default="reports/week5_eval.json")
    week5_parser.add_argument("--traces", default="reports/traces")
    week5_parser.add_argument("--results", default="reports/RESULTS.md")
    week5_parser.add_argument("--failures", default="reports/FAILURES.md")
    week6_parser = sub.add_parser("week6", help="run the Week 6 attack suite")
    week6_parser.add_argument("--output", default="reports/week6_eval.json")
    week6_parser.add_argument("--traces", default="reports/traces")
    week6_parser.add_argument("--results", default="reports/RESULTS.md")
    week6_parser.add_argument("--failures", default="reports/FAILURES.md")
    week7_parser = sub.add_parser(
        "week7",
        help="collect activations, train probes, and remeasure the six ablations",
    )
    week7_parser.add_argument("--model", default=None)
    week7_parser.add_argument("--subset", default=None)
    week7_parser.add_argument("--backend", default=None)
    week7_parser.add_argument("--device", default=None)
    week7_parser.add_argument("--layers", default=None)
    week7_parser.add_argument("--artifacts", default=None)
    week7_parser.add_argument("--activations", default=None)
    week7_parser.add_argument("--results", default="reports/RESULTS_week7.md")
    week7_parser.add_argument("--output", default="reports/week7_eval.json")
    rescore_parser = sub.add_parser("week7-rescore", help="rerun episodes with saved probes; no training")
    rescore_parser.add_argument("--artifacts", default=None)
    rescore_parser.add_argument("--results", default="reports/RESULTS_week7_rescore.md")
    rescore_parser.add_argument("--output", default="reports/week7_rescore.json")
    rescore_parser.add_argument("--subset", choices=["full", "tiny"], default="full")
    rescore_parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default=None)
    contract_parser = sub.add_parser("eval-contract", help="write the V2 BRD comparison contract; no model calls")
    contract_parser.add_argument("--backend", choices=["mock", "hf-local", "vllm-local"], default="mock")
    contract_parser.add_argument("--model", default="smaip-mock")
    contract_parser.add_argument("--output", default="reports/v2/eval_contract.json")
    agent_v2 = sub.add_parser("agent-v2", help="run bounded open-model research in an in-memory workspace")
    agent_v2.add_argument("instruction")
    agent_v2.add_argument("--vendor", required=True)
    agent_v2.add_argument("--recipient", required=True)
    agent_v2.add_argument("--backend", choices=["hf-local", "vllm-local"], default="hf-local")
    agent_v2.add_argument("--variant", choices=["no-defense", "keyword-screen", "least-privilege-only", "gateway-only"], default="least-privilege-only")
    agent_v2.add_argument("--approval-digest", default=None)
    agent_v2.add_argument("--output", default="reports/v2/agent_run.json")
    manifest_parser = sub.add_parser("validate-corpus-v2", help="validate declared source/family/group splits; no model calls")
    manifest_parser.add_argument("path")
    manifest_parser.add_argument("--output", default="reports/v2/manifest_review.json")
    acceptance_parser = sub.add_parser("brd-gate", help="check measured BRD evidence; missing evidence is pending")
    acceptance_parser.add_argument("path")
    acceptance_parser.add_argument("--output", default="reports/v2/acceptance.json")
    bench_parser = sub.add_parser(
        "bench",
        help="compare HF and vLLM when CUDA is present; skip cleanly otherwise",
    )
    bench_parser.add_argument("--output", default="reports/week7_bench.json")
    bench_parser.add_argument("--model", default=None)
    args = parser.parse_args(argv)
    if args.cmd == "serve":
        serve(args.host, args.port)
        return 0
    if args.cmd == "eval":
        return eval_main(args.output)
    if args.cmd == "week3":
        return week3_main(args.output)
    if args.cmd == "week4":
        return week4_main(args.output)
    if args.cmd == "week5":
        return week5_main(args.output, args.traces, args.results, args.failures)
    if args.cmd == "week6":
        return week6_main(args.output, args.traces, args.results, args.failures)
    if args.cmd == "week7":
        return week7_main(
            model=args.model,
            subset=args.subset or None,
            backend=args.backend,
            device=args.device,
            layers=args.layers,
            artifact_dir=args.artifacts,
            activation_dir=args.activations,
            results=args.results,
            output=args.output,
        )
    if args.cmd == "week7-rescore":
        return rescore_main(artifact_dir=args.artifacts, results=args.results, output=args.output, subset=args.subset, device=args.device)
    if args.cmd == "eval-contract":
        import json
        from pathlib import Path
        from smaip.eval.contract import contract_manifest
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(contract_manifest(backend=args.backend, model_id=args.model), indent=2) + "\n")
        print(f"wrote {output}; contract only, not measured model results")
        return 0
    if args.cmd == "agent-v2":
        import json
        from dataclasses import replace
        from pathlib import Path
        from smaip.agents.open_loop import run_open_task
        from smaip.eval.contract import evaluation_matrix
        from smaip.serving.engines import engine_for_model
        engine = engine_for_model(args.backend)
        config = next(c for c in evaluation_matrix(backend=args.backend, model_id=engine.config.model_id) if c.name == args.variant)
        config = replace(config, max_new_tokens=engine.config.max_new_tokens)
        report = run_open_task(args.instruction, vendor=args.vendor, recipient=args.recipient,
                              config=config, engine=engine, approval_digest=args.approval_digest)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n")
        print(f"{report['status']}; model calls={report['model_calls']}; sandboxed effects only; wrote {output}")
        return 0 if report['status'] in {"done", "approval_required"} else 1
    if args.cmd in {"validate-corpus-v2", "brd-gate"}:
        import json
        from pathlib import Path
        if args.cmd == "validate-corpus-v2":
            from smaip.probes.manifest import load_manifest
            _, report = load_manifest(Path(args.path))
        else:
            from smaip.eval.acceptance import assess
            report = assess(json.loads(Path(args.path).read_text()))
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 0 if args.cmd == "validate-corpus-v2" or report["passed"] else 1
    if args.cmd == "bench":
        return bench_main(["--output", args.output] + (["--model", args.model] if args.model else []))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
