"""Command line for the SMAIP mock stack."""

import argparse

from smaip.eval.harness import eval_main
from smaip.eval.week3 import week3_main


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
    args = parser.parse_args(argv)
    if args.cmd == "serve":
        serve(args.host, args.port)
        return 0
    if args.cmd == "eval":
        return eval_main(args.output)
    if args.cmd == "week3":
        return week3_main(args.output)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
