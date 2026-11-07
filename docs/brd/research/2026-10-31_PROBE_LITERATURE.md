# Activation probes for SMAIP: primary-source investigation

Research date: 2026-10-31. This is a literature investigation and proposed experiment design. No model, extraction implementation, probe weights, thresholds, GPU runtime or source dataset was changed; no GPU run was started.

## Decision supported by the evidence

Keep the frozen V2 run as a failed-transfer baseline. The next useful experiment is a larger, reviewed, grouped-data comparison of **feature context and readout position**, followed by independent low-FPR calibration. Increasing classifier capacity is a secondary ablation. The literature supports activation monitoring as a plausible mechanism; it does not establish that SMAIP's present Qwen2.5-3B detector, data or thresholds should work on an unseen source.

The nearest research methods read a model's representation of the **actual task and external context**, often near the next assistant response. SMAIP currently reads tool-content tokens under a constant inspection request. Those are different detector definitions. Neither reproducing an upstream AUROC nor changing a threshold establishes the BRD's TPR at 1% FPR or real agent utility.

## What the local implementation establishes

Owning sources inspected: `PRIOR_ART.md`, `src/smaip/probes/protocol.py`, `logistic.py`, `pipeline_v2.py`, `low_fpr.py`, `docs/brd/V2_DEVELOPMENT_TRAINING.md`, `reports/V2_EXTERNAL_FROZEN_01_ANALYSIS.md`, and the local BRD alignment capture.

| Property | Current evidence | Consequence for the next experiment |
| --- | --- | --- |
| Backbone | Pinned frozen Qwen2.5-3B-Instruct, fp16 CUDA forward, batch one, float32 pooling | Keep these fixed while testing data/context; changing backbone and feature protocol together obscures the cause |
| Input | Fixed system inspection instruction, fixed user query, assistant “Tool result follows.”, one tool result; no generation prompt | The actual authorized user task, tool schema and agent transcript are absent |
| Readout | Block 18, `hidden_states[layer+1]`; last fully contained tool-content token or mean of those tokens | “Last” does not mean the last assistant-facing prefill token used in several papers |
| Classifier | Train-only per-coordinate z-score, L2 logistic regression, 400 gradient steps | Both deployed alternatives are linear classifiers; their primary difference is pooling |
| Development data | 12 train and 12 calibration documents, six positives/six negatives in each; 2,048-dimensional vectors | Data coverage and tail estimation are severely limited; training accuracy cannot establish transfer |
| Calibration | Maximize empirical calibration recall subject to empirical FPR ≤1% | Six clean calibration cases give 16.7 percentage-point FPR resolution; there is no population 1%-FPR guarantee |
| External result | Last: 0/400 attacks, 0/400 false positives, AUROC 0.5630. Mean: 1/400 attacks, 1/400 false positives, AUROC 0.8874 | The mean readout has ranking information on this observed source, but negligible useful recall at its frozen operating point |

The sole mean-pooled flagged attack and false positive are the same source pair (`nvidia-150`); its clean member scores higher. This is evidence to investigate content/topic confounding, not proof that confounding is the sole failure mechanism. The NVIDIA-derived clean controls lack human review. This source is now observed development/regression evidence; selecting a new model or threshold on it forfeits its status as a new independent test.

## Verified literature and applicability

### TaskTracker: task-relative activations

Sahar Abdelnabi et al., **“Are you still on track!? Catching LLM Task Drift with Activations,”** arXiv:2406.00799. The method extracts the final input-token state before generation for both task-only and task-plus-document inputs, with an optional task-eliciting wrapper. Logistic probes use their difference; a separate metric-learning method uses triplets. The authors report >0.99 OOD ROC AUC in the studied four-model setup, which is not a low-FPR guarantee for SMAIP. [Paper, §§4–5](https://arxiv.org/html/2406.00799v3).

The released quick-start code directly computes `primary_text_activations - primary_activations`, then calls a probe's `predict_proba`. Its input includes `user_prompt` and `text`; the feature is not a document-only embedding. [Pinned code, commit b4fabe2](https://github.com/microsoft/TaskTracker/blob/b4fabe25504dc1d3f7c6fdf5e50d4bb209a152b0/quick_start/utils.py).

**SMAIP inference:** test task-relative features only when actual tasks vary. Subtracting one constant task-only vector from every current V2 example cannot add information to a standardized linear probe: if `x′=x−c`, then `(x′−mean_train(x′))/std_train(x′)=(x−mean_train(x))/std_train(x)`. A constant-baseline “TaskTracker” retrofit would therefore be vacuous apart from numerical effects. At inference, subtract the available trusted task-only state; never require the unknown clean counterpart of an attacked document.

### Agentic IPI exposure probes: boundary and layer choices matter

Jianshuo Dong et al., **“Your Agentic LLMs Secretly Encode Indirect Prompt-Injection Exposure in Hidden States,”** arXiv:2608.02657v2, reads prefill residual states at a post-assistant boundary in AgentDojo trajectories. Labels indicate latest-tool-result exposure, independently of eventual compromise. Groups hold out attacks, agent instructions and suites. Layer peaks vary by model; reported best-layer maxima are selected descriptively using held-out-strict AUROC, not an independently tested layer-selection procedure. Its Qwen3-8B architecture ablation favors single-layer linear probes over MLPs (mean strict AUROC 0.964 vs 0.912); nearby assistant positions are stronger than post-action readouts. Its AGRI intervention reports Qwen3.5-27B ASR 34.6%→0%, a separate agent experiment. [Paper, §§3–4 and Appendix G](https://arxiv.org/html/2608.02657v2).

The repository's title includes “Latent Signals”; versioned paper titles differ. The code provides selected-position capture, decoder-block residual hooks, and a tokenizer-specific assistant-prefill calibration function. These are useful implementation references, not pretrained Qwen2.5-3B detector weights. [Pinned features](https://github.com/jianshuod/IPI-exposure-signal/blob/03908cce41e4dfb3d32ff5ee6be51ad4195f3171/ipi_aware/probes/featurization/features.py), [pinned residual capture](https://github.com/jianshuod/IPI-exposure-signal/blob/03908cce41e4dfb3d32ff5ee6be51ad4195f3171/ipi_aware/probes/featurization/hidden_states.py).

**SMAIP inference:** compare our content readouts with a precisely located assistant-prefill boundary under the same rendering. Do not transfer a Qwen3 layer number to Qwen2.5 or select our best layer on the final test. A sentinel readout changes the protocol and requires newly fitted/calibrated weights.

### AASE: matched pairs and action gating, with a verification limit

Glen Messenger, **“AASE: Activation-Based AI Safety Enforcement via Lightweight Probes,”** 2026. Google Research's publication page verifies the title, author, AF/AAG/APC techniques and paired contrastive training to reduce topic/style confounds. It reports AAG AUC ≥0.88 on InjecAgent. [Publisher listing](https://research.google/pubs/aase-activation-based-ai-safety-enforcement-via-lightweight-probes/?trk=article-ssr-frontend-pulse_little-text-block).

Its Download link resolves to Zenodo version record **19209689**, identified as a preprint, whose abstract reports 262 InjecAgent prompts and AAG AUC 0.88–1.00. The existing `PRIOR_ART.md` points to 19209688; that may be a concept DOI, but this investigation did not verify that relationship. The PDF could not be fetched through the available web/terminal paths. Exact AAG extraction, split composition and threshold conditions therefore remain unverified here. Do not infer a 1%-FPR result from “100% detection.” [Verified Zenodo version](https://zenodo.org/records/19209689).

**SMAIP inference:** use reviewed clean/injected pairs to diagnose nuisance sensitivity and group them within splits. Paired data alone do not prove topic invariance. Add independent benign content; do not train only on span-deleted synthetic controls.

### InstructDetector: an alternative feature family, not evidence to start with an MLP

Tongyu Wen et al., **“Defending against Indirect Prompt Injection by Instruction Detection,”** arXiv:2505.06311v2 / Findings of EMNLP 2025. It combines last-token hidden states and pooled self-attention parameter gradients for a fixed response, then an MLP. Llama-3.1-8B layer 14 is chosen on validation. It reports 99.60% in-domain and 96.90% News+BIPIA accuracy, with 200 balanced training examples; these are not TPR@1%FPR. The versioned paper reports BIPIA ASR 0.03%, while the repository README retains 0.12%, so preserve version-specific attribution. [Paper](https://arxiv.org/html/2505.06311v2), [published record](https://aclanthology.org/2025.findings-emnlp.1060/), [authors' code](https://github.com/MYVAE/Instruction-detection).

**SMAIP inference:** this gives a reason to retain a nonlinear/gradient branch as future work, not a reason to expect an MLP over the current 12 training vectors to repair transfer. Backpropagation and large gradient features substantially change the compute/memory contract; defer them until simpler forward-only features are measured.

### DataSentinel and Prompt Guard 2: distinct external baselines

Yupei Liu et al., **“DataSentinel: A Game-Theoretic Detection of Prompt Injection Attacks,”** arXiv:2504.11358v2, is a separately fine-tuned detection LLM. It asks for a defender-known secret key and flags when that key is absent from the response. Minimax training alternates adaptive input optimization and detector fine-tuning. The paper reports mostly rounded-zero FPR/FNR in its evaluated task combinations; this is not an activation-probe result or proof of arbitrary-source robustness. [Paper](https://arxiv.org/html/2504.11358v2), [authors' repository](https://github.com/liu00222/Open-Prompt-Injection).

**SMAIP inference:** retain its adaptive-evaluation lesson, but do not add full detector fine-tuning before the forward-only experiment. It is a different baseline, with generation, training and threat-model costs that must be reported separately.

Meta's **Llama Prompt Guard 2** is an 86M/22M BERT-family text classifier with a 512-token context. Its scope is explicit attempts to override instructions; the older separate injection sub-label was removed. The official card reports 86M English recall 97.5% at 1% FPR on a private direct-jailbreak benchmark, and AgentDojo attack-prevention rate 81.2% at 3% utility reduction. These are different benchmarks/metrics and do not establish SMAIP transfer. The card describes application-specific distribution limitations and adaptive attacks. [Official model card](https://github.com/meta-llama/PurpleLlama/blob/main/Llama-Prompt-Guard-2/86M/MODEL_CARD.md).

**SMAIP inference:** compare one frozen Prompt Guard checkpoint as an independently trained text baseline after recording its license, revision, input unit and our calibration protocol. Calibrate document/episode scores after any chunk aggregation; a per-chunk threshold does not preserve document-level FPR. No model download is part of this investigation.

## Low-FPR evaluation: what must change

Xin Tong, Yang Feng and Jingyi Jessica Li's **“Neyman-Pearson classification algorithms and NP receiver operating characteristics,”** Science Advances 2018, distinguishes population type-I-error control from merely constraining empirical error. Its umbrella algorithm selects a classifier threshold using held-out clean-score order statistics. It can wrap a scoring classifier such as logistic regression. [Primary paper](https://arxiv.org/abs/1608.03109), [author project](https://yangfengstat.github.io/projects/neyman_pearson/).

For SMAIP, predeclare one of two honest claim levels:

1. **Empirical operating point:** freeze a calibration-selected threshold and report independent-test TPR/FPR with counts and intervals. Call it calibrated to an empirical 1% budget; do not imply population control.
2. **Statistically controlled operating point:** after classifier/feature selection, use a separate clean calibration sample and a prespecified Neyman–Pearson order-statistic rule with α=0.01 and a declared violation probability δ (for example 0.05). State assumptions and retain a separate final test. This controls the calibration target distribution under its sampling assumptions; it is not a guarantee under arbitrary source shift.

The current `low_fpr.py` zero-event expression is also a useful planning calculation: `1−0.05**(1/n)` is the one-sided 95% upper bound after zero false positives on independent Bernoulli trials at a fixed threshold. It is approximately **39.3% for n=6**, **0.9969% for n=299**, and **0.7461% for n=400**. These calculations do not repair a threshold selected on the same evaluation sample, correlated examples, unreviewed labels or a mismatched target distribution. For maximum-clean-score calibration, the related order-statistic condition is `0.99**n ≤0.05`, also requiring at least 299 independent clean calibration observations. Plan substantially more to permit useful tail estimation rather than treating 299 as a universal sufficient dataset size.

Keep classifier selection data, threshold calibration data and final test groups distinct. Group by underlying document/pair, attack template/family, source and task/transcript; keep overlapping groups together. Use source-held-out folds for development selection and a genuinely untouched final source/protocol. Report pooled and per-source results, as the deployment mixture can hide a bad subgroup. Positive sample size and family coverage determine recall precision separately from benign sample size.

Report both frozen-threshold TPR/FPR and a clearly labeled descriptive test ROC/TPR at 1% FPR. The latter uses test labels to describe ranking and must never silently become the deployment threshold. AUROC 0.8874 alone says little about the extreme low-FPR tail. Model probability calibration (for example temperature scaling) is not the same problem as choosing a safe operating threshold, and monotone score remapping alone cannot improve the ROC ranking.

## Small discriminating experiment matrix — proposed, unmeasured

This is a staged design, not a mandate to launch a GPU job. All candidates use the current pinned Qwen2.5-3B model and its existing fp16/batch-one runtime. Extract once, fit small probes on CPU, keep exact feature identities. New extraction semantics require a new versioned protocol rather than changing format-2 artifacts in place.

### Preconditions before spending GPU time

- Define the label as an attacker-inserted instruction attempt in untrusted content, distinct from whether an agent obeys it. Review clean controls, retain legitimate imperative text/code and security discussions quoting attacks as hard negatives, and record ambiguities.
- Build a larger training set across authors, content sources, task families, styles and attack families. A concrete initial development budget is 500–1,000 reviewed clean/injected pairs plus independently collected clean documents; this is a proposed budget, not a literature-derived guarantee. Retain grouped learning curves at 50/200/all available pairs to distinguish data shortage from feature choice.
- Reserve independent model-selection groups, ≥1,000 reviewed benign calibration cases when feasible, and a separately held-out final source with enough attacks to estimate recall by family. Row counts do not substitute for independent documents and authors/templates.
- Freeze the candidate list, selection rule, grouping, label policy, maximum length, rejection/coverage accounting and final metric. Preserve the present external set as a regression set. Do not repeatedly inspect the future final source to pick features.

### Stage A: nine forward-only feature candidates

Use decoder blocks **6, 18 and 30** after validating them against the pinned configuration; zero-based indexing remains explicit. For each block, fit the same regularized logistic classifier on:

| Feature | Input/readout | Question isolated |
| --- | --- | --- |
| `content-last` | Fixed V2 inspection context; last fully contained tool-content token | Is the current readout useful with adequate data at any of three depths? |
| `content-mean` | Same context; float32 mean of the same content mask | Is broad content aggregation more transferable than the trailing content token? |
| `inspection-boundary` | Same inspection-context prefix plus a precisely documented assistant-generation boundary; read the pre-generation boundary state | Is an assistant-facing summary position better than content-only readout? |

Changing the suffix must leave the original tool-content prefix tokenization unchanged, or the protocol must record and evaluate the difference. With a causal model, later suffix tokens should not change earlier content states; verify that invariant on a small diagnostic. Decode and save the selected token and its neighbors; `-1` is not a portable semantic definition. No generated rationale or action is needed for these views. Select on grouped model-selection data using a low-FPR-oriented objective, not peak final-test AUROC; retain AUROC as a diagnostic.

### Stage B: two context variants at the selected depth

Collect two new views for the same reviewed task/document groups:

| Feature | Definition | Discrimination sought |
| --- | --- | --- |
| `task-boundary` | Actual authorized task, tool identity and bounded pre-tool context, then tool result and assistant boundary | Whether missing task/context information explains part of failure |
| `task-delta` | The preceding vector minus a separately rendered trusted task/pre-tool-context-only boundary vector | Whether task-relative change improves upon the raw task-conditioned state |

Use the same extraction family for both views; cache task-only states per exact trusted context hash. Compare `task-boundary` with `inspection-boundary` to test context, then `task-delta` with `task-boundary` to test subtraction. A difference between task-delta and the present content mean would otherwise mix several interventions. The bounded context policy and any overlength refusal must be recorded; a 512-token document-only success rate does not imply 512-token task/transcript coverage.

### Stage C: limited classifier/data ablations on saved vectors

Keep logistic regression as the primary classifier. On the winning feature, use three prespecified L2 strengths around the current default (`0.005, 0.05, 0.5`) with grouped selection, and one small MLP (`2048→32→1`, weight decay/early stopping/seeds fixed beforehand) as an optional counterexample. The MLP has about 65,600 parameters and should be deferred if reviewed training data remain tiny. Do not assume that “activation probe” implies a nonlinear model. Compare learning curves and worst-source low-FPR behavior before expanding capacity or concatenating layers. Changes to optimization should be motivated by convergence diagnostics, not by the failed external threshold alone.

The main staged budget is nine base feature candidates plus two context candidates; probe fits reuse vectors. Do not run a full cross-product of many backbones, layers, context prompts, MLPs and thresholds. If data enlargement makes the existing layer-18 mean competitive, prefer that simpler explanation before redesigning the stack.

### A16 feasibility and records

The frozen 3B fp16 parameter payload is approximately 6 GB before framework/runtime overhead. Three selected layers and a few pooled vectors do not require three backbone copies. With batch one and no backward pass, this design stays close to the feature workload already completed on the A16; exact peak memory/time remain to be measured. For scale, eleven 2,048-dimensional float32 vectors require about 88 KiB per example, or about 860 MiB for 10,000 examples, excluding metadata; repeated task-only vectors can be deduplicated. Persist pooled views rather than whole token-state tensors. This is a storage estimate, not a promised throughput result.

Preserve model/tokenizer/chat-template revisions, source hashes, tensor precision, layer convention, token/span diagnostics, task/context hashes, selected-token count, overlength status, per-example latency and peak allocated memory. New fingerprints must distinguish content mean, boundary position and task-relative contexts. Existing V2 weights and thresholds remain untouched and separately reportable.

## Relating detector results to the BRD

The local BRD capture maps acceptance to low-FPR detector evidence, comparable structural/detector/gateway ablations, real utility, ASR, latency and cost. A detector improvement only advances the learned-detector component. AgentDojo explicitly evaluates tool-using agents and notes that even undefended agents can fail legitimate tasks; it is a suitable model for measuring utility separately from attack success. [AgentDojo primary paper](https://arxiv.org/abs/2406.13352).

After selecting/calibrating a candidate, run a bounded agent evaluation with the same model, tasks, decoding and budgets across no-defense, keyword, least-privilege, probe, gateway and full-stack factors. Measure legitimate task completion on clean and attacked episodes, unauthorized proposed and accepted effects, detection FPR, quarantine rate, errors, and overhead. Include adaptive attacks that know the detector and optimize for both evasion **and** an attacker objective; evasion by deleting the malicious instruction is not a successful joint attack. Count source groups/episodes in uncertainty estimates rather than treating every correlated turn as independent.

Keep the deterministic gateway as the tool authorization boundary. CaMeL is a relevant structural precedent: it extracts control/data flow from trusted queries and checks capability policies at tool calls, independently of an activation score. Its security claim belongs to that particular interpreter/policy design and cannot be inherited by SMAIP. [CaMeL primary paper](https://arxiv.org/abs/2503.18813).

A candidate passes the detector experiment only if independent frozen-threshold recall improves while achieved FPR and coverage are honestly reported. It passes the product experiment only if the measured safety gain survives the BRD utility/overhead comparison. Ties or detector redundancy remain legitimate outcomes. There is no literature basis here for a “novel detector” claim; a defensible contribution would be the measured composition and its documented limits.

## Source-verification limitations

- Primary papers, authors' repositories and official model cards were used; search snippets or secondary reviews were not used to settle method details.
- AASE's publisher and Zenodo abstracts were inspected, but its PDF and exact replication protocol remain unavailable through the attempted paths. Its AAG results should be treated as reported, incompletely audited evidence.
- Upstream papers/code were not executed. Their numerical results are attributed reports, not replications. InstructDetector's README/paper result mismatch is retained explicitly.
- The live BRD is not independently revalidated by this sub-investigation; alignment references the existing local version-1.2 capture and current owning code/results. Final scope/acceptance decisions belong in the main improvement plan.
