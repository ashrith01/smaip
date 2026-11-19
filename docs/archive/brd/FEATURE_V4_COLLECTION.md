# Collect boundary-view candidate features

The commands below document the completed 2026-10-31 collection. The current
V4 source and collector now share a feature-view module, so their bytes differ
from the frozen source bundle and archived collector checksum. Do not rerun
these commands against the frozen bundle; prepare a new versioned bundle and
output path for any new GPU collection. The archived checksum remains the
identity of the original collector for re-auditing the saved vectors.

The pinned-tokenizer audit verified that all 1,012 current task/document
renderings fit within 2,048 tokens without truncation. This collection uses
the original label-free source already on the GPU. It loads the pinned frozen
Qwen2.5-3B-Instruct once, runs one forward per candidate, and saves blocks
6, 18 and 30 with content-last, content-mean and assistant-boundary readouts
from the **same** task-conditioned rendering. It uses fp16 model weights,
float32 pooling and little-endian float32 binary storage. The first records
are the longest inputs so resource problems are exposed early.

The original source archive, all its listed files, and the returned
token-budget archive are SHA-256 checked before model load. The collector is
uploaded separately with its own checksum; no frozen bundle file changes.
Output metadata contains source/ID/task/document hashes, token counts,
protocol fingerprint and per-row binary hashes. It has no labels, review
decisions or split roles. This is forward-only research data, **not** a
trained detector or a low-FPR result.

## Upload from the Mac

```bash
cd /Users/ashrithvadde/Documents/GitHub/smaip
scp scripts/gpu/collect_feature_v4.py \
  scripts/gpu/collect_feature_v4.py.sha256 \
  root@64.177.116.166:/root/smaip-feature-v4-token-budget-r1/scripts/gpu/
ssh root@64.177.116.166
```

## Run on the GPU

```bash
cd /root/smaip-feature-v4-token-budget-r1/scripts/gpu
sha256sum -c collect_feature_v4.py.sha256
cd ../..
source /root/smaip/.venv/bin/activate
timeout --signal=TERM --kill-after=60 900 \
  python -u scripts/gpu/collect_feature_v4.py
```

The bounded job performs at most **1,012 forward passes**. It writes a fresh
`reports/v4/feature-collection-01/` and
`reports/v4/feature-collection-01.tar.gz`. The binary matrix is about 71 MiB
before compression. The 900-second cap has a 60-second hard-stop fallback.
The first input is the 1,033-token case; there is no padding to 2,048.
If a runtime error occurs, the script preserves completed rows in a failed
archive. Do not fit on partial output or overwrite it.

## Copy back and audit on the Mac

```bash
cd /Users/ashrithvadde/Documents/GitHub/smaip
scp root@64.177.116.166:/root/smaip-feature-v4-token-budget-r1/reports/v4/feature-collection-01.tar.gz \
  .local-data/returned/feature-v4-collection-01.tar.gz
.venv/bin/python scripts/analyze_feature_v4_collection.py \
  --source reports/smaip-feature-v4-token-budget-r1.tar.gz \
  --budget .local-data/returned/token-budget-v4-01.tar.gz \
  --archive .local-data/returned/feature-v4-collection-01.tar.gz \
  --collector-checksum scripts/gpu/collect_feature_v4.py.sha256 \
  --output .local-data/returned/feature-v4-collection-01.audit.json
```

The auditor verifies all 1,012 source IDs and render hashes, the exact
protocol, binary offsets/hashes, float32 finiteness and completed forward
count. After this, labels, provenance and connected lineage still need
review before choosing training/selection/threshold-development roles. The
observed NVIDIA external set remains regression-only, and these vectors do
not create an independent test or calibration sample.
