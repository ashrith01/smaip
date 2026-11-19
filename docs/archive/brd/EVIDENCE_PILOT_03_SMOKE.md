# Clean evidence pilot 03 — numbered source references

Use **smaip-task-evidence-pilot-r3.tar.gz**, agent protocol 7. R2 was audited at
2/4 single-agent and 0/4 specialist successes. Citation formatting/source identity
errors blocked correct numeric claims; see `reports/archive/EVIDENCE_CLEAN_02_SMOKE_ANALYSIS.md`.
Preserve r1, r2 and both returned archives. R3 performs no probe training.

## What changed

Read results and analyst handoffs include an explicit `source_id` and every
original line with its one-based `line_number`. The model must propose each
claim's `field`, `value`, `source_id` and `line_number`. The server validates that
exact line and attaches its original quote and source hash. It does not choose
facts, repair wrong references or expose the task scorer's expected answers.
Incorrect/unknown sources, wrong lines/fields/values, incomplete facts,
conflicting sources and changed snapshots still fail. Original version-1 quote
artifacts remain supported by checkpoint validation; new version-2 artifacts bind
the model-selected references too.

Available capabilities now follow trusted workflow state in both topologies:
read unread authorized pages, submit claims, then propose sending the validated
artifact. The schema constrains identities already authorized by the task or
produced by validation. A failed final is still an abort; every read/claim/send
must be model-proposed. The service independently enforces scope even if a
caller bypasses the decoder. This is a new constrained workflow policy, not a
completed historical BRD ablation or a detector improvement.

## Bounds and interpretation

Same four known cases clean-00/06/13/20 × two topologies = **8 episodes**. They
span one/seven fields and one/two/three pages. Keep the pinned Qwen 3B revision,
fp16 CUDA, 4,096-input/1,024-output token limits and 12 calls per episode.
Maximum: 96 calls / 98,304 generated tokens, 900-second process timeout. These
are ceilings, not estimates. The eight strict task scores must all be true to
qualify for a subsequent full diagnostic pilot. This feasibility gate is not
BRD security/release acceptance. No new GPU success is yet claimed.

Progress prints `pages=<unique>/<required>` and `read_calls=<count>` separately,
plus model-call count and failure reason. Normal failure/quality failure/timeout
preserves evidence in the return archive. Completed smoke failures exit with
code 2; they are distinct from an execution crash. A forced kill/VM termination
can prevent final archiving while already flushed episode files remain.

## On the Mac

```bash
cd /Users/ashrithvadde/Documents/GitHub/smaip
scp reports/smaip-task-evidence-pilot-r3.tar.gz \
  reports/smaip-task-evidence-pilot-r3.tar.gz.sha256 root@64.177.116.166:/root/
ssh root@64.177.116.166
```

## On the GPU

Start a fresh tmux session:

```bash
tmux new -s smaip-evidence-r3
```

Inside it, run each command after the previous succeeds:

```bash
cd /root
sha256sum -c smaip-task-evidence-pilot-r3.tar.gz.sha256
tar --keep-old-files -xzf smaip-task-evidence-pilot-r3.tar.gz
cd /root/smaip-task-evidence-pilot-r3
source /root/smaip/.venv/bin/activate
bash scripts/gpu/run_evidence_pilot.sh
```

## Retrieve and audit from a Mac terminal

```bash
cd /Users/ashrithvadde/Documents/GitHub/smaip
mkdir -p .local-data/returned
scp root@64.177.116.166:/root/smaip-task-evidence-pilot-r3/reports/v3/evidence-clean-03-smoke.tar.gz \
  .local-data/returned/evidence-clean-03-smoke.tar.gz
.venv/bin/python scripts/analyze_evidence_pilot.py \
  --archive .local-data/returned/evidence-clean-03-smoke.tar.gz \
  --bundle reports/smaip-task-evidence-pilot-r3.tar.gz \
  --output .local-data/returned/evidence-clean-03-smoke.audit.json
```

The auditor recomputes strict task effects and the progress diagnosis and binds
source/model/case identities. It separately supports historical r1/r2 protocols.
Inspect returned evidence before another full pilot or training collection.
