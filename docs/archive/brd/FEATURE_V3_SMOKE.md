# Version 3 feature rendering smoke

This forward-only development check reads 32 original assistant-authored
documents. It keeps the pinned Qwen2.5-3B-Instruct model, uses CUDA fp16,
batch one, and reads blocks 6, 18, and 30. Each document receives two
renderings: the frozen V2 inspection context, and that same literal context
with an appended assistant-generation prompt. Each view is limited to 512
tokens without truncation. The second view saves content-last, content-mean,
and the final assistant-boundary token. One extra forward repeats the first
document to check numerical stability. There are 65 forward passes total.

The new protocol has its own fingerprint. No V2 probe weights, thresholds,
labels, model fitting, or detector quality claims are involved. The existing
V2 source and its saved probe files are untouched.

## Upload from the Mac

```bash
cd /Users/ashrithvadde/Documents/GitHub/smaip
cd reports
shasum -a 256 -c smaip-feature-v3-smoke-r1.tar.gz.sha256
cd ..
scp reports/smaip-feature-v3-smoke-r1.tar.gz \
  reports/smaip-feature-v3-smoke-r1.tar.gz.sha256 \
  root@64.177.116.166:/root/
ssh root@64.177.116.166
```

## Run on the GPU

Run the following in the GPU terminal, preferably inside a fresh tmux
session. The original `/root/smaip/.venv` and cached pinned model must be
available. No package installation or model download is requested.

```bash
cd /root
sha256sum -c smaip-feature-v3-smoke-r1.tar.gz.sha256
tar --keep-old-files -xzf smaip-feature-v3-smoke-r1.tar.gz
cd /root/smaip-feature-v3-smoke-r1
source /root/smaip/.venv/bin/activate
timeout --signal=TERM --kill-after=60 900 \
  python -u scripts/gpu/feature_v3_smoke.py
```

The script writes a fresh `reports/v3/feature-v3-smoke-01/` and
`reports/v3/feature-v3-smoke-01.tar.gz`. Exit 0 means the 32-document
renderer/precision/prefix checks passed. Exit 2 means the job completed but
prefix or repeatability diagnostics require investigation; the archive is
still saved. Exit 1 means a runtime or source validation error. The 900-second
cap has a 60-second hard-stop fallback. If a forced kill prevents archiving,
retain the output directory for diagnosis.

## Copy the evidence to the Mac

```bash
cd /Users/ashrithvadde/Documents/GitHub/smaip
scp root@64.177.116.166:/root/smaip-feature-v3-smoke-r1/reports/v3/feature-v3-smoke-01.tar.gz \
  .local-data/returned/feature-v3-smoke-01.tar.gz
.venv/bin/python scripts/analyze_feature_v3_smoke.py \
  --bundle reports/smaip-feature-v3-smoke-r1.tar.gz \
  --archive .local-data/returned/feature-v3-smoke-01.tar.gz \
  --output .local-data/returned/feature-v3-smoke-01.audit.json
```

The local audit checks the exact source bundle, returned file hashes,
document IDs, token positions, vector dimensions, layer set, and smoke
decision. It does not score attack detection. If the smoke passes, the next
step is reviewed, grouped pilot data and a separate versioned feature
collection. The current 1,012-row candidate queue is unreviewed and has
no assigned split roles, so it cannot be treated as a fitted or independently
validated detector corpus.
