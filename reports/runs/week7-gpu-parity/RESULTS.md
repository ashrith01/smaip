# Saved-probe feature parity diagnostic

Status: **needs_review**. Backend `hf`; device `cuda`.

Exact nonpadding token/render match; no decision flips; all score differences <= tolerance across serving, batch sizes and repeats. Tolerance is an engineering diagnostic, not a guarantee of detector quality.

Probe hashes verified unchanged. No retraining or threshold fitting occurred.

| Condition | Probe | Max absolute score difference | Decision flips | Scores beyond tolerance |
| --- | --- | ---: | ---: | ---: |
| serving_repeat1 | linear | 0.00000000 | 0 | 0 |
| serving_repeat1 | activation | 0.00000000 | 0 | 0 |
| batch1_repeat1 | linear | 0.00000000 | 0 | 0 |
| batch1_repeat1 | activation | 0.00000000 | 0 | 0 |
| batch4_repeat1 | linear | 0.00461213 | 0 | 4 |
| batch4_repeat1 | activation | 0.00093411 | 1 | 0 |
| serving_repeat2 | linear | 0.00000000 | 0 | 0 |
| serving_repeat2 | activation | 0.00000000 | 0 | 0 |
| batch1_repeat2 | linear | 0.00000000 | 0 | 0 |
| batch1_repeat2 | activation | 0.00000000 | 0 | 0 |
| batch4_repeat2 | linear | 0.00461213 | 0 | 4 |
| batch4_repeat2 | activation | 0.00093411 | 1 | 0 |
| Prior rescore vs new serving | linear | 0.00000000 | 0 | 0 |
| Prior rescore vs new serving | activation | 0.00000000 | 0 | 0 |

Nonpadding token/render mismatches: 0.

Diagnostic only. No fitting or threshold changes. Passing parity does not validate data independence or generalization.
