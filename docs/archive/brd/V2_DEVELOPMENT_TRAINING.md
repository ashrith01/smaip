# First V2 development probe training

Use this run after the verified GPU feature smoke. It collects new real Qwen
features, fits last-token and mean-pooled logistic probes, calibrates thresholds,
and evaluates frozen probes on the development test split. Qwen stays frozen.

## Prerequisites

- The restored GPU at `64.177.116.166`, working `nvidia-smi`, the existing
  `/root/smaip/.venv` environment and pinned Qwen cache.
- The new `reports/smaip-v2-training-dev-r1.tar.gz` source bundle on the Mac.
- One GPU job at a time. This uses layer 18, which passed the feature smoke.

No package installation or model download is performed by the job. Keep the SSH
session connected until it completes, or run it inside an existing terminal
multiplexer session.

## Transfer from the Mac

```bash
scp "/Users/ashrithvadde/Documents/GitHub/smaip/reports/smaip-v2-training-dev-r1.tar.gz" root@64.177.116.166:/root/
ssh root@64.177.116.166
```

## Run on the GPU

```bash
source /root/smaip/.venv/bin/activate
if [ -f /root/smaip/.venv/smaip-gpu.env ]; then
  set -a
  source /root/smaip/.venv/smaip-gpu.env
  set +a
fi

test ! -e /root/smaip-v2-training-dev-r1 || {
  echo "Directory already exists; preserve its results."
  exit 1
}
tar -xzf /root/smaip-v2-training-dev-r1.tar.gz -C /root
cd /root/smaip-v2-training-dev-r1
bash scripts/gpu/train_v2_development.sh
```

The script verifies every bundled file before collection and puts the new source
first in `PYTHONPATH`. Its manifest records a base Git commit plus exact file
hashes: this source bundle includes locally added, uncommitted implementation.

The stages are separate commands under `python -m smaip.probes.pipeline_v2`:
`collect`, `fit`, then `evaluate`. Collection rejects oversize documents instead
of truncating them. Fitting learns standardization and logistic parameters from
training records only. The fixed layer is not selected using calibration/test
results. Each probe's threshold maximizes calibration recall subject to the
empirical 1%-FPR budget. Evaluation uses that frozen threshold and the shared
`ProtocolProbe` scoring implementation on saved test vectors; it does not refit.

## Download from a Mac terminal

```bash
scp root@64.177.116.166:/root/smaip-v2-training-dev-r1/reports/v2/probe-development-01.tar.gz "/Users/ashrithvadde/Documents/GitHub/smaip/reports/"
```

Download the archive even if the job fails. After output-directory creation,
the exit handler packages logs, partial data, status and checksums on both success
and failure. A completed collection has `collection/collection.json`; a completed
fit has `probes/fit.json`; a completed evaluation has `evaluation/evaluation.json`.

The archive includes the corpus/provenance, raw last-token and mean vectors,
feature protocol, source/runtime identities, two format-2 probe files, calibration
operating points and individual test predictions. Old V1 probes and old GPU
checkouts are untouched. A rerun requires a fresh `SMAIP_V2_OUTPUT` inside
`reports/v2/`; partial outputs are never overwritten automatically.

## Meaning of the results

`data/v2/development-01.jsonl` contains 36 original authored examples: 12 per
split, with six benign and six injected documents in each. Clean/injected source
pairs stay within a split, declared attack-family names do not cross splits, and
the normalized exact-duplicate validator passes. The provenance record documents
assistant label review, absence of human review and the synthetic group policy.

These are small, stylistically related development examples. Six benign
calibration/test documents cannot establish population 1%-FPR behavior; a zero-FP
result still has weak statistical resolution. Held-out development metrics are
diagnostics, not independent benchmark accuracy or security evidence.

After the returned artifacts are audited, build the larger reviewed independent
corpus, freeze its data/selection protocol and repeat fitting/calibration/evaluation
under that protocol. The current pipeline deliberately accepts only development
provenance; independent-corpus support and its acceptance checks need an explicit
extension. Agent integration and the two remaining actor utility failures are
separate follow-up work. Keep development metrics out of final BRD acceptance.
