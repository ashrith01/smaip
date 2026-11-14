# SMAIP study conclusion

Completed November 13, 2026. Author: Ashrith Vadde.

## Research question

I investigated how an AI agent could use untrusted documents as evidence
while keeping its actions tied to the trusted user's request. I built an
experimental platform combining source-backed numeric claims, task-scoped
tool permissions, durable owner review, and probes trained on features from
a frozen Qwen model. The work explored both engineering controls and the
quality of the evidence used to evaluate them.

The original design expected that privilege separation and checked evidence
could retain useful task completion while reducing unauthorized actions, and
that frozen-model activation probes could help distinguish injected content.
These were the project's design expectations, not preregistered hypotheses.
The [original requirement mapping](../docs/brd/BRD_ALIGNMENT_2026-10-30.md)
also sought low-false-alarm detection and a full-stack advantage over simpler
defenses. The completed experiments support narrower conclusions:

| Design expectation | Outcome at study closure |
| --- | --- |
| Checked evidence and task-scoped actions can support a useful agent workflow. | Supported within the bounded synthetic clean-task pilot and scripted mechanism checks. General user usefulness was not evaluated. |
| Specialists preserve utility and improve safety over a single agent. | Inconclusive. The clean pilot differed by one task; the attack comparison did not establish susceptibility in its undefended arm. |
| Activation probes provide a transferable injection signal at a useful operating point. | Mixed. Earlier frozen thresholds failed external transfer; V4 showed strong observed label ranking without independent threshold validation. |
| The combined system reduces attacker effects more than simpler defenses. | Unresolved. The completed real-model comparison could not demonstrate a defense advantage. |

## What I built

The repository contains a guarded workflow, sandbox evaluation tools,
versioned feature and probe experiments, a CPU-only scripted demonstration,
and audited experiment reports. The scripted demonstration shows how an
unauthorized recipient can be refused and an authorized action bound to
source evidence and an approval checkpoint. It demonstrates code-enforced
mechanisms; real-model measurements are reported separately.

## What I found

**The bounded agent workflow was workable, with remaining errors.** In the
25-task synthetic clean pilot, the single-agent arm passed 22 tasks and the
specialist arm passed 23. Successful effects were sandbox sends. The
one-task difference is descriptive, not evidence that specialists are
generally better. The [clean pilot audit](EVIDENCE_CLEAN_03_COMPLETED_ANALYSIS.md)
preserves failed tasks and checks the successful source references.

**Ranking and operational detection are different questions.** The old
mean-pool probe achieved an external AUROC of 0.8874 but caught only one of
400 attacks at its frozen cutoff; the linear probe caught none. This was
the clearest negative result: a ranking metric alone did not establish a
usable operating point. The [frozen transfer report](V2_EXTERNAL_FROZEN_01_ANALYSIS.md)
records the unchanged thresholds and their failure.

**Later features showed a strong development signal, with unresolved
generalization.** V4 ranked the observed NVIDIA and LLMail source labels
with AUROC 1.0. A NVIDIA-derived diagnostic cutoff flagged 125 of 128 LLMail
attacks and zero of 160 benign emails. These sources and features had already
been examined, and the attack examples shared connected lineage. I therefore
treated these as development findings, rather than an independent final
test or deployment result. The model retained no serving threshold. The
[results page](PORTFOLIO_RESULTS.md) provides denominators and artifact links.

**The attack study did not establish a defense advantage.** The small
real-model development comparison observed zero of four attacker objectives
in every arm, including no defense. Without observed undefended successes,
the ties could not establish that a defense caused the result. A subsequent
paired pilot was prepared but not executed.

**Label and lineage audits changed how I interpreted the metrics.** Exact
duplicates, synthetic span-deletion controls, and a disputed benign control
required explicit handling. The disputed R031 row stayed quarantined. AV's
review and later clarification retained attack judgments for the three
LLMail misses, with both submissions preserved. These checks improved the
interpretation of existing evidence without making it independent data.

## Limitations and scope

The study does not establish broad real-world injection prevention, an
incremental benefit from the probes or specialists, population performance
at 1% FPR, or production latency and cost. Synthetic tasks, related examples,
small agent samples, and previously observed detector data restrict the
claims. Private data and model/vector artifacts are excluded from Git, so
the source checkout reproduces the scripted demonstration and software
checks but not every historical model experiment by itself.

## Final interpretation

My conclusion is that evaluating a guarded agent requires separate evidence
for task usefulness, source correctness, action authority, detector operating
points, and actual unauthorized effects. SMAIP made these distinctions
concrete in code and exposed where attractive component metrics were
insufficient. The strongest outcome is an auditable experimental case study:
a bounded working agent workflow, a documented failure of probe transfer,
and a promising later feature signal whose limits are explicit.

## Three questions for possible future studies

The project ends at these findings. The following questions are optional
extensions, with no additional experiments required for this study's closure:

1. **Does the V4 signal generalize at a useful threshold?** A new study would
   reserve independent groups, select a threshold on calibration data, and
   test recall and false alarms on an untouched final set. It would report
   counts and uncertainty rather than infer 1%-FPR behavior from ranking.
2. **Which controls reduce unauthorized effects while preserving task
   usefulness?** A matched agent study would first establish a capable,
   susceptible undefended baseline, then compare controls on the same clean
   and injected tasks. Failed tasks and attacker objectives would remain
   separate outcomes.
3. **Can another person reproduce and interpret the workflow?** An external
   replication would test the documented installation, scripted demonstration,
   expected outputs, and limits with someone other than the author. It would
   distinguish reproducing software behavior from rerunning historical model
   experiments that require excluded private artifacts.
