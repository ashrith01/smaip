# Complete only the missing r3 episodes

Completion update, November 1: the combined archive is audited at 50 episodes,
with 22/25 single-agent and 23/25 specialist successes. All 40 original records
and their failures remain unchanged; 170 citations across 45 successes were
revalidated. See `reports/EVIDENCE_CLEAN_03_COMPLETED_ANALYSIS.md`. The commands
below are the retained historical procedure; this continuation need not be rerun.

The full job hit its 900-second cap after 40 completed episodes. Parent integrity
and scores were audited: single-agent 17/20, specialists 19/20. Four completed
failures remain failures. See `reports/EVIDENCE_CLEAN_03_FULL_PARTIAL_ANALYSIS.md`.

The continuation launcher preserves every completed episode byte-for-byte and
runs only clean-20 through clean-24 in both topologies. No r3 package file,
prompt, model, policy, scoring rule or per-episode budget changes. The launcher
is added under `scripts/`, outside the package, and verifies every original
manifest member plus imported runtime hashes. It records its own source/hash
and exact parent archive binding in the new summary.

## Upload from the Mac

```bash
cd /Users/ashrithvadde/Documents/GitHub/smaip
scp scripts/continue_evidence_pilot.py \
  scripts/continue_evidence_pilot.py.sha256 \
  root@64.177.116.166:/root/smaip-task-evidence-pilot-r3/scripts/
ssh root@64.177.116.166
```

## Start a fresh GPU tmux session

```bash
tmux new -s smaip-evidence-continue
```

Inside it, run each command after the previous succeeds:

```bash
cd /root/smaip-task-evidence-pilot-r3/scripts
sha256sum -c continue_evidence_pilot.py.sha256
cd ..
source /root/smaip/.venv/bin/activate
timeout --signal=TERM --kill-after=60 1800 python -u scripts/continue_evidence_pilot.py
```

The defaults pin the exact audited 40-episode parent and original r3 source
archive. Both files remain untouched. The output is a fresh
`reports/v3/evidence-clean-03-completed/` directory and corresponding tar.gz.
Progress begins at 41/50. Completed failures are not retried or replaced.

Cap: **30 minutes**, at most **120 new model calls / 122,880 generated tokens**.
The hard-kill fallback allows up to 60 additional seconds for shutdown. These
are ceilings, not estimates. Normal exceptions and termination save completed
records to an archive; forced kills/VM loss can prevent final archiving, while
flushed episode files remain. Earlier unflushed work is unobserved.

For a read-only plan check before execution, add `--check-only` to the Python
command. It validates the source/parent and lists missing IDs without loading a
model or creating the result directory. An existing output/partial archive causes
an error; preserve it and inspect it instead of deleting or overwriting it.

## Retrieve on the Mac after completion

```bash
cd /Users/ashrithvadde/Documents/GitHub/smaip
scp root@64.177.116.166:/root/smaip-task-evidence-pilot-r3/reports/v3/evidence-clean-03-completed.tar.gz \
  .local-data/returned/evidence-clean-03-completed.tar.gz
.venv/bin/python scripts/analyze_evidence_pilot.py \
  --archive .local-data/returned/evidence-clean-03-completed.tar.gz \
  --bundle reports/smaip-task-evidence-pilot-r3.tar.gz \
  --output .local-data/returned/evidence-clean-03-completed.audit.json
```

This is a segmented completion of the same clean diagnostic, not an uninterrupted
serving benchmark or a new independent dataset. All earlier failed task scores
remain in the final denominator. Execution completion is separate from quality,
security and release acceptance. This performs no model/probe training.
