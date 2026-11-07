"""Run the fixed paired development suite using the pinned local HF model."""
import argparse
import json
from pathlib import Path

from smaip.eval.open_agent_dev import run_development
from smaip.serving.open_model import configured_engine


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    summary = run_development(configured_engine('hf-local'), output=args.output)
    print(json.dumps({'status': summary['status'], 'aggregates': summary['aggregates']}, indent=2))
