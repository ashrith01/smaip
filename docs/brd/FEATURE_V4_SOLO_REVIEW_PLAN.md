# Feature V4 solo data-review path

The first mechanical pass is complete; see
`reports/FEATURE_V4_SOLO_AUDIT_01.md` for the pinned inputs, row-level
manifest, duplicate and lineage counts, and remaining limits.
The fixed-feature sensitivity is in
`reports/FEATURE_V4_SOLO_SENSITIVITY_01.md`; a separate, original paired
agent attack pilot is prepared in `reports/AGENT_ATTACK_PILOT_01_PREP.md`.
The local, saved development probe is recorded in
`reports/FEATURE_V4_SOLO_PROBE_01.md`.

## Decision

AV is the sole project reviewer and cannot manually label the remaining 938
distinct task/document pairs. The live BRD does not require a human label for
every pilot training row. That blanket requirement is part of the current
conservative corpus-v3 feasibility policy, so the existing audit must remain
`pending` until a separately named, narrower policy and study are implemented.
Do not fill the remaining review records as if a human checked them.

Keep AV's 32-case blind submission and later explanations as they are. Exclude
the disputed `R031` source row from any accepted labeled set. No second human
review is required to exclude it. The 64-case packet 02 is optional; it does
not need to be completed for the solo path and must not be called independent
if AV reviews it.

## Bounded next pass

1. Mechanically audit all 1,012 task/document rows for exact duplicates,
   provenance fields, candidate hashes, task/document compatibility, source
   licenses and connected lineage. Collapse the 43 redundant exact-pair rows
   for review planning, while retaining all source IDs and their provenance.
   Quarantine exact label conflicts, malformed rows and known contested rows.
2. Treat remaining upstream labels as **source-provided development labels**,
   not human-verified truth. Use them for exploratory fitting and error
   discovery only. Preserve the current no-threshold, serving-disabled state.
3. If AV can spare a small additional review, cap the next pass at **32 new
   distinct pairs**: 8 from each of the two-source/two-label strata, sampled
   by fixed hash without consulting model scores. Record reasons and task
   boundaries. Separately queue at most **16** model/source disagreements or
   ambiguous cases for targeted follow-up. The targeted set is deliberately
   biased and cannot estimate population label error or detector FPR.
4. Analyze disagreements by source and lineage component. Stop or exclude a
   problematic component rather than multiplying reviews of its near copies.
   If the 32-case spot check shows systematic task/label mismatch, revise the
   candidate source or task framing before fitting more features.
5. Evaluate the agent on small, explicit clean and attack scenarios and report
   observed utility, attack outcomes, and failure examples as **development
   diagnostics**. Existing scored data and owner-reviewed cases cannot be an
   untouched final test. BRD claims about TPR at 1% FPR and full-stack ASR
   improvement require new, independently grouped evaluation data and a
   frozen model/threshold protocol. If those resources are unavailable, leave
   the acceptance result unclaimed.

## Review budget and evidence labels

The immediate solo path requires **zero additional manual labels** to continue
mechanical data cleanup and development diagnosis. A useful optional spot
check is **32** new cases, plus up to **16** targeted disagreements if needed.
This is a project workload cap, not a statistically justified sample size or
proof that the remaining queue is correct. The prior 32 cases cover 31 unique
pairs; they remain an AV label screen because most reasons and all
task-boundary fields were blank in the original submission.

Report three counts separately: source-provided labels, AV-reviewed labels,
and accepted labels after task/provenance checks. Never promote an AI-generated
judgment to a human review. Any future change to `require_human_review` must
be versioned as a new experiment policy, keep the current strict audit
reproducible, and state the narrower claim it supports.
