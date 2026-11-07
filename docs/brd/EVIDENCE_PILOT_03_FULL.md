# Full clean pilot — same frozen r3 source

Execution update: the original job timed out at 40/50, with 17/20 single-agent
and 19/20 specialist successes verified. Use the
[missing-episode continuation](EVIDENCE_PILOT_03_CONTINUATION.md); do not rerun or
overwrite the first 40. The instructions below describe the original launch.

November 1 completion update: that continuation is now audited at all 50
episodes, with final results 22/25 single-agent and 23/25 specialist. See
`reports/EVIDENCE_CLEAN_03_COMPLETED_ANALYSIS.md`. Both launch procedures below
remain historical; no further clean rerun is required for this baseline.

Prerequisite passed: the returned r3 smoke archive was audited at 8/8 successes,
with 44 independently reconstructed citations, exact artifact/intent bindings,
zero refusals and no repeated reads. See `reports/EVIDENCE_CLEAN_03_SMOKE_ANALYSIS.md`.

No source update or new bundle is needed. Reuse the existing isolated
`/root/smaip-task-evidence-pilot-r3` directory and restored environment.

In the existing GPU tmux session:

```bash
cd /root/smaip-task-evidence-pilot-r3
source /root/smaip/.venv/bin/activate
SMAIP_PILOT_MODE=full \
SMAIP_PILOT_OUTPUT=reports/v3/evidence-clean-03-full \
bash scripts/gpu/run_evidence_pilot.sh
```

This runs **25 known original tasks × two topologies = 50 episodes**. Four tasks
overlap the smoke; do not count those as new independent samples. The source,
model revision, 4,096-input/1,024-output token budgets, 12 calls per episode and
scorer are unchanged. Effects remain in-memory sends with benchmark review
disabled. It performs no probe fitting, model fine-tuning or security evaluation.

The existing frozen wrapper retains its **900-second process cap**. The full
job permits at most 600 model calls / 614,400 generated tokens, subject to that
time cap. These are ceilings, not runtime or cost estimates. If time-limited,
preserve the partial archive and report incomplete execution, not a 50-episode
quality result. A normal failure/timeout writes a return archive; a forced kill
or VM termination can prevent final archiving while flushed runs remain.

The fresh `evidence-clean-03-full` directory preserves smoke and earlier results.
If it already exists, stop and inspect it rather than overwriting or deleting it.

After completion, from a Mac terminal outside SSH:

```bash
cd /Users/ashrithvadde/Documents/GitHub/smaip
scp root@64.177.116.166:/root/smaip-task-evidence-pilot-r3/reports/v3/evidence-clean-03-full.tar.gz \
  .local-data/returned/evidence-clean-03-full.tar.gz
.venv/bin/python scripts/analyze_evidence_pilot.py \
  --archive .local-data/returned/evidence-clean-03-full.tar.gz \
  --bundle reports/smaip-task-evidence-pilot-r3.tar.gz \
  --output .local-data/returned/evidence-clean-03-full.audit.json
```

Process completion is distinct from task utility. Inspect actual strict task
scores and failure traces even when the shell exits successfully. The audit's
`smoke_qualified_for_full_pilot` is a smoke-only field and is false for a full
job by definition; assess full-job completion and its per-topology counts.

Even a perfect clean result supplies no ASR/low-FPR probe result, generalization
guarantee or statistical proof of five-point noninferiority. These are synthetic
workflow diagnostics under a common constrained policy, separate from the
historical unrestricted/defense ablation matrix and subsequent detector work.
