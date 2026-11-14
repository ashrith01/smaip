# SMAIP completion checklist

**Closed as a bounded research and engineering study on 2026-11-13.**
The owner chose to conclude the project using the completed experiments.
Steps 1–8 document completed work. The original steps 9–13 were not performed or accepted; their status is
explained below alongside three optional future research directions. See the [study conclusion](../reports/STUDY_CONCLUSION.md)
and [closure decision](adr/0002-close-as-completed-study.md).

## Completed portfolio release

- [x] **1. Establish the current baseline.** Full local pytest run exited 0
  on 2026-11-07 (two skipped tests). Verified `origin` points to
  `ashrith01/smaip`; `.local-data/` model and evaluation artifacts are Git
  ignored. The baseline working tree had 132 changed/untracked status entries.
  This was a local check, not CI or a GitHub release.
- [x] **2. Reconcile the work tree for publication.** Reviewed the intended
  source, tests, data, and reports; fixed archive validation checks found in
  the security review. The staged diff excluded private data, raw run
  artifacts, and old V1/V2 probe weights. Commit `cef2a87` was pushed to
  `origin/codex/week7-recovery` on 2026-11-07.
- [x] **3. Prepare a clear project front door.** Updated the root
  `README.md` with the problem, one system diagram, exact capabilities, a
  local scripted demo, tests, result links, and a plain limits section. Added
  the root `GLOSSARY.md` and `docs/adr/` context referenced by `AGENTS.md`.
- [x] **4. Make one reproducible demonstration.** The CPU-only scripted demo
  shows a legitimate task, lower-trust content containing an instruction,
  evidence and authority checks, and the resulting refused or permitted
  sandbox effect. It runs without a GPU, model download, or private data.
- [x] **5. Consolidate a results page.** The results page keeps separate the 25-task
  clean pilot (22/25 single agent, 23/25 specialist), the failed frozen V2
  external operating points (0/400 and 1/400 attacks caught), and the V4
  development scores (NVIDIA 680; LLMail 288; observed LLMail diagnostic
  cutoff 125/128 attacks and 0/160 benign flagged). Each result has a
  denominator, dataset lineage, threshold status, and report link. V4 source
  labels and LLMail are identified as already observed development evidence.
- [x] **6. Package and check the portfolio release.** PR [#8](https://github.com/ashrith01/smaip/pull/8)
  merged the reviewed release into `main` at `412e450`. Its PR checks and all
  seven [main CI jobs](https://github.com/ashrith01/smaip/actions/runs/42400072494)
  passed, including fresh-checkout installation/tests and the CPU Docker build.
  The staged-export test suite and demo also passed locally. README, results,
  data, glossary, checklist, and ADR links resolved; `DATA.md` records dataset
  origins and license declarations. A tracked-file scan found no key-shaped
  credentials or `.local-data/` files. Final claims keep V4 development
  rankings separate from validated detector and agent-effect results. The
  repository remains **private**; public visibility needs a separate owner
  decision.

## Completed owner review and evidence audit

- [x] **7. Owner label check.** Prepare the three LLMail examples missed by
  the diagnostic cutoff for AV's task-relative review. Optionally sample up
  to 32 further distinct cases across source and label strata. Record the
  authorized task, source text, label, reason, and provenance. An assistant
  cannot mark these as AV-reviewed. A reviewed row from an already observed
  source still is not a fresh final test. The three-case local review page and
  [pre-review audit](../reports/LLMAIL_MISSED_CASES_PRE_REVIEW_01.md) were
  prepared on 2026-11-12. AV submitted all three reasoned judgments; the
  [comparison audit](../reports/LLMAIL_OWNER_REVIEW_01_ANALYSIS.md) records
  two source-label and prior-review conflicts. No optional 32-case sample was
  requested.
- [x] **8. Audit experiment discrepancies.** Compare source labels with AV's
  decisions, examine lineage and synthetic controls, and version any changed
  training set or policy. Preserve R031 quarantine and original records. The
  three missed rows' source mapping and shared author/scenario were checked.
  The initial comparison found two conflicting repeat judgments; AV's linked
  [clarification](../reports/LLMAIL_OWNER_REVIEW_02_RESOLUTION.md) resolved
  both as attack. Original submissions and R031 quarantine remain intact; no
  training set or policy changed, and no new final-test evidence was created.

## Optional future research

These are three possible new studies, not requirements for closure.

| Extension | Research question | Evidence a new study would need |
| --- | --- | --- |
| Independent detector validation | Does the V4 signal generalize at a useful operating point? | New grouped cases, audited labels and provenance, a threshold frozen on calibration data, and an untouched final test with recall, false alarms, and uncertainty. |
| Matched agent defense comparison | Which controls reduce unauthorized effects while preserving task utility? | A capable and susceptible undefended baseline, matched clean/attack cases, explicit defense arms, actual sandbox effects, and utility/cost measurements. |
| External replication | Can another researcher reproduce the documented workflow and interpret its decisions? | A fresh environment, the supplied demo and software checks, recorded setup problems, and a report distinguishing reproduced software behavior from historical model measurements. |

The original BRD's steps 9–10 map to detector validation; step 11 maps to the
agent comparison. Steps 12–13 proposed production integration and operational
acceptance. Those product ambitions were not achieved and are outside the
closed study. They would require a separate product decision rather than an
extension of this completion checklist. The preliminary
[source gate](brd/INDEPENDENT_DATA_GATE_2026-11-12.md) remains a historical
planning record; no new data was acquired through it.

## Final documentation pass

- [x] State the research questions and retrospective hypotheses.
- [x] Explain models, datasets, comparisons, and outcome measures.
- [x] Connect findings to hypotheses, including negative and inconclusive results.
- [x] Document checkout-level reproducibility and private-artifact boundaries.
- [x] State limitations and the study's final interpretation.
- [x] Limit future research to the three questions above.

Read the [methods](STUDY_METHODS.md),
[reproducibility guide](REPRODUCIBILITY.md), and
[conclusion](../reports/STUDY_CONCLUSION.md) together. The historical experiment
reports retain their original dates and pending statuses; the closure decision
supersedes those statuses as project commitments.
