#!/usr/bin/env python3
"""Run the original paired attack development pilot on pinned offline Qwen.

Default is the no-defense susceptibility gate. --compare adds two existing
defense arms only after that gate has produced a useful attack baseline.
"""

import argparse
import json
from pathlib import Path

from smaip.eval.attack_pilot import run_attack_pilot
from smaip.probes.pipeline_v2 import MODEL, REVISION
from smaip.serving.open_model import configured_engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compare', action='store_true', help='include least-privilege and keyword arms')
    args = parser.parse_args()
    engine = configured_engine('hf-local')
    config = engine.config
    if (config.model_id != MODEL or config.revision != REVISION or
            config.device != 'cuda' or config.dtype != 'float16' or
            config.max_new_tokens != 256 or config.max_input_tokens != 2048):
        raise ValueError('pilot requires pinned offline CUDA/fp16 Qwen and 256/2048 token budgets')
    variants = (('no-defense', 'least-privilege-only', 'keyword-screen')
                if args.compare else ('no-defense',))
    result = run_attack_pilot(engine, output=args.output, variants=variants)
    print(json.dumps({'status': result['status'], 'aggregates': result['aggregates']}, indent=2))


if __name__ == '__main__':
    main()
