# Feature V4 cleaned-label sensitivity 01

The fixed `content_mean/18` feature was refit from the saved 1,012-row V4
vector archive after excluding the disputed `R031` row and 43 exact duplicate
references. The cleaned audit manifest provided the 968 canonical candidate
IDs: 680 NVIDIA rows (228 source-labeled attacks, 452 controls) and 288 LLMail
rows (128 source-labeled attacks, 160 benign emails). The script is
`scripts/analyze_feature_v4_solo_sensitivity.py`; the private result is
`.local-data/feature-v4-solo-sensitivity-01/summary.json` (SHA-256
`60aa46bdaf0161f63679fa554aeb37d0c238bec5d3c3cb816c89f7b1bf49073d`).

The feature, regularization, and three-fold grouped NVIDIA procedure were
held fixed from the already observed exploratory fit. No feature search,
threshold selection, model serving, GPU inference, or new labels occurred.
The NVIDIA fit used source labels only; LLMail was scored as a source-transfer
development diagnostic.

| Ranking on the same cleaned rows | Old saved scores | New cleaned refit |
| --- | ---: | ---: |
| NVIDIA grouped out-of-fold AUROC | 1.0000 | 1.0000 |
| NVIDIA min attack minus max benign score | 0.3208 | 0.3279 |
| LLMail transfer AUROC | 1.0000 | 1.0000 |
| LLMail min attack minus max benign score | 0.1526 | 0.1617 |

The maximum per-row score changes were 0.0706 on NVIDIA out-of-fold scores
and 0.0193 on LLMail transfer scores. Removing the known row and exact
duplicates did not remove the observed separation against these source
labels. The numerical gaps are model-score units, not calibrated probabilities
or deployment margins.

This result does **not** establish semantic injection detection or 1%-FPR
performance. The feature and both sources were already observed, the source
labels are not accepted human truth, NVIDIA controls are synthetic
span-deletion cases, and all LLMail attacks share a connected lineage.
`R031` remains excluded; the exploratory model is not promoted.
