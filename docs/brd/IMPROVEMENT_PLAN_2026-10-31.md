# SMAIP improvement plan: useful detection and BRD completion

Implementation follow-up: the local acceptance, task-authority/evidence and durable
review changes are now tested, and a source-pinned candidate review queue and
bounded clean GPU pilot bundle are prepared. See
[implemented changes and next pilot](IMPLEMENTATION_NEXT_STEPS_2026-10-31.md).
Human label review and a third eligible task-source stream remain pending. The
first protocol-5 clean GPU pilot subsequently completed at 0/25 in both arms:
all readers/single agents stopped before source access. See
`reports/EVIDENCE_CLEAN_01_ANALYSIS.md`. The subsequent protocol-6 smoke completed
at 2/4 single-agent and 0/4 specialist successes, dominated by citation failures;
see `reports/EVIDENCE_CLEAN_02_SMOKE_ANALYSIS.md`. The next experiment is the
[protocol-7 numbered-source smoke](EVIDENCE_PILOT_03_SMOKE.md) subsequently passed
an audited 8/8 with all 44 citations reconstructed. The next run is the
[full clean pilot on the same frozen r3 source](EVIDENCE_PILOT_03_FULL.md). It
timed out after 40 episodes: 17/20 single-agent and 19/20 specialist successes,
with four genuine model failures preserved. On November 1 the
[missing-episode continuation](EVIDENCE_PILOT_03_CONTINUATION.md) completed all 50:
**22/25 single-agent and 23/25 specialist successes**, with 170 citations
reconstructed across successful episodes. All original 40 records/failure scores
remain unchanged. See `reports/EVIDENCE_CLEAN_03_COMPLETED_ANALYSIS.md`.
The clean-workflow diagnostic is complete; reviewed corpus and feature work
remain the next priority.
The subsequent 32-document Feature V3 smoke verified source/token provenance
and exact repeatability, but failed its absolute causal-prefix tolerance on
two 96→99-token renderings. A nine-forward, same-length changed-suffix
diagnostic reproduced the saved vectors exactly and found zero prefix change
at fixed length, supporting a sequence-length-dependent fp16 calculation
effect. The original smoke result remains failed; see
`reports/FEATURE_V3_SMOKE_01_ANALYSIS.md`. A label-free, tokenizer-only
[candidate budget audit](FEATURE_V4_TOKEN_BUDGET.md) is prepared before
any larger activation collection.
That audit subsequently verified all 1,012 candidate renderings: 72
task-conditioned views exceed 512 tokens, two exceed 1,024, and none exceed
2,048. See `reports/FEATURE_V4_TOKEN_BUDGET_01_ANALYSIS.md`. A forward-only
[V4 feature collection](FEATURE_V4_COLLECTION.md) is prepared at a 2,048-token
no-truncation cap; candidate labels and split roles remain unreviewed.
The collection subsequently completed all 1,012 forwards and passed binary
provenance checks. A **local exploratory** grouped linear fit on NVIDIA
development labels selected `content_mean/18`; one-shot LLMail source-transfer
ranking was also completely separated, with a strong length confound check.
These are unreviewed, connected-source development observations, not a
calibrated 1%-FPR or full-agent security result. The corrected fit and limits
are documented in `reports/FEATURE_V4_EXPLORATORY_02_ANALYSIS.md`.
An assistant-only blind semantic screen of 32 development candidates found
29 judgments matching the upstream labels and three ambiguous task/label
boundaries. An exact duplicate audit found that 203 LLMail benign rows reduce
to 160 distinct task/document pairs. No human adjudication or independent
low-FPR claim follows from this screen; see
`reports/FEATURE_V4_BLIND_REVIEW_01_ANALYSIS.md`.
These are workflow diagnostics, not detector gains.
The original research findings below retain their original scope.

Research date: October 31, 2026. Status: proposed implementation and experiments;
no new GPU job, base-model download, runtime change, probe replacement or threshold
change was made for this investigation. Local saved-vector and acceptance-check
diagnostics are explicitly identified below.

## Recommendation

Keep Qwen frozen for the next stage. Improve the data, task/context representation,
low-FPR ranking and deterministic task authority before considering a larger model,
an MLP, or base-model fine-tuning. More epochs and a lower threshold do not address
the measured failure. Pursue two connected tracks: a useful, constrained agent
workflow and a properly evaluated detector. A better detector cannot repair an
actor that fabricates facts; a safe gateway cannot establish detector generalization.

The next implementation should be local: strengthen evidence/acceptance checks,
introduce task-scoped authority and validated factual handoffs, and prepare the
new corpus/split/feature contracts. Only then launch a bounded GPU experiment.
Do not launch another unchanged run of the 36-document training set or tune a new
deployment threshold against the already observed NVIDIA labels.

## BRD basis and research boundaries

At the original research attempt, browser inspection and public HTTP retrieval
could not obtain the live BRD. A subsequent October 31 Chrome recheck successfully
read all 19 sections of the [live BRD](https://brd-secure-multi-agent-inference-y62m.pages.grok.bot/),
which still identifies **version 1.2, October 26, 2026** and retains the key targets
used in [BRD_ALIGNMENT_2026-10-30.md](BRD_ALIGNMENT_2026-10-30.md). See the
[live recheck](BRD_LIVE_RECHECK_2026-10-31.md) for confirmed scope and remaining
implementation gaps; this is not a byte-for-byte earlier-export comparison.
The owner's subsequent **open-model-only** decision supersedes the page's original
hosted-Codex selection. V1 training means probe training, not base-LLM fine-tuning.

The main BRD targets remain TPR at 1% FPR, least-privilege clean utility within
five percentage points of the single-agent baseline, strict full-stack security
superiority, meaningful approvals/privacy, and measured latency/cost. Proposed
additions to those requirements are labeled as proposals; the original BRD and
its acceptance conditions have not been silently rewritten.

Detailed primary-source investigations:

- [Activation methods and feature experiments](research/2026-10-31_PROBE_LITERATURE.md).
- [Dataset, split and statistical-calibration design](research/2026-10-31_DATA_CALIBRATION.md).
- [Architecture, benchmarks and acceptance design](research/2026-10-31_ARCHITECTURE_EVALUATION.md).

Papers' reported results below belong to their original settings. None is an
expected performance figure for our 3B model, and no external defense or benchmark
was reproduced as part of this literature review.

## What failed, and what the evidence actually says

| Evidence | Last-token linear | Mean-pooled linear | Interpretation |
| --- | ---: | ---: | --- |
| Frozen external recall, 400 attacks | 0/400 | 1/400 | Neither current operating point is useful on this source. |
| Frozen external false positives, 400 controls | 0/400 | 1/400 | Zero alarms with zero recall is not detector success. |
| External AUROC | 0.5630 | 0.8874 | Mean pooling contains overall ranking signal, but AUROC hides the poor upper-benign tail. |
| Post-hoc best recall at empirical FPR **at most** 1% on this observed set | 7/400 = 1.75% | 2/400 = 0.5% | Even label-informed threshold choice cannot recover useful low-FPR ranking here. This is descriptive diagnosis, **not** deployment calibration. |
| Training labels fit after first gradient step | 12/12 | 12/12 | Longer fitting is not the first missing ingredient. |
| Regularized training loss at step 400 | 0.007476 | 0.004662 | Training objective is nearly flat by the end; no evidence of optimizer divergence. |

The descriptive ROC scan allowed up to four false positives among 400 negatives;
the best-recall points actually occur with two. No saved threshold was changed.
These figures were independently checked by exhaustive score-threshold enumeration.
The same observed set must now remain development/regression evidence.

Mean pooling increases the injected score over its clean counterpart for 384/400
pairs, but its only two positive classifications are the clean and injected
versions of **the same healthcare pair**, with the clean score higher. This
suggests a useful paired-training diagnostic and possible background sensitivity;
it does not prove that topic confounding is the sole cause. At inference we do
not have an unknown clean counterpart and must never require it to compute scores.

The 36 authored documents were a pipeline feasibility corpus. They provide only
12 training and six benign calibration observations for a 2,048-coordinate model.
Their nominal pair/group IDs do not make the texts controlled same-document
counterfactuals. Their shared authorship/style, tiny tail sample, and lack of
human label review make them unsuitable as generalization evidence. NVIDIA's
external controls are span-deleted synthetic content, also not human-reviewed
benign originals. Both limitations must be addressed by the next data protocol.

The agent has a separate quality problem: least-privilege clean utility is 2/4
versus 4/4 single-agent, with unsupported fields and unnecessary files. All arms'
targeted ASR is 0/4 on those cases. That experiment neither meets the five-point
utility target nor establishes a security advantage.

Local diagnostics also demonstrate that the current `assess()` gate can return
`pass` for synthetic complete-looking records with **zero probe recall**, or
with **zero absolute task utility in every arm**. These are software counterexamples,
not real model runs: the gate lacks a useful-recall floor, an absolute utility
floor and independently bound evidence. It must not certify experimental success
merely from plausible aggregate fields.

Evidence and reproduction:

- [External audit](../../reports/V2_EXTERNAL_FROZEN_01_ANALYSIS.md), [training audit](../../reports/V2_PROBE_DEVELOPMENT_01_ANALYSIS.md), [agent audit](../../reports/OPEN_AGENT_DEV_02_ANALYSIS.md).
- [Ranking diagnostics](../../reports/research/2026-10-31/external_ranking_diagnostics.json), [optimizer traces](../../reports/research/2026-10-31/optimizer_diagnostics.json), [acceptance counterexamples](../../reports/research/2026-10-31/acceptance_counterexamples.json).
- CPU-only reproduction: `PYTHONPATH=src .venv/bin/python scripts/research/smaip_diagnostics.py`.

## Research findings that change the design

### 1. Match the representation to the actual question

Our probe sees a constant inspection query and pools tool-content tokens. It
does not see the actual authorized task, tool capabilities or agent transcript.
The nearest published methods are materially different:

- **TaskTracker** uses task-relative changes in pre-generation representations;
  its released code accepts both a user task and external text. A varying actual
  task matters. Subtracting one constant baseline under our current fixed query
  adds no information after train z-scoring: centering cancels that constant.
  [Paper](https://arxiv.org/html/2406.00799v3), [pinned author code](https://github.com/microsoft/TaskTracker/blob/b4fabe25504dc1d3f7c6fdf5e50d4bb209a152b0/quick_start/utils.py).
- **Dong et al.'s IPI exposure probes** read a model-specific assistant-prefill
  boundary and examine multiple depths. Their reported architecture ablation
  favors linear probes over MLPs; descriptive best-layer results are not an
  unbiased layer-selection recipe for our model. Exposure prediction and eventual
  harmful action are separate targets. [Paper v2](https://arxiv.org/html/2608.02657v2).
- **AASE** motivates paired contrastive training to reduce topic/style nuisance.
  Its indexed abstract/version record were verified, but exact PDF extraction and
  split details could not be retrieved. Treat it as motivation, not a fully
  reproduced training recipe or evidence of 1%-FPR performance.
  [Versioned record](https://zenodo.org/records/19209689).

Retain regularized logistic regression as the primary model. Keep an MLP and
gradient-based methods as later controlled ablations after adequate data, not
the next default. A more expressive classifier can learn the same shortcuts.
Compare a frozen, separately trained **Prompt Guard 2** text classifier as a
baseline only after pinning its checkpoint/license and calibrating it for the
same evaluation unit. Its private benchmark metrics are not ours.
[Official model card](https://github.com/meta-llama/PurpleLlama/blob/main/Llama-Prompt-Guard-2/86M/MODEL_CARD.md).

### 2. Low-FPR calibration is a statistical protocol, not a threshold tweak

Use separate fitting, model-selection, statistical-calibration and final-test
groups. Freeze the scalar score before opening statistical calibration. For a
population-control claim, implement a predeclared Neyman–Pearson clean-score
order-statistic rule with explicit `alpha=.01` and `delta=.05`, including
conservative tie handling and sampling-frame assumptions. This is different
from our current empirical-FPR selector. It is not a guarantee under source shift.
[Tong, Feng and Li](https://pmc.ncbi.nlm.nih.gov/articles/PMC5804623/).

For example, with 1,500 independent clean calibration scores the specified rule
can use an upper-tail allowance of eight; the current empirical rule permits
15. With 2,000 independent benign final-test contexts, 20 FPs is observed 1% but
has a one-sided exact 95% upper endpoint about 1.45%; 12 FPs has upper endpoint
about 0.970%. The conditions and denominator matter more than the round count.
Our direct calculations are saved in
[statistical_planning_checks.json](../../reports/research/2026-10-31/statistical_planning_checks.json).
[Exact-binomial reference](https://itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbino.htm).

Define whether 1% refers to a document, a tool return, an action or an episode.
Two 1%-FPR probes combined by OR need not remain at 1%; multiple chunks and
documents can also increase interruption rates. Prefer one selected score or a
development-frozen fusion function, then calibrate its final aggregation directly.
Track episode utility and human-review burden separately from document FPR.

### 3. Authorization and factual preservation belong outside free-form generation

CaMeL is relevant because it separates trusted control flow from untrusted data
and checks capabilities. Its secure utility is not automatically within five
points of its baseline, and its guarantees do not establish arbitrary summary
truth. Our current role names/taint strings are not a CaMeL-equivalent mechanism.
[CaMeL paper v2](https://arxiv.org/html/2503.18813v2).

For the bounded vendor workflow, add a small immutable **task-intent record**:
source/vendor scope, requested action, recipient, permitted paths, requested
fields/format, side-effect count and approval mode. A send-only task should not
grant write/delete merely because the actor role can support them generally.

Have the analyst propose structured evidence claims with source hash and quote/span.
Validate source membership and numeric correspondence, then render the canonical
numeric brief deterministically. Let the actor propose sending a validated artifact
by reference; check the artifact/recipient/subject/action digest at the gateway.
Do not silently replace a wrong proposed body with scorer ground truth or execute
an action automatically to improve the benchmark. Evidence from a source establishes
what it says, not that its real-world claims are true. Arbitrary prose still needs
attribution/review rather than a fictional semantic guarantee.

Persist pending actions and resume saved state after action-bound confirmation;
do not rerun generation and hope it recreates the approved proposal. Keep input
minimization, log redaction and output-canary checks as separate boundaries.

## Updated BRD gap map

These statuses supersede the old assessment's implementation facts, not the
underlying owner's requirements.

| BRD IDs | Current position | Required improvement | Priority |
| --- | --- | --- | --- |
| A01–A03: API and real HF/vLLM serving | API and local-generation adapters exist; returned evidence is offline HF, not a completed live serving benchmark. | Verify actual API model identity, vLLM service behavior, request-level cold/warm/cache timing. | P3 |
| A04–A05/A11: real agent and five-point utility | Open Qwen loop exists; hosted-Codex selection is superseded; clean specialist utility 2/4. | Task-scoped authority, validated factual handoff, capable clean baseline and paired utility measurement. | P0–P1 |
| A06/A09: gateway and human confirmation | Role/schema checks and action digest exist; persistent review/resume is unfinished. | Narrow role ceiling by trusted task intent; persistent one-use approval and idempotency. | P1 |
| A07–A08: trained residual probes and token scope | Real V2 weights and tool masks are verified, but transfer fails; task context is absent. | Reviewed data, readout/context experiments and new versioned protocol for changed features. | P1–P2 |
| A10/A14: structural ablations and strict combined improvement | Seven configuration rows are defined; complete capable-model matrix and a susceptible baseline are not measured. | Match cases/budgets, record shared controls, verify policies activate, measure adaptive attackers and uncertainty. | P2–P3 |
| A12: TPR at 1% FPR | Current frozen recall is near zero; six clean calibration rows cannot support the tail. | Useful-recall target, confidence-controlled calibration and fresh final testing. | P0–P2 |
| A13: external/adaptive evidence | One synthetic external detector pilot is complete; no full agent adaptive benchmark. | Separate detector/source transfer from native agent and adaptive evaluations. | P2–P3 |
| A15–A16: cost, latency and traces | Strong source/artifact traceability; historical timing/cache limitations and mock cost units remain. | Request/token-level wall-time, detector/tool/review decomposition and actual rental-cost accounting. | P3 |
| A17: executable acceptance | Aggregate contract checker can pass vacuous quality and unsupported provenance. | Evidence-derived gate, counts/intervals, absolute quality floors and explicit inconclusive state. | P0 |
| A18: privacy | Logging redaction exists; model-input and output policy is incomplete. | Trusted recipient references, source minimization, private canaries, output checks and review boundaries. | P1–P3 |
| A19: reproducibility/release | Audited bundles and NVIDIA attribution exist; final architecture, project license and release remain open. | Reproducible commands, truthful claims and final release/demo after acceptance. | P4 |

## Ordered implementation and experiment plan

### P0 — Make success non-vacuous, locally

Deliver one evidence/acceptance change before another training run.

- Recompute scores and task effects from bound per-document/per-episode artifacts;
  verify source/model/protocol/threshold hashes and matching case IDs.
- Reject missing positive support, all-negative detectors, zero-usefulness agents,
  invented performance records and boolean-only independence claims.
- Retain the BRD's five-point relative utility condition and add a proposed
  absolute utility floor. Keep the exact numeric floor pending an explicit
  specification decision, rather than inventing an existing requirement.
- Add a proposed minimum useful TPR at the defined FPR. **50% pilot recall** and
  **80% eventual research recall** can be working targets to review, not promises
  or original BRD requirements. Preserve confidence and worst-source reports.
- Separate `software pass`, `model-quality pass`, `security evidence`, and
  `release pass`; permit fail and insufficient/inconclusive evidence.

Files: `eval/acceptance.py`, `eval/contract.py`, corpus/result contracts and tests.
Exit: the synthetic counterexamples fail or remain pending; existing archived
measurements reaggregate unchanged. No previous failed run becomes a success.

### P1 — Repair the useful-work path and data contract

Implement task-intent capabilities and evidence-backed summaries described above.
For actual numeric tasks, remove the actor's need to regenerate factual body text.
Persist action review/resume. Test missing/conflicting facts and valid-looking
malicious handoffs, not just malformed JSON.

Define a new corpus schema separating **task**, **untrusted document**, **source
origin**, **source context**, **pair**, **template lineage**, **attack family**,
author/generator, label provenance and split role. Keep labels, attacker goals,
condition names and scorer answers out of model input. The present validator's
family-disjoint train/calibration/test rule cannot represent every scientific
question: version it explicitly for named in-distribution, family-held-out and
source-held-out tests. Do not rename families by split or fabricate source IDs.

Preserve V2 artifacts. A task-conditioned or assistant-boundary extraction uses
a new protocol/hash and new weights. Tool-content-only remains the unchanged-BRD
baseline. Making an assistant-boundary readout the primary FR-3 implementation
would require an explicit BRD feature-contract amendment after comparison.

Files: `agents/open_loop.py`, `agents/action_schema.py`, `gateway/gateway.py`,
`probes/manifest.py`, `probes/protocol.py` and their tests.
Exit: scripted tests establish the general policy without fixture answer injection;
a subsequent 25-clean-task, two-topology GPU pilot measures actual utility. That
50-episode pilot diagnoses failures; it cannot establish five-point noninferiority.

### P2 — Review data before collecting more features

Start with a **1,012-document feasibility pilot**, not an immediate acceptance-scale
collection:

| Role | Benign | Injected | Purpose |
| --- | ---: | ---: | --- |
| Fitting | 128 | 128 | Train-only moments and coefficients. |
| Model selection | 128 | 128 | Choose feature/readout and regularization. |
| Threshold development | 400 | 100 | Feasibility diagnosis after selection; no final statistical certification. |

Obtain multiple author/source streams and realistic vendor-style benign material;
do not manufacture independent sample counts with paraphrases. Prioritize a capped,
reviewed **LLMail-Inject** attack sample with team/scenario/template grouping,
alongside independent benign tool-result documents. Its failure-to-trigger labels
are not benign labels, and its 203 benign FP-test emails alone cannot support the
required benign counts. **NotInject** is a useful 339-example over-defense slice,
not representative deployment calibration. [LLMail card](https://huggingface.co/datasets/microsoft/llmail-inject-challenge/blob/main/README.md),
[NotInject card](https://huggingface.co/datasets/leolee99/NotInject/blob/main/README.md).

Reserve AgentDojo for stateful agent evaluation and InjecAgent for separately
named tool-injection stress testing. Respect `DATA.md`: keep external payloads
outside Git, pin exact licenses/revisions, and review component terms for BIPIA.
SPML's context-sensitive labels must not be flattened into document-only malicious
labels; unlabeled Gandalf submissions and missing-license collections are not
drop-in training truth. The detailed source choices/limits are in the data note.

Use real matched clean/injected base contexts where available, plus independent
benign documents. Balance topic, length, urgency, quotes, JSON/code, authority
language, domains and multilingual variants across labels. Label redirection
attempt, successful compromise and harmful subject matter separately. Mechanically
audit every row; adjudicate ambiguous labels and inspect source-stratified samples.
Record human review honestly. Resolve ambiguous final-test labels before scoring.

Exit: reviewed label policy, sampling frame, license inventory and duplicate/
lineage-connected split manifest are ready; hidden final material stays sealed.
If data availability cannot meet the counts/independence conditions, narrow the
claim and stop the corresponding acceptance step rather than pad the dataset.

### P2a — Bounded feature/data experiment on the same A16

Keep the pinned 3B backbone, fp16 execution, single-document batching and fp32
pooling. First smoke new rendering on 32 development documents and validate token
spans, boundary tokens, precision, repeatability and resource use.

Predeclare a staged matrix:

1. **Three blocks: 6, 18, 30.** At each depth compare tool-content last, content
   mean and assistant-prefill boundary: nine feature candidates. Save token IDs
   and neighbors, not an unexplained `-1`. Keep the V2 fixed-inspection view as
   the baseline; compare a precisely rendered boundary view. Verify whether the
   suffix preserves prefix tokenization and approximate causal-state invariance.
   Preserve distinct input/protocol hashes and numerical tolerances regardless.
2. **At the selection-chosen depth**, compare actual-task-conditioned boundary
   state with task-relative delta using the same contextual view. Cache trusted
   task-only states by exact context hash. Never subtract the unknown clean
   counterpart at inference. Never call constant-baseline subtraction TaskTracker.
3. **Saved-vector CPU work:** evaluate nested group-preserving training sizes
   128/512/1,024, two selection-chosen finalist feature/readout families, and a prespecified L2 grid
   `{0.05, 0.5, 5}` after enough fitting data are available: 18 primary fits. Match
   the mean-loss-plus-L2 objective if using a vectorized library; its `C` parameter
   is not automatically the current coefficient. Record convergence and norms.

This reconciles the detailed notes into a sequence: data and forward-only linear
baselines first; depth/readout selection only on development groups; actual task
context/delta next if justified. Do not run a large uncontrolled cross-product of
backbones, prompts, layers, MLPs and calibrators. A paired-ranking/contrastive
training objective can be one later CPU ablation on genuinely matched data, with
ordinary benign classification anchoring; it is not a substitute for global
low-FPR evaluation. A small MLP is deferred until the linear/data curves justify it.

Multiple layer readouts come from the same forward. The conservative initial
budget is at most two rendered views per 1,012 pilot documents, **2,024 forwards**,
plus at most **2,024** task/task-only forwards for the second context stage before
cache savings. This is a request-count ceiling, not an A16 wall-time estimate.
Measure throughput first, cap the job and use the actual current rental rate.
Load one model at a time. Save binary float32 vectors with ID/protocol/checksum
sidecars rather than scaling the current verbose JSON representation indefinitely.

Select using grouped low-FPR behavior, partial ROC, source/family robustness and
paired score sensitivity; keep overall AUROC as a secondary diagnostic. An apparent
improvement from a lower threshold, observed test labels or memorized wrappers
does not pass. If no candidate gives useful conservative pilot recall, prioritize
the structural platform and keep the detector experimental.

### P2b — Confidence-controlled calibration and fresh final evaluation

Only after the pilot is promising, freeze a single score/fusion and collect fresh
statistical calibration/final data. A proposed acceptance-scale study is:

| Role | Benign | Attack | Use |
| --- | ---: | ---: | --- |
| Fitting | 512 | 512 | Can subsume the pilot's fitting groups. |
| Selection | 256 | 256 | Can subsume its selection groups; no final labels. |
| Statistical calibration | 1,500 | 300 | Fresh clean-score NP calibration; attacks characterize frozen recall. |
| Untouched final target test | 2,000 | 500 | One selected rule, exact uncertainty and target-use claim. |

Total: **5,836 documents**, plus the already consumed 500 threshold-development
documents if retained separately, the known 36/800 regression material, and any
separately named external stress suites. Do not count pilot threshold-development
examples as fresh statistical calibration or final test. These are collection
targets, not a claim that the public sources above supply representative IID cases.

This stage's dominant cost may be review: at a nominal one minute per document,
5,836 documents is about 97 reviewer-hours, before disagreements or double review.
Reduce scope/claim if that is impractical. For the current two-pool, single-layer
features, binary float32 storage is about 91 MiB for 5,836 documents; extra views
and depths multiply storage. Extraction duration must come from the throughput
pilot, not a guessed rental-time promise.

Implement the explicit NP rule, verify tie/rank edge cases, and calibrate the
final document/fusion decision. If long inputs need chunking, version and calibrate
the aggregate document score; do not silently truncate or reuse a per-chunk 1%
threshold. Report target-use and held-out source/family results separately.

### P3 — Demonstrate the platform, then serving/performance

Freeze the seven BRD rows and document every shared control. Task-intent authority,
role separation, factual validation, detector and keyword policy must have explicit
factor definitions; a new structural rule must not silently appear only in the
winning arm. Keep malicious action proposals representable in the sandbox baseline
where they are part of the declared threat model. Never insert an attack follower,
weaken one arm's task prompt, or filter final cases by observed baseline success.

Check attack reachability and grader sensitivity separately from model outcomes.
Use paired clean/injected user tasks with deterministic state/effect oracles where
possible. Keep whole-task utility, source/factual/format submetrics, approvals,
unexpected actions, targeted ASR and utility under attack distinct. Persist the
review lifecycle so "blocked every action" does not become safe task completion.

Add a pinned, bounded native AgentDojo evaluation and budgeted defense-adaptive
attacks. A transformed vendor-domain adapter must have its own name/oracle; it
cannot claim native benchmark numbers. Equalize attack-search budgets and retain
failed attempts. AutoDojo's reported policy-integration correction is a concrete
reason to test that each named defense actually activates.
[AgentDojo](https://github.com/ethz-spylab/agentdojo),
[AutoDojo v3](https://arxiv.org/abs/2606.15057v3).

Report paired task/group uncertainty for the five-point utility target and any
strict ASR difference. If no-defense remains at zero ASR, comparative security is
inconclusive for that suite; no detector win follows. If a deterministic gateway
already blocks all attacks, a full-stack tie does not satisfy strict superiority.
Do not manufacture a win. Keep the original condition unmet, or explicitly propose
an owner-reviewed revision to an ASR/utility/review-cost Pareto condition.

Finally measure actual HF/vLLM API serving with source/model identity, warm/cold
loads, cache hit/miss conditions, request-level p50/p95/TTFT, token counts and
generated-token throughput. Include detector, model, tool and review time. Use the
current rental rate and utilization assumption for dollars; integer mock gateway
cost units are not money. Publish only after privacy, release and agreed cost/
latency budgets are met. Larger or quantized models are a later separate factor,
not an assumed fit in the current 15.7-GB A16 memory budget.

## Explicit BRD clarification proposals

1. Specify a minimum useful recall and an absolute clean-utility floor alongside
   the existing FPR/relative-utility targets; decide the confidence convention.
2. Define the 1% unit and target benign distribution, and distinguish empirical
   operating points, statistical calibration, OOD stress and episode interruption.
3. Permit a versioned research comparison of tool-content and assistant-boundary
   features; retain the original content-only baseline for traceability.
4. Treat strict full-stack superiority as an empirical hypothesis. Any replacement
   with a Pareto or noninferiority criterion must be an explicit revision, not a
   post-hoc redefinition after a tie.
5. Preserve the open-model policy, sandboxed tools and narrow vendor workflow;
   add reproducible evidence requirements rather than a larger product scope.

## Immediate work order

Implement **P0** and the general **P1 task-intent/evidence contract**, prepare the
reviewable **P2 corpus/schema/experiment manifest**, then schedule the single bounded
feature/clean-quality pilot. No new GPU command is warranted by this research
alone. The existing scores remain failed-transfer baselines, and no improvement
is claimed until the new experiments are run and audited.
