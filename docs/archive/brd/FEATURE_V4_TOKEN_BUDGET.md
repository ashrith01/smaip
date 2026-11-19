# Pinned-tokenizer budget audit for the candidate corpus

The Feature V3 follow-up reproduced the original vectors exactly and found
zero prefix change when the suffix tokens changed at the same sequence
length. The original 32-document smoke remains failed under its predefined
absolute tolerance. New feature work will take content and assistant-boundary
readouts from one boundary rendering, with a separate protocol fingerprint.

Before collecting new activations, this tokenizer-only audit counts the
full rendered lengths of all **1,012 unreviewed task-document candidates**
from the pinned local queue. It compares three views:

1. The fixed-inspection assistant boundary used in the smoke.
2. The candidate's actual trusted-task **description** plus its untrusted
   document at an assistant boundary.
3. That trusted-task description alone at an assistant boundary, for a
   possible later task-relative comparison.

The candidate queue stores a single trusted-task string, not the source's
native structured message roles. The task-conditioned renderer places that
string in a user message and records the source adaptation. Its results do
not establish native-agent fidelity. The bundle exports the candidate task
and document text but no labels, review decisions, or split roles. It
includes source attribution and remains outside Git. The job loads the
pinned tokenizer from the GPU's local Hugging Face cache; it loads **no model
weights**, performs no forward passes, and fits no probe.

## Upload from the Mac

```bash
cd /Users/ashrithvadde/Documents/GitHub/smaip
cd reports
shasum -a 256 -c smaip-feature-v4-token-budget-r1.tar.gz.sha256
cd ..
scp reports/smaip-feature-v4-token-budget-r1.tar.gz \
  reports/smaip-feature-v4-token-budget-r1.tar.gz.sha256 \
  root@64.177.116.166:/root/
ssh root@64.177.116.166
```

## Run on the GPU instance

```bash
cd /root
sha256sum -c smaip-feature-v4-token-budget-r1.tar.gz.sha256
tar --keep-old-files -xzf smaip-feature-v4-token-budget-r1.tar.gz
cd /root/smaip-feature-v4-token-budget-r1
source /root/smaip/.venv/bin/activate
timeout --signal=TERM --kill-after=60 600 \
  python -u scripts/gpu/token_budget_v4.py
```

The job writes a fresh `reports/v4/token-budget-01/` and
`reports/v4/token-budget-01.tar.gz`. It reports exact min/median/p95/max
lengths and counts above 512, 1,024, 2,048 and 4,096 tokens by view and
source. It refuses truncation. If an unexpected rendering fails, it saves
the completed prefix of the audit and an error archive for diagnosis.

## Copy the result to the Mac

```bash
cd /Users/ashrithvadde/Documents/GitHub/smaip
scp root@64.177.116.166:/root/smaip-feature-v4-token-budget-r1/reports/v4/token-budget-01.tar.gz \
  .local-data/returned/token-budget-v4-01.tar.gz
.venv/bin/python scripts/analyze_token_budget_v4.py \
  --bundle reports/smaip-feature-v4-token-budget-r1.tar.gz \
  --archive .local-data/returned/token-budget-v4-01.tar.gz \
  --output .local-data/returned/token-budget-v4-01.audit.json
```

The local audit verifies all source/result file hashes, the exact 1,012
candidate IDs, source/task/document hashes, token accounting and reported
distributions. The resulting budget can guide a versioned boundary feature
protocol and full-span refusal policy. The queue still needs provenance and
label review, group-preserving split assignment, and an honest feasibility
scope before any fitting or threshold claim.
