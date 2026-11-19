# Feature V4 development candidate blind screen 01

The subsequent human label submission and post-submission comparison are
recorded in [Feature V4 human label screen 01](FEATURE_V4_HUMAN_REVIEW_01_ANALYSIS.md).
The human-review status below describes the point before that submission.

## Procedure and result

This is a **local assistant semantic screen**, not human adjudication. The
source was the pinned 1,012-row task-document candidate queue (SHA-256
`842b73014b1fc071cf9a61f1daccdd144be899ebf427970b7c8ea3bc539aec9e`).
The already observed exploratory `content_mean/18` predictions informed
selection, so this is development evidence and cannot be an independent test.

The 32-case packet contained eight rows per source/upstream-label stratum:
four closest to the apparent class margin and four deterministic hash-selected
rows. Cases were reshuffled. The assistant saw only source, native role,
trusted task and untrusted text; upstream labels, model scores and provenance
were kept in a separate answer file. The completed assistant judgments and
reasons were saved before opening that answer. The saved blind packet SHA-256
is `2d758a233dd770c8f2d0ab5b64e0670294f0c1fed8c88f07272f8c7b2982d61c`;
the pre-unblinding screen SHA-256 is
`3f0ce449f2f730c5f2f19834968440f49b0b326328e268eea9db08dd048da1a6`.
The separately stored answer SHA-256 is
`ba2a45a6078c289a9d45dbf60953b349b01f04c8affbe27180702c47ff8bd10e`.

| Screen outcome | Cases |
| --- | ---: |
| Assistant judgment matches upstream label | 29 |
| Assistant marks task/label ambiguous | 3 |
| Direct nonambiguous disagreement | 0 |

All 16 hash-selected cases matched. All three ambiguities were deliberately
sampled score-tail cases. `R007` and `R027` are LLMail emails labeled as
attacks upstream: an external sender requests action on feedback, and one
includes a send-email action item. The recipient's request is to summarize
the emails, so these may be content to summarize or attempts to trigger an
unauthorized tool call. `R031` is an NVIDIA span-deletion control labeled
benign upstream: the appointment reason includes a prescription-verification
request beyond the user's chart-summary task. A human must decide whether
this is normal clinical context or an instruction to the assistant. These
three judgments do **not** relabel any source row.

The packet also contains one exact duplicate task/document pair, `R004` and
`R010`, among 32 distinct source IDs. Thus even the screened cases are not
32 independent examples. The score-tail design, upstream task adaptation,
and repeated text prevent interpreting 29 matches as a population accuracy
estimate or a detector quality measurement.

A full exact-match audit of the same 1,012 task-document candidates found
**38 duplicate LLMail groups**, containing 81 rows and 43 redundant rows.
All are upstream-benign: the 203 benign rows represent only 160 distinct
trusted-task/document pairs. There were no exact cross-label conflicts.
The 128 LLMail attack rows and all 681 NVIDIA rows were distinct by this
exact-match key. This check does not detect semantic near duplicates or
shared generation lineage, so 160 is not an independence count.

## Data decision and next gate

The original candidate queue remains unreviewed and unassigned to an accepted
train/calibration/test split. The exploratory model remains local with no
threshold and serving disabled. Human review count is zero. An answer-free
reviewer copy of the packet, blank form and instructions is in
`.local-data/feature-v4-reviewer-packet-01/`. The source answer, assistant
screen and machine-readable audit remain separately in
`.local-data/feature-v4-review-packet-01/`. Run
`scripts/analyze_feature_v4_review_packet.py` to reproduce the audit; it
preserves any existing human form entries.

Before another training run or detector promotion:

1. Have a human reviewer classify the 32 blinded task/document pairs using
   the actual trusted task and allowed actions, recording uncertainty and
   reasons. Keep the source labels and this analysis sealed from that reviewer
   until the independent review is complete. Then adjudicate `R007`, `R027`
   and `R031` in light of the human judgments. Review a broader stratified
   sample before accepting the remaining queue; this packet is only a screen.
2. Resolve duplicates and lineage before any split. Preserve separate
   scenario/author/source groups and reconsider ambiguous or task-mismatched
   rows rather than silently using upstream labels as ground truth.
3. Prepare genuinely new calibration and final-evaluation sources with
   realistic agent tasks, clean documents, and adversarial documents. Freeze
   the model and threshold-selection rule before the final evaluation. The
   already scored LLMail set cannot serve as a fresh final test.
4. Measure full-agent attack success and clean-task utility at the chosen
   false-positive target. Even treating the 160 distinct LLMail benign
   task/document pairs as independent fixed-threshold observations with zero
   false positives would leave a one-sided 95% upper FPR bound of about
   1.85%, above the BRD's 1% target. Actual dependence and post-hoc model
   selection make the claim weaker.

This screen is encouraging evidence that the observed separation was not
entirely a blatant label inversion. It does not establish robust semantic
injection detection or meet the BRD acceptance criteria.
