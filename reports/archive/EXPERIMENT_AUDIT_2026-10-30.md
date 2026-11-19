# Week 7 experiment audit — 2026-10-30

## Baseline snapshot

This audit refers to commit `9233cf9429b896778735f809d8d049b33109a27e` before the parent recovered GPU files or resumed code edits. Its line references describe that baseline. The former committed CPU report is now preserved at `reports/runs/week7-cpu-original.md`. Current recovery status, verified GPU results, implemented fixes, and pending work are in `docs/archive/RECOVERY_PLAN_2026-10-30.md`. In particular, the later parent changes address the immediate document-scoring, cache, portability, and rescore issues; generalization concerns remain.

## Scope and conclusion

Read-only code, fixture, test, and existing-report inspection; this findings file is the only authored change. No model was downloaded, trained, or run. No applicable `AGENTS.md` was found in the repository root or its ancestor directories. References below are repository-relative `file:line` locations at inspection time.

Week 7 implements a real Hugging Face feature-extraction path and trains logistic classifiers over those features. The committed result reports **Qwen2.5-0.5B-Instruct on CPU, tiny subset**, not a completed 3B/GPU experiment. Its results already show that validation success did not transfer: the last-token probe has test F1 0; the mean-pooled probe has test AUROC 0.5; both probe defenses and full-stack have benign episode utility 0 and FPR 1 on both tiny episode suites (`reports/RESULTS_week7.md:5`, `:9`, `:17`, `:18`, `:88`, `:89`, `:91`, `:101`, `:102`, `:104`). This is useful smoke evidence and failure evidence, not evidence of effective general prompt-injection detection.

At inspection, this checkout contained no `artifacts/` directory and no Week 7 evaluation/benchmark JSON under `reports/`. The Markdown is therefore an existing reported result, not an independently reconstructed result from its weights or raw scores. Downloaded archives outside this checkout are outside this audit's scope.

## What is implemented correctly

- Activation collection is an actual `AutoModelForCausalLM` forward with `output_hidden_states=True`, attention-mask-aware last/mean pooling, evaluation mode, and `no_grad`; mock collection is explicitly separate (`src/smaip/probes/activations.py:179`, `:187`, `:198`, `:207`, `:213`, `:267`, `:276`, `:304`, `:315`). It is frozen-model probe training, not language-model fine-tuning.
- Each layer's scaler and logistic weights are fit using training rows. Layer selection and threshold calibration use validation rows. Test rows are scored only after the layer and validation threshold are selected (`src/smaip/probes/train.py:33`, `:41`, `:43`, `:47`, `:68`, `:79`, `:82`, `:86`). There is no direct test-label threshold fitting in this routine.
- The artifact stores the scaler, weights, bias, selected layer, pooling, threshold, model/backend/device, and split sizes (`src/smaip/probes/train.py:88`). Inference uses those stored weights and scaler (`src/smaip/probes/trained.py:41`).
- Mock metrics are labeled as token-hash pipeline checks by the renderer (`src/smaip/eval/week7.py:126`). Earlier suites explicitly resolve absent supplied probes to stubs (`src/smaip/probes/registry.py:40`), so their published results are not silently changed by Week 7 artifacts.

## Findings that constrain research claims

### 1. Episode ablations reuse the feature-training corpus

**High consequence for generalization claims.** The corpus includes every Week 5 and Week 6 vendor page (`src/smaip/probes/dataset.py:65`, `:89`). After fitting the probes, the pipeline measures episodes loaded from those same fixture libraries (`src/smaip/eval/week7.py:51`, `:66`, `:89`, `:91`, `:97`). The episode selection is not constrained to test records or unseen vendors (`src/smaip/eval/week7.py:247`). Thus the episode tables are in-corpus integration checks with overlapping training material, even though the separate record-level test metrics use held-out IDs. The report's “different cut” wording does not explain this contamination (`src/smaip/eval/week7.py:185`).

Safe action: retain these tables as integration results and add a separate episode evaluation whose vendors, templates, and attack families were excluded from training and threshold selection. Record each episode's source-group split.

### 2. ID splitting allows related vendor pages across splits and changes membership when records change

**High consequence for independence/reproducibility.** `assign_splits` sorts within label and deals individual rows by position modulo five (`src/smaip/probes/dataset.py:118`). It does not group vendors, common templates, paraphrases, or related attacks. A lightweight fixture enumeration using the actual `Record`, `select_subset`, and `assign_splits` functions gave these full-corpus memberships:

| related records | split |
| --- | --- |
| `week5:ferry_docs/addendum.md` | train |
| `week5:ferry_docs/overview.md` | val |
| `week5:ferry_split/part_a.md` | test |
| `week5:ferry_split/part_b.md` | train |

The multi-page source relationship is explicit in the page text (`src/smaip/fixture_data/week5/vendors/ferry_docs/overview.md:3`, `:7`; `src/smaip/fixture_data/week5/vendors/ferry_split/part_a.md:3`). This does not itself prove identical-content leakage, but it violates vendor/group independence. Also, the docstring's “same id always lands in the same split” is only true for a fixed corpus: adding an earlier-sorting row of the same label shifts later memberships (`src/smaip/probes/dataset.py:8`, `:122`, `:133`). Tiny/full call splitting after subsetting, so the same ID can move between those runs (`src/smaip/probes/dataset.py:150`).

Safe action: build and freeze an explicit group-level manifest with corpus hashes before any new fit. Validate text and near-duplicate overlap across groups, and preserve the manifest with every result.

### 3. Tool-output labels have an obvious lexical shortcut

**High consequence for interpreting probe discrimination.** Every injected tool record ends with “End of dossier.” and uses dossier/relay/smuggle vocabulary, while the benign records end with tool-specific “record” strings. This is visible throughout `src/smaip/fixture_data/week7/tool_outputs.jsonl:1` through `:24`, especially the boundary at `:12`/`:13`. Both train and test use that same constructed style. The positive labels can therefore be predicted using collection artifacts unrelated to the intended trust-boundary concept. This is a demonstrated confound, not proof that the trained probe actually relies on it.

Safe action: remove class-specific suffixes and balance entities, style, tool type, length, and action vocabulary across labels. Include benign quoted uses of the same nouns/verbs and harmful cases without those words. Add suffix-only/keyword baselines and counterfactual suffix swaps to measure shortcut dependence.

### 4. Vendor labels do not always mean an injection exists in the individual page

The loader marks **every** page of a poisoned vendor positive (`src/smaip/probes/dataset.py:75`). Ferry Docs' overview contains revenue and a request to read the addendum, while the malicious email instruction is in the addendum (`src/smaip/fixture_data/week5/vendors/ferry_docs/overview.md:3`, `:5`, `:7`; `src/smaip/fixture_data/week5/vendors/ferry_docs/addendum.md:3`). Split encoded pages are also each labeled positive independently (`src/smaip/fixture_data/week5/vendors/ferry_split/part_a.md:7`; `src/smaip/fixture_data/week5/vendors/ferry_split/part_b.md:3`). A page-level detector is therefore trained partly against vendor/episode labels and incomplete attack fragments.

Safe action: define whether the task is malicious span, malicious page, or malicious episode. Annotate page/span labels separately from episode-level attacks; test multi-page context as its own task.

### 5. “Test FPR at target TPR” is a misleading name for the frozen-threshold test metric

The threshold is correctly calibrated on validation at target recall 0.95 (`src/smaip/probes/train.py:47`). But `metric_block` simply evaluates whatever threshold it receives and calls the resulting FPR `fpr_at_tpr`, without enforcing the target on that split (`src/smaip/probes/logistic.py:170`, `:177`, `:185`). The test threshold remains frozen, so its achieved TPR may be far below 0.95. The current Markdown table shows FPR and the target, but omits achieved test TPR (`src/smaip/eval/week7.py:154`, `:159`, `:289`). A linear test F1 of 0 paired with FPR 0 must not be read as “zero FPR at 95% recall.”

The tiny corpus has only two positive and two negative validation examples and the same test class counts; 95% recall means catching both validation positives. Sweeping 24 layers on four validation examples can select a perfect-looking layer with little evidence of transfer (`reports/RESULTS_week7.md:7`, `:9`, `:26` through `:78`).

Safe action: label the frozen operating-point metric `test_fpr_at_val_threshold`, report achieved recall and confusion counts alongside it, and present AUROC separately. A descriptive test-set FPR@95%-TPR can also be computed, but must not replace the preselected deployment threshold or become a tuning signal. Use larger independent calibration/test groups and uncertainty intervals.

### 6. ASR is a scripted side-effect caller, not measured model susceptibility

The graph first processes allowlisted integer extracts, and a separate fixture-specified caller then attempts the attack action using page text (`src/smaip/eval/week5.py:444`, `:461`, `:477`, `:702`; Week 6 mirrors this at `src/smaip/eval/week6.py:364`). The reader passes extracted numbers rather than page prose to the analyst (`src/smaip/agents/reader.py:28`; `src/smaip/agents/analyst.py:15`, `:45`). The analyst's default is a mock completion (`src/smaip/agents/analyst.py:48`).

The gateway checks approval before hooks, and the untrusted caller cannot create an approval (`src/smaip/gateway/gateway.py:96`, `:135`, `:146`). Therefore gateway-only ASR 0 chiefly establishes that the approval boundary blocks this scripted caller. It does not establish that Qwen generated safe actions, or that a probe adds marginal safety over the gateway. The existing report does disclose the caller, which should be preserved (`reports/RESULTS_week7.md:106`).

Safe action: describe this as a deterministic enforcement/integration experiment. If the research question concerns model susceptibility, add a separately designed real-model agent evaluation with explicit trusted/untrusted contexts and measured model-generated actions, while preserving sandboxed side effects.

### 7. Feature extraction has unverified semantics and incomplete provenance

The model sees each record as a **user chat message**, not as a tool-role result in a surrounding trusted conversation (`src/smaip/probes/activations.py:329`). Both batch collection and scoring use that renderer (`:156`, `:198`). The last non-padding vector can therefore be a chat-template terminator rather than the final content token. This is a design choice, but it should be stated and tested rather than called a generic tool-response residual.

Collection/scoring read `SMAIP_PROBE_MAX_LENGTH` dynamically, defaulting to 512 (`src/smaip/probes/activations.py:157`, `:199`, `:358`). This parameter, tokenizer/model revision, chat-template content, truncation counts, corpus manifest, package versions, and code commit are absent from the saved artifact (`src/smaip/probes/train.py:88`). Changing the environment can change inference features without changing probe weights. Inference also restores the training device literally (`src/smaip/probes/trained.py:22`, `:51`), which limits portability of CUDA artifacts.

The code equates every `hidden_states[layer+1]` with the stream directly after a block (`src/smaip/probes/train.py:108`; `src/smaip/probes/activations.py:213`). The exact final-layer normalization behavior must be checked against the pinned installed model implementation before interpreting layer positions. This audit did not load Transformers or establish that behavior.

Safe action: pin and save model/tokenizer revisions, extraction configuration and token positions; test batch versus individual vector parity, truncation boundaries, padding, final-layer semantics, and artifact round-trip score parity. Validate artifact dimensions/finite values and model metadata before loading.

### 8. Activations and Week 7 traces are not persisted despite some documentation wording

`collect` returns vectors in memory; `run_week7` writes only `artifacts/activations/summary.json`, whose fields are counts/dimensions/layers/backend (`src/smaip/eval/week7.py:55`, `:65`, `:335`). There is no vector serialization in this path. The runbook says raw activations stay on the GPU box (`docs/GPU_RUNBOOK.md:59`), which the implementation does not substantiate. Week 7 `_measure` collects traces in a local list but returns only aggregated rows (`src/smaip/eval/week7.py:238`); the JSON report contains scenario summaries, not those event traces (`:103`). The archive includes probe weights and reports but not activation data (`Makefile:66`).

Safe action: either correct the documentation to state that vectors/traces are ephemeral or explicitly persist compressed vectors, a record manifest, per-record scores, and event traces in a run-specific evidence directory. Save enough to refit/evaluate probes without repeating the model forward.

### 9. Performance numbers require a corrected measurement protocol

Trained probes cache by full input text (`src/smaip/probes/trained.py:34`, `:41`). The same probe objects are shared across ablations and suites (`src/smaip/eval/week7.py:87`, `:91`, `:97`, `:238`). Additionally, trace generation scores both probes even for disabled probe defenses after the latency timer has stopped (`src/smaip/eval/week5.py:472`, `:494`, `:605`). This can populate caches outside measured latency and make later ablations appear much cheaper. The current table's fast full-stack row after much slower individual probe rows is consistent with this protocol, not evidence of near-free additional defense (`reports/RESULTS_week7.md:88`, `:89`, `:91`).

The separate overhead benchmark repeats only four prompts 20 times with the same cached probe objects (`src/smaip/serving/benchmark.py:103`, `:122`), so 76/80 requests per probe are cache hits after the first cycle. It therefore does not characterize uncached request screening. The HF serving test labels a single batch wall time as both p50 and p95 (`:165`, `:192`); its token count uses padded output width times batch size (`:184`), and no tokenizer padding side is explicitly set for decoder-only generation (`:145`, `:168`). These are prototype benchmark limitations.

Safe action: isolate/warm models deliberately, report cache hit/miss conditions, use fresh inputs for uncached overhead, remove diagnostic scoring from timing side effects, synchronize CUDA around timing, count actual generated tokens, and repeat many requests before claiming latency percentiles or engine speedups. Cost in the episode table is fixed synthetic per-tool accounting, not monetary/model compute cost (`src/smaip/gateway/gateway.py:37`, `:213`).

## Tests and evidence limits

The existing Week 7 tests check corpus labels/determinism, a synthetic separable logistic example, mock-pipeline artifacts, ablation names/basic scripted outcomes, registry behavior, and documentation strings (`tests/test_week7.py:26`, `:53`, `:109`, `:137`, `:157`, `:210`). The opt-in HF test checks vector size and that last/mean pooling differ for one short string; it does not establish batch parity, layer-hook semantics, generalization, or an effective trained defense (`tests/test_week7.py:246`). HF tests are skipped unless `SMAIP_RUN_HF=1` (`tests/conftest.py:27`). A green default suite is therefore software smoke evidence, not validation of a 3B experiment.

A direct `prepare_records` call with the system Python failed because `langgraph` is absent; the dataset loader imports evaluation modules indirectly. No dependency installation was attempted. The fixture enumeration above used standard-library JSON/path handling for page discovery plus the repository's `Record`, `select_subset`, and `assign_splits`, avoiding the graph import. It produced full corpus **57 records: train 36, validation 11, test 10** (train 21 positive/15 negative, validation 6/5, test 6/4), and tiny **20 records: 12/4/4** (balanced within each split). These are derived corpus facts, not model results. The parent task owns fresh test execution and recovery of downloaded result artifacts.

## Prioritized safe next actions

1. Preserve the current report as the 0.5B tiny CPU smoke, including its over-blocking failures. Recover any existing GPU archive and inspect its backend, model, subset, split sizes, achieved recall, benchmark skip status, weights, run logs, and provenance before calling the GPU phase complete.
2. Freeze a group-level corpus/split manifest; remove label-specific fixture cues; separate page labels from episode labels; reserve an unseen episode suite. State the research question and success criteria before retraining.
3. Repair metric names and show achieved test recall/confusion counts. Fix cache/timing effects and artifact provenance/persistence. Add targeted parity and split-independence checks.
4. Run an inexpensive real 0.5B check on the corrected protocol, then the authorized 3B/full GPU run if needed. A larger checkpoint alone does not fix leakage, lexical confounds, mislabeled operating points, or a scripted ASR definition.
5. Report probe-only, gateway-only, and combined outcomes with benign utility, confidence intervals, failure examples, and the incremental value of each defense. Treat live-model agent evaluations and external benchmarks as separate future evidence rather than attributing them to the present fixtures.
