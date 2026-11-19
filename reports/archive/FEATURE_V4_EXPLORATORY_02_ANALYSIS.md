# Feature V4 exploratory probe fit 02

The returned GPU feature collection passed a second full local audit:
**1,012/1,012** pinned-Qwen forwards, all binary rows/hash bindings correct,
finite 2,048-coordinate vectors, and the expected nine readouts from one
task-conditioned assistant-boundary view. The source archive SHA-256 is
`eb5f57933570e29e8a927a1309c0143d5d32c798c041b11bc8e055eb3c84f443`;
the token-budget archive SHA-256 is
`516450afc39e4ff9175863c64230bd58468387b0b015b9092cde4865e3e8154b`;
the feature archive SHA-256 is
`eb745c1b9615a69067850e6969a18122bd2f701d3e1e5eacbd8f7ba81f46dbd4`.
The feature protocol fingerprint is
`ddb4e1c05d9f25100331ea78eec8cc36c47cef4866f57417e2f30607272df463`.
The A16 job took 200.2 seconds and peaked at 7,234,862,592 GPU bytes allocated.
No base-model weights were trained.

The **local CPU exploratory fit** used upstream labels from the unreviewed
candidate queue. The first run is retained under
`.local-data/exploratory-fit-v4-01/`; it had a post-hoc low-FPR reporting bug
that counted avoidable false positives under complete separation. Its exact
script was saved separately in `.local-data/exploratory-fit-sources/`.
The corrected run under `.local-data/exploratory-fit-v4-02/` preserves the
same feature choice, scores and AUROCs, and minimizes false positives when
several post-hoc cutoffs have the same recall. The corrected script SHA-256 is
`dee632bdd057ed43ce254504635e82321b06c3456b268b44603db912fed3e2bf`.

## Development result

NVIDIA supplied 681 unused-context rows (228 annotated attacks, 453
span-deletion controls). Contexts, pairs, shared author/template fields,
exact text and near duplicates were connected before assigning three
deterministic folds of 227 rows. An independent pass through the corpus V3
lineage auditor found no cross-fold lineage or near-duplicate violation;
that audit still reports **pending** because labels are unreviewed and this
is one source. Each of nine readouts used train-only z-scoring and the same
L2-regularized linear logistic objective. The selection rule used pooled
grouped out-of-fold scores, with descriptive low-FPR ranking first and
AUROC as a tie-break.

| Development comparison | Selected `content_mean/18` |
| --- | ---: |
| NVIDIA grouped out-of-fold AUROC | 1.0000 |
| NVIDIA annotated attacks above every control | 228/228 |
| NVIDIA minimum attack score / maximum control score | 0.5337 / 0.2130 |
| NVIDIA paired contexts with injected score above its control | 228/228 |
| LLMail source-transfer AUROC, after fitting on all NVIDIA rows | 1.0000 |
| LLMail minimum attack score / maximum benign score | 0.2128 / 0.0602 |

The LLMail source-transfer view contains 128 annotated attack submissions
and 203 FP-test benign emails. It was scored only after selecting the
readout on NVIDIA. Its 331 scores were independently recomputed from the
saved model weights and binary features with maximum error
`2.22e-16`. The saved model has **no threshold** and
`serving_enabled=false`. The LLMail scores are now observed development
evidence, not a fresh final set.

Simple length does not fully explain this result. Task-boundary token length
alone has AUROC 0.9818 on NVIDIA and 0.8353 on LLMail. Within LLMail's
shared 355–404-token range, all 203 benign emails and 30 attacks remain
perfectly ranked by the selected feature, while length AUROC is 0.5306.
All LLMail records share the same rendered trusted-task description. These
checks reduce one obvious confound but do not establish semantic injection
detection across new tasks, formats or authors.

## Limits and next decision

The two sources differ in construction and task adaptation. NVIDIA controls
are synthetic attack-span deletions. LLMail attacks are from a bounded prefix
and its 128 attack rows form **one connected lineage component** under
scenario/author grouping; they are not 128 independent attack samples. The
203 benign LLMail emails include 38 exact duplicate groups: they reduce to
160 distinct trusted-task/document pairs, with no human adjudication in this
queue. All reported low-FPR points use labels after
scoring to describe ranking; they are **not** frozen calibrated thresholds.
Even under an unrealistically independent fixed-threshold assumption, zero
false positives in 203 benign observations leaves a one-sided 95% upper FPR
bound of about 1.46%; using the 160 distinct task/document pairs gives about
1.85%, still above the BRD's 1% target. Post-hoc selection and dependence
make the actual claim weaker. The exact duplicate audit and assistant blind
screen are recorded in `reports/archive/FEATURE_V4_BLIND_REVIEW_01_ANALYSIS.md`.

This is a promising **development feasibility result**, not an accepted
detector, BRD threshold result, or real-agent security improvement. Keep
the frozen V1/V2 probes and protocol-7 clean pilot separate. Next, adjudicate
task/label/provenance and format coverage, establish fresh independent
calibration and final samples with adequate benign counts, and run the
full-stack attack/utility evaluation. Do not tune against these now-observed
LLMail scores or promote the exploratory JSON file to `artifacts/probes`.
