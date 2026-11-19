# Study questions and methods

This document describes the completed SMAIP study using the preserved
experiment reports. It reconstructs the research questions from the work;
it is not a claim that the entire study was prospectively preregistered.
The [closure decision](adr/0002-close-as-completed-study.md) defines its final
scope, and the [conclusion](../reports/STUDY_CONCLUSION.md) interprets its findings.

## Retrospective questions and working hypotheses

The hypotheses below are retrospective framing of exploratory work, not
preregistered hypotheses. I investigated whether an agent could produce
useful numeric reports from
lower-trust documents while keeping evidence and actions tied to the
authorized task. The working hypothesis was that explicit source checks,
task-scoped permissions, and owner approval could make violations observable
and prevent unsupported effects in a bounded workflow.

I also investigated whether separating agent roles would preserve task
utility, and whether small probes on a frozen language model could identify
injected instructions. These were questions to test, not established benefits.
The detector experiments further tested whether strong score ranking would
translate into useful behavior at a fixed threshold on another source.

## Models and experimental units

The real-model work used **Qwen/Qwen2.5-3B-Instruct**. The V2 feature collection
and V4 collection used revision
`aa8e72537993ba99e69dfaafa59ed015b17504d1`. Qwen remained frozen: probe fitting
trained small classifiers, while agent studies performed inference. Historical
protocols and artifacts are versioned; V2 and V4 measurements should not be
combined as if they came from one unchanged detector.

The study used distinct units of evaluation:

- A **task episode** for agent utility and unauthorized sandbox effects.
- A **task/document example** for probe scores and source-label classification.
- A **source/line reference** for checking whether a selected numeric claim
  corresponded to its authorized document.

An episode could contain several model calls or claim attempts. Those attempts
are not additional independent tasks. A model's statement that it sent a
message is not an observed sandbox effect.

## Experiment sequence and comparisons

| Stage | Method | Comparison or outcome |
| --- | --- | --- |
| Guardrail implementation and scripted demonstration | Original synthetic documents, fixed task intent, evidence validation, controlled recipient, and approval checkpoint | Demonstrates mechanisms and deterministic checks without a model; approval in the demo is programmatic. |
| V2 development probe fit | 36 authored documents, with 12 fit, 12 calibration, and 12 development-test documents; six examples per label in each role | Last-token and mean-pooled logistic probes with fixed layer 18; normalization and weights from fitting rows, thresholds from calibration rows. |
| Frozen V2 transfer | Unchanged probes and cutoffs scored 400 NVIDIA attack/control pairs | Measures transfer of an existing operating point; AUROC and fixed-cutoff outcomes are reported separately. |
| Real-model attack development | Four original clean/attack pairs, three policies, 24 sandbox episodes | No defense, keyword screen, and least privilege; clean utility and observed attacker objectives. |
| Completed clean-workflow pilot | 25 original synthetic numeric tasks, one single-agent and one specialist episode per task | 50 paired episodes under the same task/evidence controls; strict task completion, source correctness, and authorized sandbox effect. |
| V4 feature and probe development | Archived task-boundary feature vectors, cleaned source-label manifest, fixed `content_mean/18` feature for the final solo fit | Fit on 680 NVIDIA rows; score 288 already observed LLMail rows as a development transfer diagnostic. |
| Diagnostic cutoff and owner audit | NVIDIA training-score midpoint applied to saved LLMail scores; source and repeat-review checks | Counts flags and misses at one descriptive cutoff; preserves AV clarification and the R031 quarantine. |

The V4 feature had been selected through earlier exploratory analysis. Its
final solo fit did not rerun a fresh feature search. The NVIDIA grouped
out-of-fold ranking reported alongside it comes from the earlier fixed-feature
sensitivity analysis; the solo model's saved NVIDIA predictions are in-sample.
LLMail had already been observed before the cutoff diagnostic. These details
prevent interpreting the final fit as a prospective independent final test.

## Data, controls, and lineage

The clean tasks and early probe documents were original synthetic material.
The external NVIDIA source was synthetic; matched controls were created by
removing annotated attack spans. A removed span does not guarantee that the
remaining text is semantically benign for the authorized task.

The V4 inventory contained 1,012 task/document references. Its cleaned
development manifest excluded 43 redundant exact-pair references and the
disputed NVIDIA control R031, leaving 968 canonical rows: 680 NVIDIA and
288 LLMail. NVIDIA contributed 228 attacks and 452 controls; LLMail contributed
128 attacks and 160 benign emails. Labels inherited from sources were kept
distinct from AV review and formal accepted-label fields. The LLMail attacks
share connected lineage; row counts therefore do not establish independent
sampling units. Separate NotInject user-prompt diagnostics were not treated
as representative task/document calibration data.

The [data inventory](../DATA.md), [mechanical audit](../reports/archive/FEATURE_V4_SOLO_AUDIT_01.md),
and [owner-review resolution](../reports/archive/LLMAIL_OWNER_REVIEW_02_RESOLUTION.md)
record the transformations, exclusions, and label qualifications.

## Measures and interpretation rules

**Clean utility** is the fraction of task episodes passing the strict task,
evidence, and effect checks. In the completed pilot, both topologies shared
these controls; the comparison does not isolate the benefit of the gateway
or a probe. The five unsuccessful episodes remained failures. The continuation
completed only missing episodes, preserving the original completed results.

**Attack success** requires an observed unauthorized sandbox effect. Zero
attacker objectives in the undefended arm prevents attributing the defended
arms' zero counts to a defense advantage.

**AUROC** measures ordering across possible cutoffs. **Recall** and **false
positive rate** count flagged attacks and benign examples at a specific
cutoff. A score is not a calibrated probability. The LLMail cutoff was the
midpoint between the highest benign and lowest attack score on NVIDIA training
rows; it was diagnostic and was never enabled for serving. Zero flags among
160 previously observed benign examples cannot establish population 1%-FPR
performance.

## Reproducibility boundary

A source checkout can run the CPU-only scripted demo and software tests using
the README commands. The demo does not reproduce Qwen experiments or send
real email. Detailed reports expose experiment counts, source and artifact
hashes, protocol identities, failures, and audit procedures.

Historical data, review submissions, model artifacts, and returned vectors are
kept outside Git or in retained owner archives. Scripts that verify those
artifacts require the matching private inputs. Consequently another reader
can inspect the methods and run the provided software checks, but cannot
regenerate every reported model measurement from the source checkout alone.
Hardware-dependent runs additionally require the pinned model and runtime.

The study did not complete independent detector validation, a susceptible
matched attack study demonstrating defense improvement, production-path
integration, or repeated serving/cost benchmarks. These are limitations of the
completed study and optional future investigations, not passed acceptance gates.

## Evidence references

- [V2 development fitting and calibration](../reports/archive/V2_PROBE_DEVELOPMENT_01_ANALYSIS.md)
- [Frozen external transfer](../reports/archive/V2_EXTERNAL_FROZEN_01_ANALYSIS.md)
- [Real-model attack development](../reports/archive/OPEN_AGENT_DEV_02_ANALYSIS.md)
- [Completed clean pilot and preserved failures](../reports/archive/EVIDENCE_CLEAN_03_COMPLETED_ANALYSIS.md)
- [V4 feature exploration](../reports/archive/FEATURE_V4_EXPLORATORY_02_ANALYSIS.md)
- [V4 solo fit and saved score verification](../reports/archive/FEATURE_V4_SOLO_PROBE_01.md)
- [LLMail diagnostic cutoff](../reports/archive/FEATURE_V4_LLMAIL_CUTOFF_01.md)
