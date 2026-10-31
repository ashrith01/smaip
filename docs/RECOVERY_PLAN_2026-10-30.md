# SMAIP recovery and continuation — October 30, 2026

## BRD-level continuation plan

The subsequently supplied BRD v1.2 has now been read and mapped to the code. The full product completion roadmap is `docs/brd/BRD_ALIGNMENT_2026-10-30.md`. It keeps the probe-parity/data work below and adds unfinished BRD requirements: real hosted agent behavior, a single-agent baseline and true least-privilege ablations, TPR at 1% FPR, live HF/vLLM serving, joint cost/performance gates and release artifacts. Historical `LP-only` rows mean linear probe, not the BRD's structural least privilege.

## Current status after the returned GPU run

The manual GPU rescore has completed. Its archive is now in the repo and has been independently validated: unchanged probe artifacts, 55 matching source hashes, 57 matching document hashes/labels/splits, and all 12 episode aggregates verified. Week 5 trained/full-stack rows now complete all benign tasks; Week 6 mean pooling does too. Linear/full-stack retain one benign false positive (87.5% utility, 12.5% FPR). Fresh mean-pooled validation recall is 83.3% despite the copied training-time 100% metadata, due to a near-threshold score change. Test metrics still match. See `reports/WEEK7_RESCORE_ANALYSIS.md` for exact results, evidence limits, and the new ordered next steps. The manual transfer/run commands below are historical; they do not need repeating for the same rescore.

## Feature-parity diagnostic completed

The returned A16/fp16 diagnostic reproduces the earlier validation mismatch: batch-one collection exactly matches serving and the prior rescore, while batch-four changes the Ferry mean-pooled decision at its frozen boundary. All repeated paths are internally exact in these runs; tokens match and no input was truncated. Both probe files remain unchanged. `reports/WEEK7_PARITY_ANALYSIS.md` records the independently verified 342 vector rows/684 scores and the ordered next work: one shared feature protocol, corrected grouped dataset v2, then new fitting/calibration and independent evaluation.

## Where work stopped

The initial local checkout was clean on `main`, commit `9233cf9429b896778735f809d8d049b33109a27e`, matching the current remote main. Seven merged commits implement Weeks 1–7. Remote heads were checked during recovery; no later fix branch was present.

The linked [Cursor session](https://cursor.com/agents/bc-e01a3c15-ebfc-5a6d-b2cd-96e32a807aaf) is titled **SMAIP Week 7: commit trained probes + fix episode calibration**. Its UI reports an unexpected error after 14 minutes 13 seconds and **12 edited files, +486/−70**. The Changes panel says **No pushed changes**. Its workspace still contains the draft, which was exported there as `/workspace/cursor-recovery.patch` for preservation. The browser's download route was blocked by Chrome; the full diff was read from the file editor. This recovery reconstructs the useful changes locally and adds regression checks and measurement safeguards; it is not an unreviewed application of the draft.

The draft edited activation extraction, trained inference, benchmarking, gateway scoring, Week 5/6 callers, Week 7 rescoring, CLI, Makefile, GPU bootstrap, gitignore, and GPU documentation. It had not added tests, imported the GPU archive, committed, or pushed changes. Its main finding was that a probe trained on raw documents was also classifying generated digest arguments.

## What the repo contains

| Area | Location | Implemented state |
| --- | --- | --- |
| API and serving | `src/smaip/serving/` | FastAPI/OpenAI-compatible surface, authentication, rate/body limits, request IDs, redaction, metrics, cache; mock default, optional HF CPU, separate HF/vLLM benchmark |
| Agent workflow | `src/smaip/agents/` | LangGraph planner, reader, analyst, actor; mock vendor research/digest task, trusted fields, taint/provenance |
| Enforcement | `src/smaip/gateway/` | Role allowlists, schemas, approval tokens, arithmetic sandbox, protected audit file, in-memory side effects |
| Detectors | `src/smaip/probes/` | Context-aware keyword/encoding checks, phrase stubs, actual HF residual extraction, last/mean logistic probes, saved scalers and thresholds |
| Data and evaluation | `src/smaip/fixture_data/`, `src/smaip/eval/` | Original vendor/tool fixtures; six ablations; Week 1–6 deterministic gates; Week 7 training and episode integration |
| Operations | `Makefile`, `scripts/gpu/`, Docker files, `.github/workflows/ci.yml` | CPU CI, container build definition, single-GPU bootstrap, training/archive path, new rescore-only path |
| Research context | `PRIOR_ART.md`, `DATA.md`, `docs/ATTACK_TAXONOMY.md` | Prior work, original-data scope, attack families; external benchmark datasets are not vendored |

This is a working experimental scaffold, with real frozen-model probe training added in Week 7. The Qwen language model itself was not fine-tuned. The default agent analyst and its side effects are mocked. AgentDojo/InjecAgent/BIPIA integration and a real-model autonomous attack evaluation remain future work.

## GPU archive checked

Source: local `Downloads/week7-gpu-results.tar.gz`, 122,146 bytes. SHA-256:

`3d3d146592215820f827939f7208a4f1b4b906664c405825478bafb64c265996`

All five expected files were recovered. Both probes have 2,048 weights, means, and positive standard deviations; all checked values are finite. Their metrics match the evaluation JSON. Byte-for-byte originals and a hash manifest are saved under `reports/runs/week7-gpu-original/`. The former committed 0.5B CPU report is preserved at `reports/runs/week7-cpu-original.md`. The 3B files are also at the canonical `artifacts/probes/` and `reports/` paths.

| Property | Original GPU evidence |
| --- | --- |
| Backend/model/subset | HF, `Qwen/Qwen2.5-3B-Instruct`, CUDA, full |
| Corpus | 57 records: 33 injected, 24 benign |
| Split | 36 training, 11 validation, 10 test (test: 6 positive, 4 negative) |
| Linear | Last pooled, layer 20, threshold 0.3726051384960104; test AUROC 1.0, F1 0.9231, recall 1.0, FPR 0.25 |
| Activation | Mean pooled, layer 23, threshold 0.2796754800440131; test AUROC 1.0, F1 1.0, recall 1.0, FPR 0.0 |
| Episode failure | LP-only, probe-only, full-stack: utility 0, FPR 1 on both suites; all report ASR 0 |
| Other rows | Keyword: utility 1/FPR 0, ASR 0.10 on Week 5 and 0.25 on Week 6. Gateway-only: utility 1/FPR 0/ASR 0 |
| Benchmark | `skipped: false`; CUDA and vLLM ran at concurrency 1/4/8. Performance interpretation is limited by the old timing/cache protocol |

The session prompt identifies the rental as an NVIDIA A16 16 GB. The archive does not independently record hardware, package versions, base-model revision, or code revision. Its timestamp and file structure are consistent with the downloaded run, but local checks do not independently rerun the GPU model.

The tarball contains logistic probe parameters, not the 3B base checkpoint. The source code saved only an activation summary, not raw vectors. The full record-level test is only ten examples, so the AUROC values do not establish broad generalization.

## Local continuation completed

Work is on local branch `codex/week7-recovery`; it is uncommitted and unpushed.

- Restored the actual GPU probes and original results, with source hashes and separate baseline copies.
- Trained probes now score each raw source document separately. Generated digest arguments no longer become out-of-distribution probe inputs. A derived send/write checks the original read sources, preserving source-based blocking. Keyword/phrase defenses retain their previous argument scans.
- Multi-page follow-up calls pass the original page boundaries instead of only concatenated pages. The keyword screen can still join fragments across documents.
- Both trained probes share a bounded residual cache and loaded model keyed by model/device/dtype. CPU rescoring can use CUDA-trained artifacts without editing them, preserving collection precision. Exact cross-device feature parity is not assumed.
- Ablation rows clear text caches independently. Trace logging reads existing trained scores and does not perform new model forwards outside the timer. The overhead benchmark now clears text caches per request and preloads the model; the original benchmark JSON remains unchanged historical evidence.
- Added `week7-rescore` CLI/Make target. It reuses weights/thresholds, writes separate rescore outputs, records artifact/source hashes, runtime versions, configuration, and per-document scores. It does not train or install vLLM.
- CPU smoke writes to `reports/smoke/` and `artifacts/smoke/`, protecting the saved GPU artifacts.
- GPU bootstrap handles Ubuntu 22.04's Python 3.10/missing-venv issue and preserves/defaults a single-card `CUDA_VISIBLE_DEVICES` selection. It was syntax-checked locally, not executed on Ubuntu.

Local verification: baseline 157 passed/2 skipped; recovered version 164 passed/2 skipped. `make week6` ran all earlier evaluation gates successfully, using the already installed development environment (`-o install`). The Week 7 mock smoke passed with the same install skip. The optional HF tests remained skipped. No 3B model was downloaded or executed locally, no Docker build was performed, and no cloud or GitHub state was changed except creating the local branch and preserving a patch file on the Cursor workspace. Canonical GPU file hashes remained unchanged after smoke validation.

## Manual GPU run — completed; historical instructions

The owner confirmed the rental is still running and chose to run commands manually. Host supplied: `root@45.63.76.130`. No SSH connection was attempted by this recovery.

A standalone bundle is generated as `reports/week7-recovery-source.tar.gz`. It contains the recovery source, tests, configuration, documentation, original GPU probes/results, and a bundle hash manifest. It excludes `.git`, local virtual environments, caches, and secrets. It extracts into a new `smaip-week7-recovery/` directory and does not overwrite the old checkout.

From the Mac:

```bash
scp "/Users/ashrithvadde/Documents/GitHub/smaip/reports/week7-recovery-source.tar.gz" root@45.63.76.130:/root/
ssh root@45.63.76.130
```

On the GPU:

```bash
test ! -e /root/smaip-week7-recovery || { echo "Recovery directory already exists; choose a fresh directory first."; exit 1; }
tar -xzf /root/week7-recovery-source.tar.gz -C /root
# Activate the SAME Python environment used by the completed training run.
# If its path differs, substitute that existing path here.
source /root/smaip/.venv/bin/activate
cd /root/smaip-week7-recovery
CUDA_VISIBLE_DEVICES=0 SMAIP_PROBE_DEVICE=cuda bash scripts/gpu/rescore.sh
```

The script uses `PYTHONPATH` to run this source with that environment. It installs nothing and defaults to `HF_HUB_OFFLINE=1`; the previously downloaded Qwen cache must be visible. If the old run used a custom `HF_HOME`/`HF_HUB_CACHE`, export the same values first. If offline loading fails, first check that cache path rather than starting another training run. A missing dependency should be resolved in the existing environment with the repo's declared `hf` requirements; do not run bootstrap or reinstall vLLM for this rescore.

After success, from the Mac:

```bash
scp root@45.63.76.130:/root/smaip-week7-recovery/reports/week7-rescore-results.tar.gz "/Users/ashrithvadde/Documents/GitHub/smaip/reports/"
```

The result tarball contains `week7_rescore.json` and `RESULTS_week7_rescore.md`, including the unchanged-probe hashes and source-score diagnostics. That file has now been returned and analyzed; see `reports/WEEK7_RESCORE_ANALYSIS.md`. Keep the original GPU archive and returned rescore archive as separate evidence.

## Next decisions after the rescore

1. Inspect every benign source score and the benign episode utility/FPR. If raw benign pages still cross the frozen thresholds, document those failures. Do not tune thresholds against these evaluation episodes. First separate remaining page-level false positives from the corrected digest mismatch.
2. Freeze an independent, grouped train/calibration/test manifest. Keep vendors, templates, related multi-page records, and near-duplicates together. Remove the class-specific “End of dossier.” versus “record” fixture cues. Annotate page injection separately from poisoned-vendor/episode labels.
3. Report achieved recall and confusion counts at the frozen validation threshold; rename the ambiguous test `fpr_at_tpr` label. Add larger unseen-vendor episodes, shortcut/counterfactual tests, and uncertainty intervals before claiming a robust detector. The current episode tests overlap training pages.
4. Pin/save base-model and tokenizer revisions, chat-template/truncation configuration, corpus hashes, runtime versions, raw activations or per-record vectors, and event traces. Verify real batch-versus-single embedding parity and layer semantics on a small run before another full training run.
5. Redesign the serving benchmark before drawing HF/vLLM latency or speedup conclusions: correct token counting, padding, missing-metric fallback, repeated measurements, and explicit cache/warmup conditions. The original fast full-stack row is not evidence of negligible defense cost.
6. Review the validated recovery diff, commit/push it, and open a PR. CI must stay CPU/mock. Real-model agent susceptibility and external benchmarks should be a separate phase with sandboxed actions.

The detailed baseline research audit is in `reports/EXPERIMENT_AUDIT_2026-10-30.md`. It records the remaining measurement/design limits and source references at the original commit.
