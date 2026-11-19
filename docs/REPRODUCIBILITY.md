# Reproducing the SMAIP study

The source checkout supports the CPU-only scripted demonstration and software
regression suite. Historical real-model experiments also depended on archived
data, model/vector artifacts, and runtime configurations that are not all
included in Git. This page distinguishes running the available software from
reproducing those measurements.

## Run from a fresh checkout

Use Python 3.11 or later. The commands below use a POSIX shell on macOS or
Linux and assume the repository is already cloned and the shell is at its root.
Dependency installation needs network access; the demonstration needs no GPU,
API key, model download, or external email service.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python scripts/demo_guarded_agent.py
.venv/bin/python -m pytest -q
```

On Windows, use `.venv\Scripts\python.exe` in place of
`.venv/bin/python`. Run the test suite through `python -m pytest` from the
repository root so imports of repository scripts resolve consistently.
Leave the optional real-model test flags unset for the ordinary CPU suite.

The install command resolves dependency versions allowed by `pyproject.toml`;
it is not a bit-for-bit recreation of a historical GPU environment. The
repository also contains `uv.lock` for a locked dependency workflow. Historical
runtime versions and model revisions must be taken from the corresponding run
records when reproducing a specific model experiment.

## Interpret the demonstration

The demo reads a synthetic page containing a revenue value and an instruction
to send a copy to an unauthorized address. A scripted actor proposes that
recipient. The workflow refuses the argument, validates the numeric claim,
and creates a review checkpoint for the recipient authorized by the task.
The script then approves that checkpoint programmatically in a temporary
in-memory sandbox.

The JSON output should show:

| Field | Expected value | Meaning |
| --- | --- | --- |
| `refused_action_count` | `1` | The unauthorized recipient proposal was refused. |
| `sent_before_owner_approval` | `0` | No sandbox send occurred before approval. |
| `pending_recipient` | `owner@example.com` | The checkpoint retained the trusted task's destination. |
| `sent_after_owner_approval` | One summary with `revenue_last_quarter=42` | The approved sandbox effect used the validated evidence. |
| `audit_file_preserved` | `true` | The sandbox audit seed remained intact. |
| `external_email_sent` | `false` | No real email was delivered. |

Successful execution demonstrates the programmed authority and review
mechanisms. The actor is scripted and the approval is programmatic, so this
does not reproduce an LLM attack experiment or a human approval interaction.
The temporary review database is removed when the demo exits.

## Historical experiment availability

| Study component | Available in the repository | Additional material needed for full reproduction |
| --- | --- | --- |
| Guarded scripted workflow | Demo source, implementation, fixtures, regression tests | Installed ordinary dependencies only. |
| Clean Qwen agent pilot | Experiment code and [audited report](../reports/archive/EVIDENCE_CLEAN_03_COMPLETED_ANALYSIS.md) | Matching model revision/runtime and the original run inputs and outputs referenced by the report. |
| Frozen V2 external transfer | Evaluation code, provenance documentation, [transfer report](../reports/archive/V2_EXTERNAL_FROZEN_01_ANALYSIS.md) | Pinned external source snapshot, derived corpus, frozen probe/vector artifacts, and matching feature protocol. |
| V4 probe development and cutoff diagnostic | Feature/fit/evaluation scripts and [probe report](../reports/archive/FEATURE_V4_SOLO_PROBE_01.md) | Private archived vectors, source candidates, fitted model and predictions under `.local-data/`; raw-document extraction additionally needs the pinned Qwen snapshot/runtime. |
| AV label review and clarification | Review/audit tooling and [resolution report](../reports/archive/LLMAIL_OWNER_REVIEW_02_RESOLUTION.md) | Original private review submissions, clarification, sealed mapping, and source files matched by the recorded hashes. |

The [results page](../reports/PORTFOLIO_RESULTS.md) links the detailed evidence
for each reported measurement. The [data inventory](../DATA.md) records source
declarations and transformations. Paths and hashes in reports identify the
artifacts used; a path in a report is not a promise that the artifact is
included in a fresh checkout. Untracked files in the author's workspace are
also not part of the distributed repository.

External raw text, private review responses, and local model/vector artifacts
remain under ignored `.local-data/` or other excluded paths. Access to those
artifacts and compliance with their source licenses would be required to
recompute the corresponding historical measurements. No private artifact
access is required to inspect the public reports or run the scripted demo.

The multi-megabyte Week 7 parity vector dump is excluded from Git and verified directly from the original result archive by `scripts/analyze_week7_parity.py`.

If the exact original inputs are unavailable, a newly acquired dataset or new
model run is a separate replication experiment. Record its revisions,
transformations, grouping, thresholds, and runtime rather than presenting it
as an exact rerun of the completed study.
