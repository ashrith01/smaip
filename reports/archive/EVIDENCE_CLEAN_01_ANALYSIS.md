# Clean evidence pilot 01 — verified failure

The returned GPU archive contains all 50 episodes and matches the exported r1
source bundle. File hashes, original task cases, model/revision/budgets and
post-run task scores were checked locally without loading a model. Both
single-agent and specialist topologies scored **0/25** clean successes.

| Observed trace event | Count |
| --- | ---: |
| Model calls | 125 |
| Successful source reads | 0 |
| Claim submissions | 0 |
| Executed sandbox sends | 0 |
| Single-agent early final responses | 25 |
| Reader early final responses | 25 |
| Analyst early final responses | 25 |
| Invented artifact IDs refused by the actor boundary | 25 |

Every single agent stopped on its first response. Every reader also stopped
before accessing a page. The old loop proceeded to analyst and actor despite
missing source data; the actors invented artifact IDs. Source/artifact validation
correctly blocked those sends. No task reached the evidence-grounding step.

The model-facing system prompt named tools and showed a final-answer object, but
did not show tool-call JSON argument schemas. Those schemas were passed only to
the constrained decoder. That restricted generated syntax without explaining
the tool interface to the model. Generic instructions also did not distinguish
each role's responsibility sufficiently. This is an agent-interface failure;
the run supplies no measurement of detector quality or probe-training need.

The trace establishes premature stopping and missing tool documentation. It
does not prove that documenting the interface alone restores model utility.
The previous scripted tests exercised valid hand-authored actions but did not
establish that Qwen could infer the undocumented action contract.

## Corrective version

Protocol 6, exported in r2, adds model-visible role-specific JSON schemas and
role-specific guidance. Its decoder and server validator use the same role
schema. Unsupported calls remain refused; all numeric facts, quote spans and
artifact identities remain validated. No expected answer is added to the model
input, no tool action is synthesized, and no failed final response is converted
into success. Failed reader/analyst dependencies now block downstream inference.

An explicit final is recorded as a model abort. Each episode reports reads,
calls and failure reason. The next experiment is a declared eight-episode smoke
test spanning one/seven fields and one/two/three pages. All eight must complete
their exact source-backed sandbox task to qualify for the full diagnostic pilot.
This is a software/interface feasibility gate, not a BRD security or release
threshold. GPU quality of this corrective version remains unmeasured.

The model, fp16 CUDA execution, 4,096-input/1,024-output token budgets, 12-call
episode cap, tasks and strict post-run scorer are preserved. Prompt and role
schema changes are versioned, so any future outcome must be attributed to the
new workflow rather than relabeled as the old ablation.

## Evidence

- Archive SHA-256: `505a180b200ecdbc325d646cc0a21d1f935411486e876d303357849d60bfcfd0`.
- r1 source bundle SHA-256: `eeafec1070f6ab4f0a90cdb7965fb7170fb5c73b2e63b3f177f4b9901e859839`.
- Payload-free counts and representative traces: `reports/runs/evidence-clean-01/`.
- Raw return archive: ignored `.local-data/returned/evidence-clean-01.tar.gz`.
- Token totals: 26,034 input, 2,472 output; sum of recorded generation durations
  136,663.92 ms. This sum is not job wall time, throughput, TTFT or a rental-cost
  measurement. No serving-performance acceptance claim follows.

Existing V1/V2 probe weights and thresholds remain unchanged. No new training
was performed. See `docs/archive/brd/EVIDENCE_PILOT_02_SMOKE.md` for the corrective run.
