"""Command line for the SMAIP mock stack."""

import argparse

from smaip.eval.harness import eval_main
from smaip.eval.week3 import week3_main
from smaip.eval.week4 import week4_main
from smaip.eval.week5 import week5_main
from smaip.eval.week6 import week6_main


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
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
