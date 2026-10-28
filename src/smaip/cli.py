"""Command line for the Week 1 scaffold."""

import argparse

from smaip.eval.harness import eval_main


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    from smaip.serving.app import create_app

    uvicorn.run(create_app(), host=host, port=port)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="smaip")
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve_parser = sub.add_parser("serve", help="run the mock-default API on localhost")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    eval_parser = sub.add_parser("eval", help="run the ablation harness")
    eval_parser.add_argument("--output", default="reports/week1_eval.json")
    args = parser.parse_args(argv)
    if args.cmd == "serve":
        serve(args.host, args.port)
        return 0
    if args.cmd == "eval":
        return eval_main(args.output)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
