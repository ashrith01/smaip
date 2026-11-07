# SMAIP results and limits

This page separates agent task completion, probe ranking, fixed-cutoff
classification, and attacker effects. Numbers are from preserved development
experiments, not a combined final benchmark. The original Qwen2.5-3B-Instruct
backbone was frozen. The [data inventory](../DATA.md) records source origin,
transformations, and license declarations.

## What was measured

| Experiment and evidence | Data and setup | Exact observed result | Interpretation |
| --- | --- | --- | --- |
| [Audited clean agent pilot](EVIDENCE_CLEAN_03_COMPLETED_ANALYSIS.md) | 25 original synthetic numeric tasks; 50 Qwen episodes, one run per single-agent and specialist arm | **22/25 (88%)** single-agent and **23/25 (92%)** specialist tasks passed strict evidence/effect scoring | Shows this bounded agent can often complete the task under its common evidence and authority policy. One-task difference is not proof of specialist superiority. No attacks or V4 probe were tested in this pilot. |
| [First V2 probe development test](V2_PROBE_DEVELOPMENT_01_ANALYSIS.md) | 36 authored documents: 12 fit, 12 calibration, 12 test; test has six attacks and six benign | Frozen linear cutoff: **0/6** attacks caught, **0/6** benign flagged. Mean-pool cutoff: **4/6** caught, **1/6** benign flagged. | The test is too small to support low-FPR claims; even a good AUROC can give a poor operating threshold. |
| [Frozen V2 external transfer](V2_EXTERNAL_FROZEN_01_ANALYSIS.md) | 400 synthetic NVIDIA attack/clean pairs, 800 documents; V2 weights and cutoffs unchanged | Linear: **0/400** attacks caught, **0/400** benign flagged, AUROC **0.5630**. Mean-pool: **1/400** caught, **1/400** benign flagged, AUROC **0.8874**. | The old operating points failed to transfer usefully. This is not a V4 result. |
| [V4 source-label ranking](FEATURE_V4_SOLO_PROBE_01.md) | Fixed `content_mean/18` feature. Fit on 680 cleaned NVIDIA rows (228 attack, 452 controls); score 288 Microsoft LLMail rows (128 attack, 160 benign). | NVIDIA grouped out-of-fold AUROC **1.0000**; observed LLMail transfer AUROC **1.0000**. Saved model reproduces all 968 scores. | Promising ranking against inherited source labels on already observed datasets. No prospective final test or deployed threshold. |
| [V4 LLMail diagnostic cutoff](FEATURE_V4_LLMAIL_CUTOFF_01.md) | Midpoint cutoff **0.480185** calculated from NVIDIA training scores, then applied to the 288 already observed LLMail examples | **125/128** labeled attacks flagged (97.66%); **3/128** missed; **0/160** benign flagged in this sample. | Descriptive classification on correlated, previously observed development examples. The model still has `threshold: null` and serving disabled. |
| [Real-model attack development](OPEN_AGENT_DEV_02_ANALYSIS.md) | Four original attack/clean pairs, three policy variants, 24 sandbox episodes | No-defense **4/4** clean tasks passed, least privilege **2/4**, keyword **4/4**; attacker objective achieved **0/4** in every arm. | With no observed undefended successes, these cases cannot establish a defense advantage. The [new paired pilot](AGENT_ATTACK_PILOT_01_PREP.md) is prepared, not run. |

The clean pilot's 45 successful episodes contained **170 model-selected
field/value/source/line references** independently reconstructed from the
original pages. The validator refused 34 mismatched field/value/line attempts
and three incomplete briefs across attempts. Five failed tasks remain failed;
all successful effects were sandbox sends, not real mail. These details are
audited in the [clean pilot report](EVIDENCE_CLEAN_03_COMPLETED_ANALYSIS.md).

## What the numbers mean

**AUROC** measures ranking across all possible cutoffs. An AUROC of 1.0 on
the observed LLMail rows means every labeled attack scored above every benign
email. The NVIDIA-derived diagnostic cutoff still missed three attacks. A
score is not a calibrated probability; AUROC alone does not state attack
recall, false alarms, or whether an agent followed an injected instruction.

**Dataset size is not independence.** NVIDIA's [source dataset](https://huggingface.co/datasets/nvidia/Nemotron-RL-Agentic-Indirect-Prompt-Injection-v1)
is fully synthetic; SMAIP's local controls remove attack spans. The
[Microsoft LLMail challenge](https://huggingface.co/datasets/microsoft/llmail-inject-challenge)
contains human attacker submissions to a simulated email agent, plus benign
emails, but its 128 sampled attacks share connected lineage. V4's 968 cleaned
rows are development examples, not 968 independent final test cases. The
original 1,012 candidate references included 43 duplicate LLMail references
and one disputed NVIDIA row that were excluded. The [audit](FEATURE_V4_SOLO_AUDIT_01.md)
records this cleanup and the distinction between upstream labels and owner
review.

## Impact claim and missing evidence

**Supported:** SMAIP implements task-scoped authority, exact source-backed
numeric summaries, durable one-use review, and a reproducible evaluation
workflow. It completed many bounded synthetic clean tasks and exposed a
concrete failure of earlier probe transfer. The V4 probe has a strong observed
development ranking signal worth testing further.

**Not established:** real-world prevention of prompt injection, a V4
reduction in agent attack success, population 1%-FPR operation, statistical
five-point noninferiority, or serving performance/cost. The four-pair attack
pilot is not run; V4 has no validated serving cutoff. New, independently
grouped data and a real-model attack comparison are required before those
claims. The [completion checklist](../docs/PROJECT_COMPLETION_CHECKLIST.md)
tracks them separately from the portfolio release.
