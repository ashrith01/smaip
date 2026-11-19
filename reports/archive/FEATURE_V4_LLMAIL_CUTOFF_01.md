# V4 probe on Microsoft LLMail examples: observed cutoff diagnostic

The saved V4 model was fitted on 680 cleaned NVIDIA examples. This local CPU
check applied it to the 288 already scored Microsoft LLMail examples: 128
source-labeled attacks and 160 benign challenge emails. The model's 968 saved
predictions were verified against its archived vectors before counting outcomes.

The **diagnostic** cutoff was the midpoint between the maximum benign score
(`0.05627950228442556`) and minimum attack score (`0.9040907088128125`) on
the NVIDIA **training** rows only: `0.48018510554861904`. The LLMail scores
did not enter this numerical formula. The feature, model and LLMail source had
already been examined earlier, so this is not a prospective or independent
test. The saved model still has `threshold: null` and `serving_enabled: false`.

| LLMail source label | Flagged by diagnostic cutoff | Not flagged |
| --- | ---: | ---: |
| Attack | **125** | **3** |
| Benign | **0** | **160** |

On these source labels, the observed attack recall was **125/128 = 97.66%**;
the observed benign false-positive rate was **0/160 = 0%**. AUROC remained
**1.0** because every labeled attack scored above every benign email. AUROC
measures ordering across all possible cutoffs; the fixed cutoff still missed
three attacks whose scores were above benign scores but below `0.480185`.
The saved private summary lists the three missed candidate IDs for manual
inspection. A score is not a calibrated probability.

This experiment does **not** measure whether an agent followed or resisted any
email instruction. LLMail attack submissions share connected lineage; source
labels have not become accepted human truth for SMAIP's task-relative label.
The sample does not support a population 1%-FPR or deployment claim. No cutoff
was added to the serving model.

Reproduce with `.venv/bin/python scripts/evaluate_feature_v4_llmail_transfer.py --verify-only`. The script is
`scripts/evaluate_feature_v4_llmail_transfer.py`; the private result is
`.local-data/feature-v4-llmail-cutoff-01/summary.json`, SHA-256
`315904c54076f355abd13dc57ab56629cdc55c487071f7b82c10eda1d3975629`.
