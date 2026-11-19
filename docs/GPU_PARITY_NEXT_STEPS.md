# Next manual GPU step: feature parity

## Diagnostic completed

The GPU archive has been returned and verified. Serving and batch-one vectors/scores match exactly; batch-four reproduces the Ferry threshold crossing in both repeats. The diagnostic completed with `needs_review` as designed. No token mismatch or truncation occurred. See `reports/archive/WEEK7_PARITY_ANALYSIS.md` for the evidence and next local implementation/data work. The GPU commands below are retained as historical instructions and do not need repeating for the same check.

## Current project position

The project is at **Week 7 validation**, following completed frozen-Qwen probe training and a completed real-GPU integration rescore. Qwen itself has not been fine-tuned. The repo contains the agent/API/gateway scaffold, deterministic attack suites, trained linear and mean-pooled logistic probes, and the recovery/evaluation tooling.

Verified current results:

- Week 5: both probes and full-stack complete 4/4 benign tasks and block 10/10 scripted attack side effects.
- Week 6: mean pooling completes 8/8 benign tasks and blocks 8/8 scripted attack side effects. Linear/full-stack complete 7/8 benign tasks; both incorrectly block Cedar Halves. They also block 8/8 scripted attacks.
- Fresh test metrics match the original training artifact values. One near-threshold Ferry page changes the mean-pooled validation recall from the stored 100% to 83.3% under rescore inference.
- Dataset independence, page-label quality, numerical parity, real-model agent evaluation and credible serving benchmarks remain unfinished. Recovery/evidence changes are local on `codex/week7-recovery`, uncommitted/unpushed.

See `reports/archive/WEEK7_RESCORE_ANALYSIS.md` for the complete evidence and limitations.

## What this diagnostic does

The new `scripts/gpu/probe_parity.py` uses the existing probe files and already-cached Qwen snapshot. It compares:

1. Actual `TrainedProbe.score` serving inference, one document at a time.
2. The training collection path with batch size 1.
3. The training collection path with batch size 4, matching the original default.

Each condition runs twice on all 57 current records, with text caches cleared between conditions. It reuses the model, does not fit weights, does not move thresholds, and writes to a separate output directory. The selected layers are 20 and 23; this is not an all-layer sweep or another training job. Serving inference currently pools all layers internally; the saved vectors include only the two selected probe features.

The script resolves the existing cached snapshot in offline mode and uses that immutable local snapshot path for every condition. It records the snapshot directory/revision, config/tokenizer hashes, runtime/GPU details, model dtype/attention configuration, chat template, token IDs/masks, padding/truncation information, source/probe hashes, selected feature vectors and scores. This pins the current diagnostic; it cannot retroactively prove which unrecorded model revision the original training used.

The predeclared diagnostic rule is: identical unpadded tokens/rendering, no threshold decision flips, and maximum score difference <=0.001 across conditions/repeats. The tolerance is a practical investigation screen, not a statistical guarantee. **Any threshold flip requires review even when its score difference is below 0.001.** The script does not fix a failure by changing thresholds. If the previous `reports/week7_rescore.json` is present, it also verifies its probe hashes and compares the new serving scores with that prior run, recording any runtime or score differences.

Local verification: shell syntax and Python compilation checked; four targeted tests passed, including the case where a tiny score difference crosses a threshold. A mock end-to-end run exercises all six conditions without changing artifacts. The real GPU run has since completed; its verified analysis is in `reports/archive/WEEK7_PARITY_ANALYSIS.md`.

## 1. Upload the two new scripts from the Mac

Run in a **Mac Terminal**:

```bash
cd /Users/ashrithvadde/Documents/GitHub/smaip
scp scripts/gpu/probe_parity.py scripts/gpu/parity.sh root@45.63.76.130:/root/smaip-week7-recovery/scripts/gpu/
```

These scripts use the existing recovery checkout that completed the previous rescore. No `git pull`, package reinstall, bootstrap, or new training command is needed for this diagnostic.

## 2. SSH into the same GPU and activate its existing environment

```bash
ssh root@45.63.76.130
source /root/smaip/.venv/bin/activate
cd /root/smaip-week7-recovery
nvidia-smi
```

If your previous successful run used a different virtual-environment path, activate that same environment instead. If it used custom `HF_HOME` or `HF_HUB_CACHE`, export those same values before the diagnostic. Do not change package versions between the rescore and this check.

## 3. Run the diagnostic

```bash
CUDA_VISIBLE_DEVICES=0 bash scripts/gpu/parity.sh
```

The wrapper forces offline model access, uses the currently activated `python`, and loads the cached fp16 model on CUDA. It writes only new diagnostic outputs. Runtime has not been measured on the rental; wait for all six conditions and the final archive message. It will print progress such as `Running serving_repeat1` and `Running batch4_repeat2`.

A successfully completed diagnostic prints either `parity_screen_passed` or `needs_review`. Both are valid completed outcomes; the second means numerical or token differences need analysis. It then creates:

```text
/root/smaip-week7-recovery/reports/week7-parity-results.tar.gz
```

If the cached snapshot cannot be found, check the existing HF cache path. If an output already exists from an attempted run, preserve it and choose new paths rather than overwriting it:

```bash
SMAIP_PARITY_OUTPUT=reports/week7-parity-run2 \
SMAIP_PARITY_ARCHIVE=reports/week7-parity-results-run2.tar.gz \
CUDA_VISIBLE_DEVICES=0 bash scripts/gpu/parity.sh
```

A Python traceback or missing completion/archive message means execution failed; return the error text for diagnosis rather than rerunning training. If the host changes, substitute its current SSH address in the transfer commands.

## 4. Copy the archive back from a Mac Terminal

Leave the GPU terminal as-is and open a **second Mac Terminal window**:

```bash
scp root@45.63.76.130:/root/smaip-week7-recovery/reports/week7-parity-results.tar.gz "/Users/ashrithvadde/Documents/GitHub/smaip/reports/"
```

If you used the alternate run-2 paths, copy that archive instead. Tell this chat when the archive is in the repo. Preserve the earlier training and rescore archives too.

## 5. What happens after the diagnostic

- If decision flips or meaningful drift appear, inspect the saved vectors/tokens to isolate batching, padding, precision, reduction or runtime differences. Define one consistent extraction path for future fitting/calibration/serving and test it before another fit.
- If parity passes, the earlier mismatch still needs explanation against the recorded prior scores; a new passing screen does not erase the historical discrepancy. Verify the snapshot/runtime and the near-threshold page first.
- Keep Cedar Halves as a known v1 false positive. Do not tune the old threshold on it or add a fixture-specific exception.
- Freeze the v1 recovery/evidence in version control. Build dataset v2 with corrected per-page labels, balanced wording, independent grouped splits and a new untouched holdout.
- Train/calibrate on v2 only after the extraction protocol and data manifest are fixed. Then measure independent accuracy and the incremental value over the gateway, followed by sandboxed real-model agent evaluation and redesigned serving benchmarks.

The immediate action is this diagnostic. Another unchanged `make week7-gpu` run would not establish feature parity or dataset independence.
