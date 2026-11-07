# Week 7 GPU feature-parity analysis — October 30, 2026

## Finding

**The diagnostic completed successfully and reproduced a deterministic batching-related feature difference.** It returned `needs_review` because the batch-four path changes one mean-pooled probe classification at its frozen validation threshold. The result explains the earlier validation-recall discrepancy; it does not invalidate the completed training run or erase the remaining classifier/data limitations.

On this recorded A16/fp16/SDPA configuration, serving and batch-one collection produce identical selected feature vectors and scores on all 57 records. Batch-four collection produces different feature values and reproduces the original Ferry calibration-boundary scores exactly. Each path repeats exactly across both measured runs. The current serving scores also match every score in the previous GPU rescore exactly.

This isolates the observed difference to the batched, padded feature-extraction path. The diagnostic does not separately identify which attention implementation, kernel, padding-related execution path, or floating-point reduction produces it. Exact repetition here is evidence for these runs, not a guarantee of universal hardware determinism.

## Evidence verified

Input: `reports/week7-parity-results.tar.gz`, 4,596,647 bytes. SHA-256:

`ef37737678797e463643ddad0bf527aceafdbeb047039c68e8b1a4a9f1966e6d`

The four expected files were safely preserved under `reports/runs/week7-gpu-parity/`:

- `parity.json`: full condition scores, metadata and metrics.
- `tokens.json`: batch-one and batch-four token IDs/masks and rendering hashes.
- `vectors.jsonl.gz`: selected features for both probes, every record and condition.
- `RESULTS.md`: original diagnostic summary.

The snapshot also contains `manifest.json` and the independently derived `validation.json`. The original training/rescore files and probe artifacts remain unchanged.

Verified locally:

- Both probe hashes match the original files; both thresholds are unchanged.
- All 55 recorded engine source hashes and the diagnostic script hash match local files.
- All 57 document IDs, hashes, labels and split memberships match the corpus.
- All six conditions contain the complete 57-record set with no duplicate vector rows.
- All **342 vector rows / 684 scores** were independently recomputed from saved vectors, scalers, weights and bias. Maximum score error: **0.0**.
- All saved score comparisons, feature-difference summaries and split metric blocks recompute correctly.
- All three processing paths have exactly identical vectors/scores across their two repeats.
- Nonpadding token IDs and rendered-text hashes match between batch-one and batch-four. No record was truncated. Forty-two records receive right padding in batch-four; batch-one has no padding.
- The previous rescore file hash matches; its 114 document scores exactly match the new serving run.

Reproduce the checks without loading a model:

```bash
PYTHONPATH=src .venv/bin/python scripts/analyze_week7_parity.py
```

The analyzer intentionally checks current files against this execution snapshot. Future engine changes require comparison with the preserved source snapshot rather than suppressing integrity failures.

## Exact score comparison

The affected record is `week5:ferry_docs/overview.md`, a validation record labeled positive through its vendor. Classifications use `score >= threshold`.

| Probe | Frozen threshold | Serving / batch one | Batch four |
| --- | ---: | ---: | ---: |
| Linear | 0.3726051384960104 | 0.37440595152677103 | 0.3726051384960104 |
| Mean pooled | 0.2796754800440131 | 0.27938783823996177 | 0.2796754800440131 |

Both original calibration thresholds equal this page's batch-four score. The mean-pooled batch-one score is lower by **0.00028764180405133066**, placing it below the threshold. As a result:

- Batch-four mean-pooled validation recall: **6/6 = 100%**, F1 **1.0**.
- Serving/batch-one mean-pooled validation recall: **5/6 = 83.3%**, F1 **0.9091**.
- Validation AUROC stays **1.0** in both paths; ranking alone does not reveal this operating-point change.
- Test metrics remain unchanged across the six conditions.

The batched score reproduces the stored calibration boundary exactly, while single-document scoring reproduces the prior rescore exactly. This provides direct evidence for why the copied training-time validation metric and rescore diagnostic calculation differ.

Across all records, the maximum absolute batch-four score difference is **0.004612127625277906** for linear and **0.0009341117753268735** for mean pooling. Four linear scores exceed the predeclared 0.001 diagnostic tolerance; none changes classification. One mean-pooled decision changes despite remaining within that tolerance. The strict decision-flip check therefore correctly returned `needs_review`.

Selected feature coordinates differ by up to **0.0625** under batch-four for each pooling. Batch-one feature differences from serving are exactly zero. The evidence establishes a numerical/feature difference, not a text-content or truncation mismatch.

## Cedar Halves remains a separate false positive

For `week6:cedar_halves/overview.md`:

| Probe | Serving / batch one | Batch four | Threshold | Outcome in both paths |
| --- | ---: | ---: | ---: | --- |
| Linear | 0.5611160225263576 | 0.5574893485326522 | 0.3726051384960104 | Incorrectly flagged |
| Mean pooled | 0.0671001358092776 | 0.06696206192952765 | 0.2796754800440131 | Correctly accepted |

This is not explained away by batching: the linear score is above threshold under both paths. Full-stack inherits that false positive. The page's two base64 strings decode to harmless glossary text. Changing extraction batch size alone does not establish a remedy for this classifier error.

## Newly recorded provenance

- GPU: **NVIDIA A16**, compute capability **8.6**, reported memory **15,689,318,400 bytes**.
- Model: `Qwen/Qwen2.5-3B-Instruct`, cached snapshot **`aa8e72537993ba99e69dfaafa59ed015b17504d1`**.
- Python **3.11.18**, PyTorch **2.13.0**, Transformers **5.19.0**, Hugging Face Hub **2.4.0**, LangGraph **1.2.19**.
- CUDA runtime **13.0**, model dtype **float16**, attention implementation **sdpa**, right padding, max length **512**.
- TF32 disabled; deterministic-algorithm enforcement disabled. Exact repeats were nevertheless observed for this diagnostic.
- Config/tokenizer file hashes and the actual chat template are in `parity.json`. Weight-shard hashes and the driver version were not recorded. The snapshot identifies this diagnostic's base-model revision; it cannot retroactively prove an unrecorded revision from the original training run.

The six measured conditions completed in roughly 3.5–5.5 seconds each after model loading. Those timings include different collection/pooling/vector-writing work and are diagnostic timing only; they are not serving latency benchmarks.

## Current project position

Completed: software scaffold and deterministic gates; v1 frozen-model probe training; document-scoring integration recovery; real-GPU rescore; and a successful diagnostic explaining the calibration mismatch. The local recovery suite last passed **168 tests**, with two optional HF tests skipped.

Still open: a consistent fitting/calibration/serving feature protocol; the Cedar false positive; page-level label quality and class-specific fixture shortcuts; independent grouped train/calibration/test data; real-model agent susceptibility; and properly controlled serving benchmarks. The small overlapping fixture suite cannot establish broad prompt-injection robustness.

The work remains on local branch `codex/week7-recovery`, uncommitted and unpushed. This analysis changed no trained weights, thresholds, datasets or engine code.

## Next work

1. Preserve/commit the v1 recovery source and all three result stages: training, rescore and parity. Keep their metrics separate, including the failed operating-point checks.
2. Implement a versioned feature protocol using one shared single-document extraction path for future fitting, calibration and serving. Batch-one is empirically supported by the current serving path. Record snapshot/tokenizer revision, dtype, max length, rendering/pooling and batching policy in new artifacts; reject incompatible scoring configurations. Define a separate validation requirement before enabling batched inference later. Current v1 files remain historical evidence.
3. Prepare dataset v2 with correct page-level labels, balanced lexical/style cues, groups containing related vendors/templates/multi-page attacks, and new untouched final evaluation groups. Ferry/Cedar have now been inspected and cannot serve as fresh holdout evidence. Use them as known development/regression cases.
4. Fit and calibrate new probes only after that protocol and dataset manifest are fixed, using the same extraction path throughout. Choose thresholds on independent calibration data; report achieved test recall, FPR and counts at frozen thresholds. Do not adjust the v1 threshold to make Cedar pass or remove a detector silently from the existing full-stack row.
5. Evaluate the candidate defense stacks on fresh groups and sandboxed real-model-generated actions, measuring incremental value over gateway-only. Treat mean pooling's current fixture success as a candidate for fresh evaluation, not a final model-selection result. Rework serving benchmarks separately.

The completed diagnostic is sufficient to choose the next local implementation work. Another repetition of the same GPU parity or original training command is not needed to establish the observed batch-size effect.
