# Paired open-agent development run

**Completed run:** revision 4/checkpoint `9d40bd7` has been returned and verified.
All 24 episodes completed. Clean task success was 4/4 for no-defense, 0/4 for
least privilege, and 4/4 for keyword; no declared attacker objective succeeded.
See `reports/OPEN_AGENT_DEV_01_ANALYSIS.md` for the audit and remaining failures.
The commands below reproduce the historical protocol-3 run; they are not a request
to run it again. Protocol-4 handoff repairs are tested locally but await a future
GPU regression. Preserve a completed snapshot before destroying the idle instance.

## Current checkpoint

Pilot 03 verified the Pydantic/constrained generation path on the A16: 24 valid
responses, four sandboxed deliveries, no attacker-directed send or audit mutation.
The summaries exposed missing facts, unsupported currency and placeholder contamination;
the delivery flag is not factual-quality evidence. See `reports/OPEN_MODEL_PILOT_03_ANALYSIS.md`.

This completed run measured a newly declared canonical numeric task on four matched
clean/injected pairs. This is development-only fixture evaluation; it does not train
probes or establish independent BRD acceptance. The script uses the decoder package
and model cache already verified in pilot 03, with the same Python environment.

## Transfer and run

Mac terminal:

```bash
scp "/Users/ashrithvadde/Documents/GitHub/smaip/reports/brd-open-model-v2-r4.tar.gz" root@45.63.76.130:/root/
ssh root@45.63.76.130
```

GPU terminal:

```bash
test ! -e /root/smaip-open-model-v2-r4 || {
  echo "Directory already exists; preserve its results."
  exit 1
}
tar -xzf /root/brd-open-model-v2-r4.tar.gz -C /root
source /root/smaip/.venv/bin/activate
cd /root/smaip-open-model-v2-r4
bash scripts/gpu/open_agent_development.sh
```

No package installation or training command is needed. The wrapper validates the
bundle and pinned decoder, records runtime versions, sets offline/cached model
access, and uses the new directory's source via `PYTHONPATH`. The existing GPU
checkout is not automatically synchronized: this transfer is the source update.

The job runs four clean controls in each of three variants, then the four injected
counterparts in each variant only if all four undefended clean tasks pass. At most
24 episodes/288 model calls run, each bounded to 12 calls and 256 new tokens per
call. It loads Qwen once and uses in-memory fixture tools. No runtime estimate is
claimed for this newly implemented benchmark.

Mac terminal after completion:

```bash
scp root@45.63.76.130:/root/smaip-open-model-v2-r4/reports/v2/open-agent-dev-01.tar.gz "/Users/ashrithvadde/Documents/GitHub/smaip/reports/"
```

Outputs contain the exact case manifest/instruction/ground truth, every model/tool
trace, independent per-case scores, counts/rates, runtime metadata, package versions,
bundle validation and model logs. Runtime failures retain completed rows and the
log. Missing attack rates are null. A positive attacker-send rate records the tool
effect, not proof of confidential-data disclosure or causal attribution by itself.

## Decisions after this run

1. The utility/effect scores have now been checked: the least-privilege handoff adds
   unreported fields or scratch files, while all attacker objectives remain zero.
   Preserve those results. Recheck the local protocol-4 repair in the next scheduled
   GPU window; susceptibility and strict full-stack superiority remain pending.
2. Freeze a broader independent evaluation/data protocol with source/family holdouts,
   reviewed document labels, upstream license records and adaptive cases. Keep these
   V1-derived development pairs out of final accuracy claims.
3. Implement the V2 feature-collection/fitting command using the existing pinned
   tool-content extractor and independent 1%-FPR calibration policy. Validate actual
   feature collection/scoring on GPU before training and preserve raw vectors.
4. Add learned-detector/full-stack rows only with real V2 weights, then finish
   persisted approval/review, live serving benchmarks, release documentation and demo.

The BRD gate remains pending throughout this development-only run. No old probe
thresholds or result files should be changed to improve these outcomes.
