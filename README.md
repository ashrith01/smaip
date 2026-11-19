# SMAIP: a study of evidence, authority, and prompt injection in AI agents

**Study completed · November 2026**

I built SMAIP as a research framework for AI agents that read untrusted
documents. The architecture pairs source-checked numeric summaries with
task-scoped tool permissions, approval for exact action arguments, and an
in-memory workspace for testing side effects. The repository includes a
CPU-only scripted demo, a replayable evaluation harness, and frozen-model
probe experiments.

The real-model pilot passed 22 of 25 clean tasks with a single agent and 23
of 25 with specialists. The attack experiments left the defense advantage
unresolved. In a preregistered, group-disjoint test on 2,000 repository files,
frozen V4 reached AUROC 0.7379 (95% CI 0.7126–0.7608): its development cutoff
flagged 68.1% of benign files (and 84.96% of NotInject trigger-word prompts),
while its target-calibrated cutoff held benign FPR to 0.4% but caught only
2.6% of attacks. V4 serving remains disabled.

[Study methods](docs/STUDY_METHODS.md) ·
[External test results](reports/PORTFOLIO_RESULTS.md#preregistered-v4-external-test) ·
[Read the study conclusion](reports/STUDY_CONCLUSION.md) ·
[Detailed measurements](reports/PORTFOLIO_RESULTS.md) ·
[Study closure and scope](docs/PROJECT_COMPLETION_CHECKLIST.md)

## What I investigated and found

| Question | Finding | Evidence and limits |
| --- | --- | --- |
| Can an agent produce a numeric report with checked sources and controlled actions? | The bounded workflow completed most clean tasks. | Single agent: **22 of 25** tasks; specialists: **23 of 25**. Synthetic tasks and sandbox effects; the one-task difference does not establish superiority. |
| Does a useful ranking score imply a useful fixed detector threshold? | No. The earlier frozen operating points failed to transfer. | Linear probe caught **0 of 400** attacks; mean-pool probe caught **1 of 400**. The latter still had AUROC **0.8874**. |
| Do later frozen-model features contain a useful signal? | They separated the observed source labels, warranting further investigation. | V4's observed LLMail AUROC was **1.0**; a diagnostic cutoff flagged **125 of 128** attacks and **0 of 160** benign emails. Prior observation and shared lineage limit interpretation. |
| Did the agent experiments demonstrate attack reduction? | They did not establish a defense advantage. | The small development study observed **0 of 4** attacker objectives in every arm, including no defense. |

These questions summarize the exploratory development sequence. The later V4
external test followed a preregistered protocol. [Study methods](docs/STUDY_METHODS.md) ·
[External test](reports/PORTFOLIO_RESULTS.md#preregistered-v4-external-test)

The main lesson is methodological: source evidence, action authority, detector
ranking, threshold behavior, and actual attacker effects need separate checks.
A strong result on one does not establish the others. See the
[conclusion](reports/STUDY_CONCLUSION.md) for the interpretation and limitations.

## Try the guarded workflow without a GPU

Requirements: Python 3.11+ and a network connection to install dependencies.
From a fresh checkout:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python scripts/demo_guarded_agent.py
.venv/bin/python -m pytest -q
```

The demo contains a synthetic page with a revenue figure and an instruction to
send a copy to an attacker address. A **scripted adversarial actor** proposes
that recipient; SMAIP refuses the unauthorized argument. It then creates a
source-backed summary for the task's recipient and creates an owner-review
checkpoint. The demo then programmatically approves that checkpoint inside an
**in-memory sandbox**. This scripted approval demonstrates the mechanism; it
is not a human review. The demo sends
no real email and does not run a language model. The real Qwen pilot and its
archived evidence are reported separately; the demo does not claim to reproduce
those model results.

**Expected output (excerpt)**

```text
  "refusal_reason": "unauthorized recipient argument rejected by action schema",
  "sent_before_owner_approval": 0,
  "pending_recipient": "owner@example.com",
  "sent_after_owner_approval": [
    {
      "to": "owner@example.com",
      "subject": "Vendor numeric summary",
      "body": "revenue_last_quarter=42"
```

For environment details, expected output, and historical-artifact availability,
see the [reproducibility guide](docs/REPRODUCIBILITY.md).

## How it works

```mermaid
flowchart LR
    U[Trusted user task] --> I[Task intent and allowed sources]
    D[Lower-trust document] --> R[Reader]
    I --> R
    R --> C[Evidence claims with source and line]
    C --> V[Deterministic validation and summary]
    V --> A[Task-scoped action check]
    A --> H[Owner approval checkpoint]
    H --> S[Sandbox effect]
    D -. development feature experiment .-> P[V4 activation probe]
```

The model can use page text as evidence. Trusted task state sets tool
permissions, recipients, and approval. A model proposes claims and actions, while code checks
the source, exact numeric line, action arguments, and saved checkpoint. The
gateway consumes its argument-bound approval after successful dispatch. A
quarantine label preserves the scripted page record as tainted evidence.
Model-facing callers withhold the raw text. V4 remains an offline experiment.
[Architecture and scope](docs/archive/brd/BRD_LIVE_RECHECK_2026-10-31.md) ·
[Terms](GLOSSARY.md) · [Design decisions](docs/adr/)

## Repository guide

- [`src/smaip/agents/`](src/smaip/agents/): task progression, source evidence,
  action generation, and durable owner review.
- [`src/smaip/probes/`](src/smaip/probes/): versioned feature and evaluation
  contracts; V4 weights and private vectors are excluded from Git.
- [`src/smaip/eval/`](src/smaip/eval/): sandbox cases, effects, and scoring.
- [`tests/`](tests/): CPU checks; CI does not download model weights.
- [`DATA.md`](DATA.md): dataset origins, transformations, and license notes.
- [`reports/`](reports/PORTFOLIO_RESULTS.md): audited measurements and known
  failures. [Archived reports](reports/archive/)
- [`docs/archive/`](docs/archive/): earlier plans, recovery notes, runbooks,
  and repository guidance.
- [`docs/DEVELOPMENT_HISTORY.md`](docs/DEVELOPMENT_HISTORY.md): the original
  week-by-week walkthrough, retained for context.

## Study status

This study is closed at the evidence documented here. The original production
and full BRD acceptance ambitions were not achieved and are retained as
optional future research. There is no validated serving threshold for V4 or
population 1%-false-positive-rate claim. Qwen stayed frozen; the trained
components were small probes on its features.

Readers can run the scripted demonstration, inspect the implementation and
audited reports, or use the evaluation structure as a starting point for their
own experiments. Private external data, review submissions, and model/vector
artifacts are excluded from Git; experiments requiring them cannot be fully
reproduced from the public source alone.
