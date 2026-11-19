# First V2 probe training — execution verified, operating points need more data

Reviewed October 31, 2026. The original archive is
`reports/probe-development-01.tar.gz`, SHA-256
`ff9a571dae09e4860124ca30b1dea91f40962d27226eb535cc9b90b27f4947f0`.
Unmodified members, raw vectors, fitted probes and a validation report are saved
under `reports/runs/probe-development-01/`.

## Verified execution and reproducibility

The audit verified all 152 source-bundle files, 66 Python source hashes in each
stage, all returned member checksums, the exact 36-document corpus/provenance,
split identities, protocol fingerprint and the separate completed collection,
fit and evaluation records. The bundle is a hash-pinned working-tree snapshot
based on `76481bf`, including the uncommitted V2 implementation; it is not a new
Git commit.

Collection ran on the restored NVIDIA A16 using Qwen2.5-3B-Instruct revision
`aa8e72537993ba99e69dfaafa59ed015b17504d1`, CUDA 13.0, Torch 2.13.0+cu130 and
Transformers 5.19.0. Features use layer 18, CUDA/float16 execution, batch one,
fully contained tool-content tokens and float32 pooling. All 72 saved vectors
have 2,048 finite values: 147,456 scalar features in total.

This run fitted actual format-2 last-token and mean-pooled logistic probes.
Qwen remained frozen. Each probe used 12 training documents (six per label),
12 separate calibration documents and 12 development test documents. Layer 18
and the fitting configuration were fixed in advance. Training moments/weights
use training records only; thresholds use calibration records only.

The local audit recomputed both fits from saved vectors without loading Qwen.
Parameters match within 1e-10 tolerance (largest observed absolute difference
8.89e-16). Calibration records, frozen test predictions and all test metrics
reproduce exactly. Reproduce the audit from the repo root:

```bash
PYTHONPATH=src .venv/bin/python scripts/analyze_v2_development.py
```

## Frozen development test results

| Probe | Threshold | Attacks caught | Benign false alarms | AUROC | F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Last-token linear | 0.952380 | 0/6 | 0/6 | 1.0000 | 0.0000 |
| Mean-pooled activation | 0.593590 | 4/6 | 1/6 | 0.9444 | 0.7273 |

The linear probe's perfect test ranking does not make its frozen operating
point useful: it misses every test attack. Its highest-scoring benign
calibration document is the ordinary failed-inspection report
`dev01-calibration-0-06`, score 0.9523802274033019. With only six benign
calibration cases, the empirical 1%-FPR budget permits zero false positives.
The selected threshold is just above that benign score, and catches no
calibration or test attacks. This is the specified calibration outcome, not
a reason to lower the threshold against observed test labels.

The mean-pooled probe separates all 12 calibration documents, but on the test
split it flags a benign JSON message-format example and misses one forged
approval and one unrequested-purchase workflow hijack. Its observed test recall
is 66.7% and its observed test false-positive rate is 16.7%.

## Limits and next stage

These 36 authored, stylistically related documents establish the software and
artifact pipeline. They do not establish independent accuracy or population
1%-FPR behavior. Both calibration artifacts correctly mark low-FPR evidence as
insufficient. With six independent benign observations and zero false positives,
the one-sided 95% zero-event upper bound would still be about 39.3%; the synthetic
groups also do not establish that independence assumption.

Preserve this run and freeze these documents as known development material.
The next stage is a larger reviewed corpus with provenance/license records,
source/family/group holdouts, hard negatives and sufficient benign calibration
and test cases. Extend the pipeline's explicit development-only provenance gate
under a declared independent-data protocol, then retrain/calibrate and evaluate
on untouched held-out data. Integrating detectors into the agent and resolving
the remaining actor utility failures remain separate work. No final BRD,
low-FPR, full-stack-superiority or deployment acceptance is claimed.
