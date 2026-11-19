# Full r3 clean pilot — timeout with 40 verified episodes

The returned archive's exit code is **124**, confirming the frozen wrapper's
900-second timeout. Its summary still says running, and it contains 40 of the
planned 50 completed episodes. It is an **incomplete run**, not a 50-episode
result or a quality pass.

| Topology | Completed | Strict successes | Observed rate |
| --- | ---: | ---: | ---: |
| Single-agent | 20 | 17 | 85% |
| Specialist | 20 | 19 | 95% |

The 36 successful episodes' **138 citations** were independently reconstructed
from original source pages. Artifact and intent bindings, original quote spans,
and exact sandbox sends were rechecked, accounting for the already documented
display-only digest redaction. No failed binding was waived. There are 176 model
calls in completed records; this excludes any unflushed in-flight work lost at
the timeout and is not a complete billing/performance denominator.

## Genuine model failures preserved

- Single-agent clean-01: the first numeric pairs were correct, but one reference
  selected the prose line instead of the metric line. Later retries invented
  more fields/values. The 12-call budget was exhausted.
- Both topologies, clean-10: the model included three unreported fields with zero
  values. These claims were refused. The single agent exhausted its budget;
  the specialist analyst exhausted its phase allowance and its actor was blocked.
- Single-agent clean-12: incorrect line references, incomplete claim lists and
  unreported zero-valued fields prevented completion. The budget was exhausted.

Across attempts there were 32 exact field/value/line mismatches and two
incomplete-brief refusals. These are not timeout failures: the episodes finished
with recorded failed scores. They must remain in the eventual full-pilot table.

The generic validation feedback did not help these retries recover. More specific
claim-index/error feedback is a possible **later versioned experiment**, not a
change to apply during completion of this baseline. The next action only fills
missing episodes, without changing the model, prompts, state policy, validation,
scorer, decoding or episode budgets.

## Continuation boundary

Cases clean-20 through clean-24 in both topologies are missing: **10 episodes**.
`scripts/continue_evidence_pilot.py` is an additional launcher outside `src/`.
It audits the parent, verifies all original r3 manifest members and imported
runtime hashes, and carries all 40 completed run files byte-for-byte, including
all four failures. It then invokes the same frozen runtime for missing pairs only.

The new summary records the exact parent archive hash, source bundle hash and
complete launcher source/hash. It identifies a separate execution segment;
latency/cost must not be represented as one uninterrupted serving benchmark.
The parent files and archive are not modified. A timed-out in-flight episode with
no durable record may be executed again; its earlier unflushed work is unknown
and cannot be counted as zero. Effects are in-memory, not real external sends.

The launcher has a 30-minute continuation cap and at most 120 new model calls /
122,880 generated tokens, excluding all earlier work. Synthetic CPU tests verify
preserved failed/successful bytes, absence of calls for completed IDs, rejection
of forged parent scores, and archival of interrupted continuation results.
They are not measured GPU continuation results.

Local evidence: `reports/runs/evidence-clean-03-full/validation.json` and
`failure-diagnosis.json`. Raw archive remains ignored under `.local-data/returned/`.

- Parent archive SHA-256: `d7566b93bd1615abf18dece38a56dc3aa3bc7b935979456c8f1adf793ed50fbb`.
- Frozen r3 source SHA-256: `a675c268fb24b243e8ee117017715f2dfd941005ba2761b237ac9d5bbb547ffe`.

No probe training or threshold change occurred. This remains a known synthetic
clean workflow diagnostic under common constraints, not attack-resistance,
independent generalization or statistical noninferiority evidence. See
`docs/archive/brd/EVIDENCE_PILOT_03_CONTINUATION.md` for the next commands.
