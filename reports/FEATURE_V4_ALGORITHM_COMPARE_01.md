# Feature V4 algorithm comparison 01

This local CPU experiment compared the saved V4 logistic baseline with a
pair-difference linear probe motivated by the paired clean/injected structure.
The second method learned a direction from 227 NVIDIA attack-minus-clean vector
pairs; the same fixed `content_mean/18` feature, cleaned 968-row manifest,
source labels, and grouped NVIDIA folds were used. The implementation is
`scripts/compare_feature_v4_probe_algorithms.py`. The private summary is
`.local-data/feature-v4-algorithm-compare-01/summary.json`, SHA-256
`28fbf1db3014775bf357ba340e7266ce2b9219a3461f3edc7b13f3dab805fa22`.

The NVIDIA positives come from a fully synthetic, LLM-generated tool-use
dataset; local benign controls are made by deleting the annotated attack span.
LLMail positives are human attacker submissions to a simulated email-agent
challenge; benign items are the challenge's separate false-positive emails.
The local cleaned set contains 680 NVIDIA rows and 288 LLMail rows after 43
LLMail exact duplicate references and one disputed NVIDIA row were excluded.
Neither source provides accepted human truth for this project's task-relative
instruction label.

| Method | NVIDIA grouped out-of-fold AUROC | NVIDIA paired order | Observed LLMail transfer AUROC |
| --- | ---: | ---: | ---: |
| Existing regularized logistic | 1.000000 | 227/227 | 1.000000 |
| Paired-difference logistic | 0.999971 | 227/227 | 1.000000 |

**Decision:** retain the existing saved logistic probe. The paired alternative
did not improve the already saturated observed ranking and had a negative
minimum-attack/maximum-benign separation gap on NVIDIA out-of-fold scores.
The LLMail transfer dataset has connected attacker lineage; its AUROC is an
observed development diagnostic, not independent confirmation. The two
methods' raw score gaps have different scales and should not be compared as
calibrated margins. No threshold or model was selected from this comparison.

The relevant paper method is TaskTracker's *task-only versus task-plus-external-
data activation delta*. Our paired **example** differences are a cheaper,
distinct test and do not implement TaskTracker's task-state delta. The saved
archive contains only task-plus-document views; a genuine task-only delta
would require new pinned Qwen inference and a versioned collection. See
`docs/brd/research/FEATURE_V4_PROBE_PAPERS_2026-11-07.md` for primary sources
and dataset provenance.

Reproduce the comparison from pinned local vectors with
`.venv/bin/python scripts/compare_feature_v4_probe_algorithms.py --verify-only`.
This experiment neither tests new raw documents nor establishes agent defense,
low-FPR operation, or final detector accuracy.
