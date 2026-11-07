# Feature V4 solo probe fit 01

On 2026-11-07, `scripts/train_feature_v4_solo_probe.py` fitted and saved a small
linear injection probe on the archived V4 feature vectors using the local Mac.
The base Qwen/Qwen2.5-3B-Instruct model stayed frozen; its collection revision
was `aa8e72537993ba99e69dfaafa59ed015b17504d1`. This run did not require
the model snapshot, a GPU, or new feature extraction.

The fixed input was `content_mean/18` from the previously selected V4 protocol.
The cleaned manifest excluded the disputed `R031` row (`nvidia-12-clean`) and
43 exact duplicate references. A deterministic logistic probe used 680 NVIDIA
rows (228 source-labeled attacks, 452 source-labeled controls) for fitting.
It scored 288 LLMail rows (128 source-labeled attacks, 160 benign emails) as
an already observed source-transfer diagnostic. The 300-step fit used the
same training-only normalization and L2 setting as the sensitivity analysis.

The private outputs are:

| Artifact | SHA-256 |
| --- | --- |
| `.local-data/feature-v4-solo-probe-01/model.json` | `6a6d2bd79f3a731282efe4084f33e7851c92959ad5e65e13418e996be42c1b1c` |
| `.local-data/feature-v4-solo-probe-01/predictions.jsonl` | `b3d98caa77ed4e31b44190dc21794f2211c11a36e2dcec6257649d7f07eda594` |
| `.local-data/feature-v4-solo-probe-01/summary.json` | Contains the artifact hashes and protocol limits. |

The saved model reproduced all 968 saved scores exactly when reloaded against
the archived vectors (`max_abs_score_error = 0.0`). The observed LLMail
source-label AUROC was 1.0000, with a minimum attack versus maximum benign
score gap of 0.1617. The NVIDIA grouped out-of-fold AUROC of 1.0000 is copied
from the prior fixed-feature sensitivity report; it was not rerun here.
The saved NVIDIA scores themselves are in-sample. Run
`.venv/bin/python scripts/train_feature_v4_solo_probe.py --verify-only` to
recheck the saved artifact against the pinned local inputs.

This is a **development artifact**, not a validated detector. The labels are
source-provided, both datasets and this feature had already been observed, and
the LLMail attacks share lineage. No independent final test, operating
threshold, 1%-FPR estimate, or real-agent defense result was established.
`threshold` is null and `serving_enabled` is false. The JSON weights cannot
score a new raw document without the pinned feature extractor.
