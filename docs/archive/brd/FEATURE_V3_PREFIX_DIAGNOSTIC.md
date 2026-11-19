# Diagnose the two Feature V3 prefix exceptions

Completion update, November 1: the returned diagnostic archive was audited
against the original source and GPU result. All nine forwards completed.
Original-view replay and same-length changed-suffix comparisons each had
maximum absolute difference **0.0** across the selected readouts. The
`shape_effect_supported` result is true. The original 32-document smoke
remains failed under its predeclared tolerance. See
`reports/archive/FEATURE_V3_SMOKE_01_ANALYSIS.md`. The commands below are retained
for provenance and need not be rerun.

The original 32-document smoke completed and its archive passed integrity
checks, but its predeclared causal-prefix tolerance failed on two 96 → 99
token renderings. See `reports/archive/FEATURE_V3_SMOKE_01_ANALYSIS.md`.

This small follow-up does **nine** forwards: original baseline, original
boundary, and an equally long boundary rendering with different suffix token
IDs for each of the two exceptions and one passing control. It checks replay
against the saved parent vectors. It uses the original pinned model, unchanged
source checkout, and original GPU archive; no source bundle is rebuilt, no
training occurs, and no failed smoke is overwritten.

## Upload from the Mac

```bash
cd /Users/ashrithvadde/Documents/GitHub/smaip
scp scripts/gpu/diagnose_feature_v3_prefix.py \
  scripts/gpu/diagnose_feature_v3_prefix.py.sha256 \
  root@64.177.116.166:/root/smaip-feature-v3-smoke-r1/scripts/gpu/
ssh root@64.177.116.166
```

## Run on the GPU

```bash
cd /root/smaip-feature-v3-smoke-r1/scripts/gpu
sha256sum -c diagnose_feature_v3_prefix.py.sha256
cd ../..
source /root/smaip/.venv/bin/activate
timeout --signal=TERM --kill-after=60 300 \
  python -u scripts/gpu/diagnose_feature_v3_prefix.py
```

The original source archive, all 75 source files, and the original GPU result
are hash-checked before the model loads. The new output is
`reports/v3/feature-v3-prefix-diagnostic-01.tar.gz`. It is a diagnostic
result, even if `shape_effect_supported` is false. Preserve the original
`feature-v3-smoke-01.tar.gz`.

## Copy back to the Mac and audit

```bash
cd /Users/ashrithvadde/Documents/GitHub/smaip
scp root@64.177.116.166:/root/smaip-feature-v3-smoke-r1/reports/v3/feature-v3-prefix-diagnostic-01.tar.gz \
  .local-data/returned/feature-v3-prefix-diagnostic-01.tar.gz
.venv/bin/python scripts/analyze_feature_v3_prefix.py \
  --archive .local-data/returned/feature-v3-prefix-diagnostic-01.tar.gz \
  --source reports/smaip-feature-v3-smoke-r1.tar.gz \
  --parent .local-data/returned/feature-v3-smoke-01.tar.gz \
  --output .local-data/returned/feature-v3-prefix-diagnostic-01.audit.json
```

The auditor checks the exact source/parent hashes, result inventory, three
case identities, all six readouts at each selected block, and the saved
numerical conclusion. A supported shape-effect explanation permits a new
versioned feature protocol to use the boundary view as its own readout; it
does not retrospectively change the V3 smoke result or establish detector
quality.
