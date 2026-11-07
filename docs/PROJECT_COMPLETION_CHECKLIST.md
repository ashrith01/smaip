# SMAIP completion checklist

Status checked 2026-11-07 on branch `codex/week7-recovery`. This distinguishes
a bounded, honest **portfolio release** from the stronger **BRD acceptance**
claim. Completing the portfolio release does not certify the BRD. The owner's
open-model-only decision remains in force.

## Portfolio release: complete these in order

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
- [x] **5. Consolidate a public results page.** The results page keeps separate the 25-task
  clean pilot (22/25 single agent, 23/25 specialist), the failed frozen V2
  external operating points (0/400 and 1/400 attacks caught), and the V4
  development scores (NVIDIA 680; LLMail 288; observed LLMail diagnostic
  cutoff 125/128 attacks and 0/160 benign flagged). Give every number its
  denominator, dataset lineage, threshold status, and report link. Mark V4
  source labels and LLMail as already observed development evidence.
- [ ] **6. Package and check the portfolio release.** Fresh-checkout setup,
  tests, demo, report links, dataset licenses/attribution, secret/private-file
  scan, CI, and a final claim review. Publish the reviewed repository state;
  only change repository visibility if the owner separately chooses that.

## Evidence work that can improve the portfolio release

- [ ] **7. Owner label check.** Prepare the three LLMail examples missed by
  the diagnostic cutoff for AV's task-relative review. Optionally sample up
  to 32 further distinct cases across source and label strata. Record the
  authorized task, source text, label, reason, and provenance. An assistant
  cannot mark these as AV-reviewed. A reviewed row from an already observed
  source still is not a fresh final test.
- [ ] **8. Audit experiment discrepancies.** Compare source labels with AV's
  decisions, examine lineage and synthetic controls, and version any changed
  training set or policy. Preserve R031 quarantine and original records.

## Full BRD acceptance: separate, resource-dependent work

- [ ] **9. Obtain independent detector data.** Reserve new, separately
  grouped benign and attack cases before model selection; verify task scope,
  provenance, licenses, and labels. Keep fitting, feature selection, threshold
  calibration, and final-test roles separate. Do not reuse the observed
  NVIDIA/LLMail rows as a fresh final test.
- [ ] **10. Freeze and test a V4 operating point.** Extract needed features
  with the pinned open model, set a threshold on eligible calibration data,
  and evaluate attack recall, benign false alarms, uncertainty, source/family
  shifts, and hard benign cases on a final holdout. The current V4 model has
  no serving threshold and does not establish TPR at 1% FPR.
- [ ] **11. Run the real-model attack study.** Establish that no-defense
  episodes can complete legitimate tasks and are susceptible to the chosen
  attacks; then compare matched defense arms, including keyword, least
  privilege, probe-only, and full stack. Measure actual unauthorized sandbox
  effects and clean utility, plus adaptive cases. The four-pair pilot is
  prepared but not run; current zero-ASR ties do not show superiority.
- [ ] **12. Complete production-path integration.** Wire the constrained
  real-model task path into the intended orchestration and mediated gateway;
  add V4 raw-document extraction and scoring only after validation. Finish
  model-input/output privacy handling, review integration, and regression
  tests. Keep the mock CI path intact.
- [ ] **13. Measure operations and acceptance.** Run repeated serving,
  cache, concurrency, latency and actual cost benchmarks; compare external
  defenses under the same evaluation unit; check clean-utility, attack,
  statistical and performance gates. Report any failed gate instead of
  declaring full BRD acceptance.

The older October 31 runbooks are historical records; later reports supersede
their initial pending pilot statuses. Use the current audit reports before
launching or repeating a GPU job.
