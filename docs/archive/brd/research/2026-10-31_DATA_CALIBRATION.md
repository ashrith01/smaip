# Data and calibration research for SMAIP V2

Research date: October 31, 2026. This is a proposed experiment and evidence plan, not a training run or a low-FPR certification. No dataset payload, model, paid API or GPU job was downloaded or run for this research. Sources below are upstream papers, author repositories and dataset cards; their current metadata was checked on this date.

## Decision

Keep the existing feature protocol and artifacts as reproducible baselines. Spend the next effort on reviewed, grouped data and a separate model-selection/calibration/final-test protocol. A larger number of variants of the same synthetic templates will not resolve the evidence gap. The primary scientific question is whether a frozen probe ranks new attack/benign contexts well enough in the upper benign-score tail to operate usefully at 1% FPR. Overall AUROC and a zero-alarm classifier cannot answer that question alone.

The first affordable gate is a reviewed development corpus with a learning curve; the more demanding statistical gate is a separate, representative benign calibration sample plus a final evaluation sample. Do not merge those budgets or label the former an independent acceptance test.

## What the repository establishes

Inspected: `DATA.md`, `src/smaip/probes/{manifest,low_fpr,pipeline_v2,external_v2,logistic,protocol}.py`, `reports/archive/V2_PROBE_DEVELOPMENT_01_ANALYSIS.md`, and `reports/archive/V2_EXTERNAL_FROZEN_01_ANALYSIS.md`.

* Development has 36 assistant-authored documents, split 12/12/12, six per label in each split. Each probe fits 2,048 standardized activation coordinates from 12 training observations. Training-only standardization and explicit document labels are sound safeguards; they do not create independent data or reliable generalization.
* Last-token development test: 0/6 TP, 0/6 FP, AUROC 1.0000. Mean pooling: 4/6 TP, 1/6 FP, AUROC 0.9444. These ranking/operating-point differences justify checking the benign upper tail, rather than lowering the threshold against observed tests.
* Frozen external scoring: last-token 0/400 TP, 0/400 FP, AUROC 0.5630; mean pooling 1/400 TP, 1/400 FP, AUROC 0.8874. Both mean-pooling positives are the same clean/injected healthcare pair; the clean control scores higher. There is ranking signal in mean pooling but almost no useful detection at its frozen threshold.
* The 400 NVIDIA clean controls were made by exact annotated-span deletion. They are derived labels, not human-reviewed benign originals. Related wrappers and context generation remain possible dependence. The corpus has now been observed: keep it as regression/development evidence and obtain a fresh final test.
* `calibrate()` maximizes calibration recall subject to **empirical** FPR <=1%. Its zero-event field and `sample_size_screen_passed` are conditional screens, not certifications. At six benign calibration cases, the empirical constraint permits zero FPs and can force a useless high threshold. At 299 benign cases it permits two FPs; simply increasing `n` does not turn this selector into a 95%-confidence population-FPR procedure.
* `validate_manifest()` rejects cross-split declared `source_id`, `group_id`, positive `attack_family`, and normalized exact text. It cannot verify those declarations, near-duplicate templates, common authorship or semantic label correctness. `pipeline_v2.read_corpus()` presently requires `development-only` original material and `third_party_material is False`; the new external-source fitting plan requires an explicit, reviewed adapter/schema change before execution.

The root investigation also replayed the training objective: both probes fit their 12 training labels after one gradient step, and the regularized objective stabilizes by 200–400 steps. This supplies no evidence that more epochs would fix transfer.

## Which outside data is useful

An injection label describes an attempted trust-boundary violation in a setting. Harmfulness, successful jailbreak, defense evasion and successful unauthorized tool execution are different targets. Keep them as separate fields. A failed attack is not automatically benign; a quoted attack description is not automatically malicious. SPML's authors explicitly discourage using their dataset to train a context-free injection detector, because the same payload can be legitimate under another system prompt and their techniques are limited. Its system/user pairs are a useful context-sensitivity diagnostic, not a substitute for tool-result training data. [SPML author FAQ and schema](https://prompt-compiler.github.io/SPML/).

| Source and direct primary evidence | Appropriate proposed use | Label, grouping and license conditions |
| --- | --- | --- |
| [Microsoft LLMail-Inject card](https://huggingface.co/datasets/microsoft/llmail-inject-challenge/blob/main/README.md), [paper v2](https://arxiv.org/abs/2506.09956v2) | High-priority independent-author attack source for email/tool-action stress testing. Begin with a capped sample, not the full raw release. | Card declares MIT. Raw submissions include team/scenario/time metadata; group author/team and near-duplicate attack lineages. `attack_attempt` annotations use an API trigger or LLM judge; review ambiguous cases. Defense failure is not benignness. Card supplies only 203 additional benign FP-test emails. Reconstruct relevant untrusted email content and preserve task metadata. |
| [NotInject author card](https://huggingface.co/datasets/leolee99/NotInject/blob/main/README.md) | 339 benign trigger-word examples for over-defense diagnostics. Keep a named diagnostic slice separate from representative calibration. | MIT; 113 examples each using one, two or three trigger words. These are prompts, not naturally sampled vendor-tool results. Review the transformation if inserted into tool context. Related prompt forms must stay grouped. |
| [AgentDojo author repository](https://github.com/ethz-spylab/agentdojo), [license](https://github.com/ethz-spylab/agentdojo/blob/main/LICENSE), [2024 paper](https://arxiv.org/abs/2406.13352) | End-to-end task utility and attack-success evaluation; optionally derive detector diagnostic slices under a separate import decision. | MIT repository license, with any individually marked upstream exceptions checked at the chosen commit. Tasks and tool content are interdependent. Follow current `DATA.md`: do not vendor its environment/tasks/attack corpus here. A detector score is not an AgentDojo agent result. |
| [InjecAgent author repository](https://github.com/uiuc-kang-lab/InjecAgent), [license](https://github.com/uiuc-kang-lab/InjecAgent/blob/main/LICENCE), [2024 paper](https://arxiv.org/abs/2403.02691) | External indirect-tool-injection stress testing, especially attacker tool/action objectives. | 1,054 cases spanning 17 user tools and 62 attacker tools; repository declares MIT. Group shared tool responses, attacker templates and objective variants. Cases are not 1,054 independent benign/attack pairs. Current `DATA.md` prohibits vendoring test cases here. |
| [BIPIA author repository](https://github.com/microsoft/BIPIA), [data-specific license exclusions](https://github.com/microsoft/BIPIA/blob/main/LICENSE) | Task-conditioned benchmark and held-out template diagnostics, after component-specific provenance review. | MIT code does not license every underlying context. WikiTableQuestions and Stack Exchange components are CC BY-SA 4.0; invoice rows are MIT; other context origins need their own checks. Current `DATA.md` prohibits vendoring benchmark/context data. |
| [Agentic Boundary Pairs author card](https://huggingface.co/datasets/3nesdeniz/agentic-prompt-injection-boundary-pairs) | Small supplementary paired hard-negative development source, after manual relevance review. | CC BY 4.0; 1,200 synthetic rows/600 pairs from 50 workflows. Scenario-isolated splits and explicit boundary metadata are useful. Author review covered 180 pairs, not every row; labels are intended policy boundaries and include direct requests. It is not independent real-traffic validation. |
| [PIArena author card](https://huggingface.co/datasets/sleeepeer/PIArena/blob/main/README.md), [platform repository](https://github.com/sleeepeer/PIArena) | Future context/long-document stress testing rather than first-round fitting. | Card declares MIT and exposes task, clean context and injected task. Underlying contexts include Dolly and several other datasets; verify their component terms instead of treating the wrapper's MIT metadata as a blanket grant. Many listed contexts exceed the current 512-token protocol. |

Version caution: LLMail's paper v2 was revised October 9, 2026 and reports 208,095 distinct human-written attack prompts from 839 participants. The browsed card separately lists 370,724/90,916 raw phase submissions and 160,741/37,303 annotated unique phase prompts. These are different counting units/versioned artifacts; do not add them together or silently substitute one denominator. The published ASR of another agent is not an expected SMAIP detector result. [Paper v2](https://arxiv.org/abs/2506.09956v2), [card](https://huggingface.co/datasets/microsoft/llmail-inject-challenge/blob/main/README.md).

Sources to defer:

* [Lakera Gandalf ignore-instructions](https://huggingface.co/datasets/Lakera/gandalf_ignore_instructions/blob/main/README.md): MIT, but the 1,000 rows expose `text` and embedding `similarity`, not audited binary labels. The collection was filtered for similarity to an override phrase; its authors acknowledge some non-injection noise. Use a reviewed diagnostic sample, never label similarity as ground truth or infer a representative benign distribution.
* [xTRam1 safe-guard](https://huggingface.co/datasets/xTRam1/safe-guard-prompt-injection/blob/main/README.md): the reviewed card lacks a license declaration and describes synthetic attacks seeded from several other datasets. Public downloadability is not a grant. Resolve the exact data terms and seed provenance before import; do not cite its reported same-method accuracy as transfer evidence.
* [deepset prompt-injections](https://huggingface.co/datasets/deepset/prompt-injections/blob/main/README.md): metadata contains both top-level Apache-2.0 and nested CC BY 4.0; 546 train/116 test rows and little generation/annotation detail. Resolve data-specific terms and origin/overlap before using it as training or final evidence. A mirrored/repackaged copy is not an independent source.

## Split design: preserve the actual unit of independence

Proposed provenance fields: upstream dataset/revision/license, source URL/content hash, original document/context ID, clean/injected pair ID, author or generator, generation batch, base template ID, attack family, domain, length, trust role, annotation origin, reviewer and transformation. This is a design recommendation, not a claim these fields already exist.

Build a graph joining exact/normalized duplicates, clean/attack counterparts, paraphrase/template variants, shared base contexts and known author/generator lineages. Allocate connected groups before fitting. Include token-normalized/MinHash and semantic near-duplicate review; neither alone proves independence. Keep paraphrases, translations, domains with only entity-name substitutions, and chunked fragments of one document in the same group. Reserve whole upstream sources for separate source-transfer stress tests.

Use three named evaluations rather than conflating difficulty axes:

1. **Target-use distribution:** independent source-context groups from the actual vendor-research setting, with the domain/format mixture fixed before scoring. Calibration and target test must represent this same declared benign distribution. A newly withheld domain changes the estimand; its FPR is an OOD stress result, not covered by the original calibration guarantee.
2. **Template/family transfer:** genuinely withheld attack construction lineages, with paired clean counterparts. Report per-family recall and uncertainty. Broad semantic families should retain honest names rather than being relabeled by split to satisfy validation.
3. **Source/domain transfer:** a whole author/dataset/domain held out from every fitting, selection and calibration decision. Test on the source once the pipeline is frozen. Source independence does not guarantee representative deployment sampling.

The current schema forces *every* declared positive family into exactly one of train/calibration/test and has no model-selection split. For the next study either retain that restriction explicitly or version the schema to separate `attack_family` from `template_lineage_id` and encode named holdout axes plus a development split. Do not bypass the validator with invented per-row source/family IDs. Genuine family-disjointness and ordinary in-distribution validation answer different questions. The same is true of upstream dataset identity versus source-context identity: store both.

Calibrating a threshold and repeatedly choosing a pooling method, layer, feature context or regularization using that calibration's recall makes it model-selection data. Give selection a separate development set, freeze one final scalar score, and only then open calibration. Changing context, pooling or normalization after calibration requires a new calibration artifact. Existing observed development and NVIDIA results may guide the next proposal but cannot serve as its untouched test.

## Low-FPR arithmetic and the claim it supports

For a detector rule fixed **before** an independent benign test, zero FPs in `n` IID Bernoulli observations gives the one-sided 95% exact upper endpoint `1 - 0.05^(1/n)`. With nonzero FPs use the exact binomial endpoint, not a normal approximation or the zero-event expression. This is a sampling-model statement about the declared target distribution, not a guarantee under arbitrary domain shift. [NIST exact binomial limits](https://itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbino.htm).

The following are direct calculations from that binomial model:

| Independent benign test size | Zero-FP 95% upper endpoint | Interpretation |
| ---: | ---: | --- |
| 6 | 39.304% | Current development scale cannot assess a 1% tail. |
| 100 | 2.951% | Zero observed alarms is still insufficient. |
| 299 | 0.997% | Minimum zero-event count for a *fixed-rule* 1% claim under assumptions. |
| 400 | 0.746% | Existing external set fails independence/label/population conditions; mean has a FP. |
| 1,000 | 0.299% | Tail information remains sparse. |
| 2,000 | 0.150% | More practical reporting scale for a low-FPR detector. |

One FP in 400 has an exact one-sided 95% upper endpoint about **1.180%**. Twenty FPs in 2,000 is observed 1% but upper endpoint **1.450%**. At most 12 FPs in 2,000 gives upper endpoint about **0.970%**. Repeating tests until one passes or choosing the winning detector on final-test labels invalidates that ordinary single-test interpretation. Count independent benign contexts, not documents obtained by repeating templates. Cluster bootstrap can describe observed cluster uncertainty but cannot manufacture an IID 1%-FPR guarantee.

For **threshold selection**, use a predeclared Neyman–Pearson order-statistic rule: fit/freeze the score independently; sort `n` fresh benign calibration scores ascending; choose the least conservative rank `k` satisfying `P[Binomial(n,1-alpha) >= k] <= delta`; flag strictly above that score. This controls `P_calibration(FPR > alpha) <= delta`. Implement ties conservatively (`nextafter` matches the current `>=` comparator). For `alpha=.01, delta=.05`, 299 benign scores support only the maximum-score boundary. This is an order-statistic calibration theorem, not an application of a fixed-test confidence interval to an arbitrarily optimized threshold. [Tong, Feng and Li, Science Advances, February 2, 2018, Proposition 1](https://pmc.ncbi.nlm.nih.gov/articles/PMC5804623/).

Equivalent directly calculated allowable upper-tail counts for that rule are 0/299, 0/400, 4/1,000, 8/1,500, and 12/2,000. Current empirical-FPR selection instead permits 2/299, 4/400, 10/1,000 and 15/1,500. Thus it spends more tail risk than the proposed confidence-controlled procedure. Keep a future calibration artifact's `alpha`, `delta`, selected rank, benign-group count, comparator, frozen-score hash and sampling-frame assumptions explicit. Treat insufficient independent calibration data as “insufficient evidence,” rather than silently returning a certified detector.

The NP rule does not guarantee useful recall. Parametric alternatives can reduce minimum counts by imposing assumptions; their assumptions must be justified, not borrowed for convenience. [Tong et al., JMLR 2020](https://www.jmlr.org/papers/v21/18-577.html).

Conformal prediction/CRC terminology needs care. Split-conformal marginal coverage is not automatically a benign-conditional FPR bound. CRC controls expected monotone loss averaged over calibration/test randomness; that is different from a 95%-probability bound on the deployed rule's population FPR. A label-conditional construction may target benign errors under exchangeability, but its exact guarantee must be stated. [Angelopoulos et al., ICLR 2024](https://research.google/pubs/conformal-risk-control/). Risk-controlling prediction sets and Learn then Test offer high-probability/multiple-testing approaches when selecting among candidate rules, with their own assumptions and correction costs. For one frozen scalar detector the NP construction is simpler. [Bates et al., 2021](https://arxiv.org/abs/2101.02703), [Angelopoulos et al., 2022 version](https://arxiv.org/abs/2110.01052v5).

Also define the level at which 1% applies. Two independently calibrated 1%-FPR screens combined by OR can have up to 2% FPR. A conservative union allocation uses each `alpha=.005`, with calibration failure budgets `.025` each for simultaneous 95% confidence; the zero-tail minimum then becomes 736 independent benign scores per screen. Prefer selecting one score or freezing one fusion function on development data and calibrating that final function directly. For an episode with ten screened documents, a union bound from document FPR 1% is as large as 10%; report empirical episode interruption/utility separately. No independence between screens/documents is needed for those union bounds.

## Bounded learning experiment before acceptance-scale collection

There is no defensible universal “ten rows per feature” rule that proves this 2,048-coordinate ridge probe adequate. Modern logistic-regression theory also warns against classical high-dimensional MLE inference; it is not itself a sample-size theorem for this ridge probe. [Sur and Candès, PNAS 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6642380/). Ridge/elastic-net methods are established ways to fit penalized logistic models; regularization strength remains a development choice. [Friedman, Hastie and Tibshirani, JSS 2010](https://www.jstatsoft.org/article/view/v033i01).

**Stage A, local saved-vector diagnostics:** preserve current artifacts and repeat no GPU work. Inspect train/calibration/NVIDIA score distributions, per-pair score differences, source/length strata, and near-zero feature scales. Compare weights/norms and the upper benign tail. Treat every analysis as development. Any refit using observed external labels must be named as such. Scalar probability calibration alone will not improve ranking; a monotone rescaling cannot rescue an absent low-FPR ranking signal.

**Stage B, useful small pilot:** review 256 fitting documents (128/label), 256 selection documents (128/label), and 400 new benign threshold-development contexts plus 100 attacks: **1,012 documents**, independently grouped. Keep layer 18, Qwen revision, tool-content masking and 512-token rendering fixed. This is a feasibility study, not the final acceptance set. Include at least three genuinely independent author/source streams and same-topic hard negatives. If enough real independent contexts cannot be obtained, report that limit instead of padding with paraphrases. Evaluate whether any candidate has worthwhile partial ROC/recall near 1% FPR; stop if the signal is absent.

**Stage C, planned learning curve after the pilot gate:** enlarge fitting to **1,024** documents (512/label) and selection to **512** (256/label). Fit nested group-preserving training sizes **128, 512, 1,024**, with both pooling methods and `l2={.05,.5,5}`: **18 CPU fits**. These values are proposals, not literature-established optima. Freeze the solver/objective and record loss convergence and weight norms; do not substitute library `C` for the current mean-loss-plus-L2 coefficient without matching conventions. Prefer one pinned vectorized CPU implementation, checked against the current scorer/objective on saved vectors. The existing Python loops would require about **8.18 billion feature visits** for 400 steps over that grid, before counting gradient/prediction arithmetic. Do not promise an instant local sweep. A second grouped partition adds another 18 fits only if development instability warrants it. Select one model/configuration before opening statistical calibration; no layer sweep in this first collection.

Training and selection metrics should include partial AUC over FPR 0–1%, development recall at a stated conservative threshold, per-source/family recall, clean/attack pair score differences, length/format slices, and counts of excluded long/ambiguous examples. Report source-held-out failures even if aggregate AUROC improves. Refuse an “improvement” based only on memorized wrappers or a lower chosen threshold.

## Separate acceptance-scale data and resource budget

Conditional on a promising learning curve, pre-register this target-use study:

| Role | Benign | Attack | Use |
| --- | ---: | ---: | --- |
| Fitting | 512 | 512 | Frozen score fit; Stage C data. |
| Selection | 256 | 256 | Choose pooling/regularization once. |
| Statistical calibration | 1,500 | 300 | Fresh IID benign contexts for NP threshold; attacks characterize recall only after model choice. |
| Untouched target final test | 2,000 | 500 | One frozen configuration; exact FPR endpoint, recall uncertainty and declared BRD operating point. |
| Total | 4,268 | 1,568 | **5,836 documents**, excluding the known 36/800 regression material and named external stress suites. |

The Stage B threshold-development set (400 benign plus 100 attacks) is also
additional if already inspected. It cannot be counted as fresh statistical
calibration or untouched final testing. Fitting/selection groups may be nested
as specified, but preserve every consumed set's actual role in the study record.

Those counts are collection targets, not a promise that the listed public datasets can supply representative independent contexts. At least 1,500/2,000 genuinely independent benign calibration/test contexts must come from the declared vendor-use sampling frame. If the available corpus contains 100 underlying templates, 2,000 variants do not qualify. Sampling across unrelated public benchmarks establishes benchmark-mixture FPR, not deployment FPR. OOD source/family tests stay separately reported.

For a 500-attack IID test, an ordinary normal planning approximation gives a 95% half-width about 4.4 percentage points near 50% recall and 2.6 points near 90%; actual reporting should use exact/binomial or group-aware intervals as appropriate. Five hundred aggregate attacks do not give precision per rare family. Human review should adjudicate every ambiguous label; for nominal planning, one minute per document is **97.3 reviewer-hours**, and a second review of 20% adds **19.5 hours**, before disagreements. If that is unaffordable, run Stage B and make the narrower diagnostic claim. Do not claim human review merely because automated structural screens passed.

The frozen protocol requires **one Qwen forward per document** to collect both last/mean vectors. For 5,836 documents at no more than 512 rendered tokens, the token-position ceiling is **2,988,032**; raw two-pool float32 vector storage is **95,617,024 bytes (~91.2 MiB)**, with JSON/storage overhead additional. Extraction time needs a measured throughput pilot: at 1 document/sec it is about 97 minutes, at 5/sec about 19.5 minutes, excluding model load/audit. These are arithmetic scenarios, not measured A16 estimates. Make one future bounded feature collection only after labels, licenses, split groups and sample counts are ready; do all saved-vector fitting locally. This research authorizes no GPU expense.

The 512-token rule excludes longer real contexts. Track pre-score exclusions and compare included/excluded domains; do not crop away attacks or discard examples based on scores. A longer-context/chunking protocol would be a separately versioned experiment and need new features and threshold calibration, especially if document prediction becomes the maximum of chunk scores.

## Completion criteria for the next evidence milestone

1. Publish the sampling frame, source/license inventory, reviewed label policy, grouped split manifest and frozen experimental choices before feature extraction.
2. Demonstrate nontrivial detection at the conservative target operating point on selection data; otherwise retain the detector as experimental and prioritize agent permission/gateway controls.
3. Freeze a single score/configuration, calibrate it using an explicitly implemented confidence-controlled rule, then run a fresh final test once. Report exact counts/endpoints, sampling/label limits and results of named OOD suites, including failures.
4. Measure agent utility, attacker-goal success and per-episode interruptions separately. Detector FPR/TPR cannot establish full-stack BRD acceptance or causal reduction in agent harm.

No code/model artifacts were modified by this research note. Dataset import, schema evolution, calibration implementation, feature collection and evaluation remain proposed work.
