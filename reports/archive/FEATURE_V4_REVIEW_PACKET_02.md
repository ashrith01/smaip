# Feature V4 second reviewer packet

The versioned, answer-free packet is at
`.local-data/feature-v4-reviewer-packet-02/`. A shareable archive containing
only its README, blind cases, and blank review template is
`.local-data/feature-v4-reviewer-packet-02.zip` (SHA-256
`896f15be75510ebcecf6f4df94f3beae212f636a55fc0de2fa2e5a85623c581d`).
The sealed mapping is stored separately at
`.local-data/feature-v4-review-packet-02/` and must not be given to the
reviewer. The builder is `scripts/build_feature_v4_review_packet_02.py`.

The builder checked the pinned 1,012-row task/document queue and prior
32-case packet by SHA-256. It selected 16 rows from each source/upstream-label
stratum using a deterministic hash, without using model scores. Exactly one
row is a blinded repeat for a second judgment; the other 63 task/document
pairs were absent from the first packet. All 64 selected pairs are distinct
within this packet. The blind file contains only `source_origin`,
`native_role`, `trusted_task`, `untrusted_text`, and `review_key`. Its SHA-256
is `f9fba6d4ba3e38680e703115cddecef53797285dcb643bef0a995f6cdd719e66`.

This packet was prepared for an independent reviewer other than AV. The owner
is working solo, so completing it is **optional** and not a required gate.
If AV reviews it, record that it is a second pass by the same person, not an
independent review. Each judgment needs a reason, reviewer ID, UTC time, and
task-boundary clarity. The packet is a development data-quality screen; it is
neither calibration nor a fresh final test. No human judgments for packet 02
have been received.

The metadata and exact-pair linkage audit of the 1,012 queue rows found 614
connected components using source context, pair, template, author, generation
batch, and exact task/document identity. NVIDIA has 453 components across 681
rows, including 228 paired attack/control components. LLMail has 161
components across 331 rows; all 128 attacks fall in one connected component.
Packet 02 spans 49 such components, with 16 LLMail attacks in that one
component. These counts exclude semantic near-duplicate links and are not
independence estimates. Duplicate and lineage resolution is still required
before accepted split assignment.

The earlier human submission and AV's follow-up remain intact. The
conflicting R031 row remains quarantined; exclusion is a valid solo resolution
without a second reviewer. No candidate has been relabeled, split, calibrated,
or promoted. See `docs/archive/brd/FEATURE_V4_SOLO_REVIEW_PLAN.md`.
