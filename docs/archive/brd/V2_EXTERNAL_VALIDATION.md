# Frozen external probe validation

Run this after the first V2 development training archive has been audited. It
scores the two saved probes on a separate source without retraining, changing
thresholds or adding an agent loop.

**Completed:** the returned run scored all 800 documents, with no token-budget
exclusions. The audit verified frozen models, data preparation, classifications
and metrics. Linear caught 0/400 attacks with 0/400 benign false alarms; mean
pooling caught 1/400 with 1/400 false alarms. Both mean-pooling positives came
from the same clean/injected pair. See
`reports/archive/V2_EXTERNAL_FROZEN_01_ANALYSIS.md`. The commands below reproduce the
completed configuration; an unchanged repeat is not needed. This set is now
known development evidence and must not become a threshold-tuning final test.

## Data and measurement plan

Source: NVIDIA Corporation,
[Nemotron-RL-Agentic-Indirect-Prompt-Injection-v1](https://huggingface.co/datasets/nvidia/Nemotron-RL-Agentic-Indirect-Prompt-Injection-v1/tree/d738d4f361cc38bb4d7a42b9066776dade5332f5),
revision `d738d4f361cc38bb4d7a42b9066776dade5332f5`. Its pinned card explicitly
declares CC BY 4.0, fully synthetic generation without seed data, and NVIDIA
ownership. Original attribution, the license link and modification details are
included in the prepared corpus. No external raw examples are checked into Git;
local source and prepared data are under ignored `.local-data/`.

The upstream source has 1,272 attack records. The adapter locates the unique
environment string containing the exact annotated injection. It derives a clean
control by removing that span and trimming outer whitespace. It excludes four
missing/ambiguous spans, 16 contexts with fewer than eight residual words and
seven residual attack wrappers, retaining 1,245 candidate pairs. A declared
near-duplicate check creates 1,235 context groups. No exact or declared near
overlap with the known 36-document development corpus was found.

Selection is frozen before scoring: one hash-selected representative per clean
context group, then the first 400 groups in a fixed hash order. The prepared
corpus has 400 clean controls and 400 injected documents across nine domains and
four upstream attack categories. The source, derived corpus, selection policy and
two exact probe hashes are recorded in `policy.json` and the source bundle.

The extractor retains the trained feature protocol and layer 18. A pair exceeding
the 512-token feature budget is excluded in full, before either member is scored;
every such exclusion is reported. There is no truncation or score-based filtering.
Both probes reuse one model forward per accepted document. The job saves raw
vectors, document scores, fixed-threshold predictions, confusion counts and AUROC.

The probes remain exactly those from development run 01: last-token threshold
0.952380227403302 and mean-pooled threshold 0.593589928048717. Corpus contents,
thresholds and candidate selection must not be changed after seeing this run to
report a more favorable held-out score.

## Scope and limitations

These examples were held out from probe fitting and calibration, but they come
from a single synthetic source optimized against a different defender. Shared
attack wrappers remain. Clean controls are derived from upstream span metadata,
not human-labeled clean originals; structural filtering does not prove every
remaining control is semantically clean. Human label review has not occurred.
Context deduplication does not prove statistical independence.

This is therefore external pilot validation of detector behavior, not a final
independent deployment-population benchmark. Any zero-FP upper bound is explicitly
conditional on independence. The result cannot establish a population 1%-FPR
guarantee, adaptive robustness, agent ASR, full-stack superiority or BRD acceptance.
There is no model or probe training in this run. A broader reviewed corpus and
predeclared training/calibration/final-test protocol remain subsequent work.

## Mac: upload and connect

```bash
scp "/Users/ashrithvadde/Documents/GitHub/smaip/reports/smaip-v2-external-eval-r1.tar.gz" root@64.177.116.166:/root/
ssh root@64.177.116.166
```

## GPU: run with the restored environment

```bash
source /root/smaip/.venv/bin/activate
if [ -f /root/smaip/.venv/smaip-gpu.env ]; then
  set -a
  source /root/smaip/.venv/smaip-gpu.env
  set +a
fi
test ! -e /root/smaip-v2-external-eval-r1 || {
  echo "Directory already exists; preserve its results."
  exit 1
}
tar -xzf /root/smaip-v2-external-eval-r1.tar.gz -C /root
cd /root/smaip-v2-external-eval-r1
bash scripts/gpu/evaluate_v2_external.sh
```

The bundle includes the prepared external data, source card/attribution and exact
frozen probes. The wrapper verifies all file hashes, forces the new source first
in `PYTHONPATH`, reuses the pinned cached Qwen checkpoint offline and installs
nothing. Keep the SSH session connected or use an existing terminal multiplexer.
Source is a hash-pinned working-tree snapshot, not a newly committed Git revision.

## Mac: download evidence

```bash
scp root@64.177.116.166:/root/smaip-v2-external-eval-r1/reports/v2/external-frozen-01.tar.gz "/Users/ashrithvadde/Documents/GitHub/smaip/reports/"
```

Download on failure too. After output-directory creation, the exit handler
packages status, logs, checksums and partial artifacts. It refuses to overwrite
an earlier result. A completed run has `evaluation/evaluation.json` and top-level
`status.json` reporting `completed`. Returned evidence must be audited before
reporting measured results. The completed run and its audit are described above.
