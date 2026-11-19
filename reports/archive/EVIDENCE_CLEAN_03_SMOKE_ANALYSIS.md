# Clean smoke 03 — eight episodes verified

R3 / agent protocol 7 completed **4/4 single-agent and 4/4 specialist** clean
tasks. The eight strict task scores and progress records were recomputed from
the returned archive; all match. The smoke qualifies for the declared full clean
pilot. It does not qualify the project for release or establish detector quality,
attack resistance or five-point statistical noninferiority.

Independent citation reconstruction from the original case pages verified:

- **44 model-selected field/value/source/line references** support their exact
  claims. Derived original quotes, character spans and source hashes match.
- Derived artifact identities match the unredacted execution-event bindings,
  and intent hashes match the trusted tasks.
- Each episode performs one exact canonical sandbox send to the authorized
  recipient, with complete source coverage and no extra effects.
- **14 page reads, 30 model calls, zero refused actions and zero repeated reads.**
  Per-episode model-call counts are 3, 3, 4 and 5 in each topology.

The same known four development cases were used as in smoke 02. Interface,
citation handling and state-scoped capabilities changed together. This is
evidence for that combined workflow correction; it is not an isolated causal
ablation of line references, an unrestricted single-agent baseline, or a learned
detector improvement. No probe weights, thresholds or model weights changed.

## Evidence integrity and one logging limitation

The existing PII formatter masks a ten-digit substring inside the displayed
`summary_artifact.intent_sha256` in both clean-00 records. No citation was waived
to accommodate this. The complete display artifact exactly matches the redaction
of the independently reconstructed artifact; the **unredacted run intent hash**
and **execution-event artifact ID** separately match the exact recomputed
digests. Original source-event hashes also match original pages. The masking is
a display/provenance usability issue, not a task execution or citation failure.
It remains documented for a future logging cleanup; the exported r3 source is
kept frozen for the full pilot.

Local records: `reports/runs/evidence-clean-03-smoke/validation.json` and
`citation-validation.json`. Raw return archive remains ignored under
`.local-data/returned/`.

- Archive SHA-256: `6f94e2f40440c6d881ab188cb1de2d7441d61c5374ac9aebf0793954d251fa36`.
- R3 source SHA-256: `a675c268fb24b243e8ee117017715f2dfd941005ba2761b237ac9d5bbb547ffe`.

The sum of episode elapsed times is 157,735.76 ms, including their recorded
overheads; it is not a request-level serving benchmark, TTFT or an independent
rental-cost measurement. No performance acceptance follows from this pilot.

Next: run the same frozen source/configuration on all 25 original tasks in both
topologies, preserving the smoke output. Commands are in
`docs/archive/brd/EVIDENCE_PILOT_03_FULL.md`.
