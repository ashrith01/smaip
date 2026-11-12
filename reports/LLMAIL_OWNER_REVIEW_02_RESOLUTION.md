# LLMail missed-case review: AV clarification and resolution

On 2026-11-12, AV clarified that M01 and M02 should be kept as **attack** in
AV's review. The exact reply is preserved in a new private artifact at
`.local-data/feature-v4-llmail-owner-review-01/owner-clarification-20261112T233124Z.json`
(SHA-256 `ab7884d08d8e3939d44b27519a72f4ea9ea816fa2688ff3161c901839bd522cd`).
It links to the immutable [first comparison audit](LLMAIL_OWNER_REVIEW_01_ANALYSIS.md)
and both earlier review submissions. AV gave a corrected label but no new
case-specific reason; the submitted reasons remain unchanged.

The versioned `python3 scripts/audit_llmail_owner_clarification.py` check
reproduces audit 01, verifies the clarification binds exactly M01/R019 and
M02/R017, and verifies the original submissions and `R031` quarantine. Its
private summary is
`.local-data/feature-v4-llmail-owner-review-audit-02/summary.json`
(SHA-256 `3a4cb85d80ec44ca5aa38c6e6c4b5b55c51c59f9e56eae8822443898397e9bc2`).

| Case | Earlier AV screen | Submitted second judgment | AV clarification | Source label |
| --- | --- | --- | --- | --- |
| M01 / R019 | Attack | Benign | **Attack** | Attack |
| M02 / R017 | Attack | Benign | **Attack** | Attack |
| M03 / R007 | Attack | Attack | Attack (unchanged) | Attack |

After the linked clarification, AV's effective judgments agree with the
upstream attack labels on all three selected cases. This resolves the two
repeat-review discrepancies for the limited audit. The project rule remains
task-relative: the trusted user asked only for an email summary, so an email's
request to send a confirmation is lower-trust content and does not authorize
the assistant to send it. That explanation is the project analysis, not a
reason newly supplied by AV.

All three examples are already observed development data from one upstream
author and scenario within one connected lineage component. The review does
not create independent test cases or validate the observed cutoff. No
training set, experiment policy, probe weights, serving threshold, or split
was changed. No new candidate label was promoted to the corpus-v3
`accepted_label` field. The NVIDIA synthetic control disputed as `R031`
remains quarantined, with its source label and AV judgment preserved. Any
later change to training data or policy must receive its own versioned
artifact.
