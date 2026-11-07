# Feature V3 development smoke 01: causal prefix exception

The returned GPU archive was copied to `.local-data/returned/feature-v3-smoke-01.tar.gz`
and independently audited against source bundle
`reports/smaip-feature-v3-smoke-r1.tar.gz`. The source SHA-256 is
`28cab08911171840e1f066c725dd23a788e6a9c64a132ec53bba22a5b3a21f94`;
the returned archive SHA-256 is
`850528f73d92d370728e48f0e824751e59e52ecb4bcb1d9ebda2fd7f9a4a6266`.
The auditor reported `verified`; the GPU's `scientific_smoke_pass` is **false**.

All 32 original development documents produced finite 2,048-dimensional
vectors for blocks 6, 18 and 30. The baseline token IDs were exact prefixes
of the assistant-boundary renderings for all 32. The first document's repeated
forward yielded identical vectors at every selected block/readout. No probe
was fitted and no threshold or detector quality was measured.

The absolute `0.02` causal-prefix tolerance failed for exactly two records:

| ID | Baseline → boundary tokens | Largest content-pool difference | Block/readout | Relative vector L2 difference |
| --- | ---: | ---: | --- | ---: |
| `dev01-test-1-05` | 96 → 99 | 0.0625 | 30/content-last | 0.003180 |
| `dev01-test-1-06` | 96 → 99 | 0.078125 | 30/content-last | 0.003321 |

Every other sampled rendering ended at 94 or fewer boundary tokens and had
zero saved content-pool difference. The two exceptions have identical prefix
token IDs and selected content positions. Their nonzero differences span many
coordinates and increase at later blocks. The relative changes are small,
but that does **not** turn the prespecified absolute-tolerance failure into a
pass. A GPU computation-shape effect at 96 → 99 tokens is a hypothesis, not
yet a verified explanation.

A focused 3-document diagnostic subsequently completed and was audited. Its
archive SHA-256 is
`caa21c14394f2a7e549ecbd13b460f9c92ce1d2480f0ca1c4f7fd1d20aa4a105`.
The nine forwards reproduced both original views with **zero** maximum
absolute difference. Replacing the three assistant-suffix token IDs while
keeping the full sequence at 99 tokens also produced **zero** difference in
all selected prefix vectors for both exceptions and the control. Comparing
the 96-token baseline with the 99-token view still produced the original
0.0625/0.078125 maxima. The model reported fp16 with SDPA attention.

This supports a sequence-length-dependent numerical calculation effect,
not a content effect from future assistant tokens at fixed length. It does not
identify which CUDA operation caused the rounding difference. The original
smoke's predeclared absolute-tolerance result remains **failed**; it is not
retroactively changed. Future candidate extraction should take content and
boundary readouts from one boundary rendering, fingerprint that view as a
new protocol, and treat historical V2 content-only vectors as a separate
baseline. See `docs/brd/FEATURE_V3_PREFIX_DIAGNOSTIC.md` for the retained
procedure and `.local-data/returned/feature-v3-prefix-diagnostic-01.audit.json`
for the verified result.

This is a rendering/numerics check only. The candidate corpus remains
unreviewed and unassigned; no new probe training or independent low-FPR
evaluation has happened.
