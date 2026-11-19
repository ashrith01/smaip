# Clean evidence pilot 02 — protocol-6 smoke test

Execution update: audited at 2/4 single-agent, 0/4 specialist successes. See
`reports/archive/EVIDENCE_CLEAN_02_SMOKE_ANALYSIS.md`. Use the next
[r3 numbered-source smoke runbook](EVIDENCE_PILOT_03_SMOKE.md) for further work;
the r2 instructions below are retained as the historical run record.

Pilot 01 finished but scored 0/25 in each topology: all readers/single agents
returned final before source access. See `reports/archive/EVIDENCE_CLEAN_01_ANALYSIS.md`.
The corrective source bundle is **smaip-task-evidence-pilot-r2.tar.gz**. Preserve
r1 and its failed evidence. R2 does not train or change any probe weights.

The new model prompt includes its exact tool/argument JSON schema and a clear
role task. Decoder constraints and role validation use that same schema. Missing
reader/analyst prerequisites block later models. Numeric source/quote validation,
trusted recipient binding, deterministic rendering and exact artifact checks
remain active. No oracle fields or automatic successful actions are introduced.
Protocol 6 is a new workflow policy, not an updated result for protocol 5.

Default job: cases clean-00, clean-06, clean-13 and clean-20 in both topologies,
**8 episodes**, covering one/seven reported fields and one/two/three pages.
These are known synthetic development cases, not a fresh generalization test.
Qwen model/revision, fp16, 4,096-input/1,024-output tokens and 12 calls per episode
match the old pilot. Limits: 900-second process timeout, 96 model calls and at
most 98,304 generated tokens. These are ceilings, not time/cost estimates.

All eight exact task scores must be true to qualify for a subsequent full
diagnostic pilot. Any failed task gives exit code 2 after preserving all eight
results; the shell still creates a return archive. This criterion does not
establish BRD quality/security acceptance. Partial execution, timeout or VM loss
remain distinct from completed task failures. A forced process/VM kill can
prevent the final archive while flushed episode files remain.

## Transfer from the Mac

```bash
cd /Users/ashrithvadde/Documents/GitHub/smaip
scp reports/smaip-task-evidence-pilot-r2.tar.gz \
  reports/smaip-task-evidence-pilot-r2.tar.gz.sha256 root@64.177.116.166:/root/
ssh root@64.177.116.166
tmux new -s smaip-evidence-r2
```

## Run inside the new GPU tmux session

Run each command only after the previous command succeeds:

```bash
cd /root
sha256sum -c smaip-task-evidence-pilot-r2.tar.gz.sha256
tar --keep-old-files -xzf smaip-task-evidence-pilot-r2.tar.gz
cd /root/smaip-task-evidence-pilot-r2
source /root/smaip/.venv/bin/activate
bash scripts/gpu/run_evidence_pilot.sh
```

Each progress line includes exact task success, successful page reads, model
calls and failure reason. Do not start the full pilot automatically. Return
the smoke traces first, including any failures.

## Retrieve from a Mac terminal

```bash
cd /Users/ashrithvadde/Documents/GitHub/smaip
mkdir -p .local-data/returned
scp root@64.177.116.166:/root/smaip-task-evidence-pilot-r2/reports/v3/evidence-clean-02-smoke.tar.gz \
  .local-data/returned/evidence-clean-02-smoke.tar.gz
.venv/bin/python scripts/analyze_evidence_pilot.py \
  --archive .local-data/returned/evidence-clean-02-smoke.tar.gz \
  --bundle reports/smaip-task-evidence-pilot-r2.tar.gz \
  --output .local-data/returned/evidence-clean-02-smoke.audit.json
```

The auditor recomputes task effects, verifies source/model/case identities and
supports historical protocol-5 r1 evidence separately. Process completion alone
does not mean quality passed. A software-tested correction has no measured GPU
quality improvement until the returned protocol-6 evidence has been audited.
