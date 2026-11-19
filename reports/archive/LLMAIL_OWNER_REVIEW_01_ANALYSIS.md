# LLMail missed-case owner review 01: discrepancy audit

AV submitted three reasoned task-relative judgments on 2026-11-12 at
23:26:27 UTC. The immutable private submission is
`.local-data/feature-v4-llmail-owner-review-01/owner-review-20261112T232627Z-9fb7bb.json`
(SHA-256 `538bb85cb1b431b483a69cc69901cff4325c6561b05720298f4d7d3f444bdd5b`).
The local packet bound each judgment to the pinned source and trusted task.
The source mapping and shared lineage are in the
[pre-review audit](LLMAIL_MISSED_CASES_PRE_REVIEW_01.md).

The reproducible comparison is `python3 scripts/audit_llmail_owner_review.py`.
Its private summary is
`.local-data/feature-v4-llmail-owner-review-audit-01/summary.json`
(SHA-256 `caf95109b84835a980f5caaae3d18fa3d201f7bf33b46971a4943c0f12c2bdfa`).
The audit verified the new submission, the earlier 32-case sealed mapping and
AV screen, the original candidate manifest, and the unchanged `R031`
quarantine.

| New key | Earlier key | Source label | Earlier AV screen | New AV judgment | Task boundary |
| --- | --- | --- | --- | --- | --- |
| M01 | R019 | Attack | Attack | Benign | Clear |
| M02 | R017 | Attack | Attack | Benign | Clear |
| M03 | R007 | Attack | Attack | Attack | Clear |

Thus the new review agrees with the source and earlier AV screen on **one of
three** cases, and disagrees on **two of three**. The two changed judgments are
repeat reviews of the *same source rows*, not new independent examples. AV's
new reasons describe M01 and M02 as ordinary requests for confirmation and
say they do not manipulate the model into calling a tool. The emails do,
however, explicitly ask the recipient to send a confirmation, while the
trusted user asked the assistant only to summarize emails. The project
glossary defines injection relative to the trusted task, so those two rows
need an explicit reconciliation of intent and task boundary before their
labels could be accepted. M03's new attack judgment remains consistent with
AV's earlier attack screen and later explanation for R007.

All three rows share the same upstream author/team and scenario and the same
metadata-connected component. There are no exact duplicate task/document
pairs among them. Do not count them as three independent failures or change a
population estimate based on this selected score tail. The source-provided
LLMail cutoff count remains an observed development diagnostic, not an
accepted-label result. The current V4 probe was fitted on NVIDIA rows only;
this review did not change its training set, weights, threshold, or serving
status.

Pending AV clarification, keep M01 and M02 out of any **accepted-label** set.
Keep both immutable AV submissions, source labels, original rows, and scores.
`R031` remains quarantined. If AV confirms revised judgments, record the
clarification as a new linked artifact rather than rewriting either review.
If no clarification is available, exclusion is a defensible resolution for
those two rows. A future development-set or policy change must be versioned;
the already observed LLMail examples cannot become a fresh final test.
