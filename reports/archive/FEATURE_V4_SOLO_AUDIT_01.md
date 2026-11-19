# Feature V4 solo mechanical audit 01

The pinned candidate queue and AV's first review were audited without
changing either source. Run `scripts/audit_feature_v4_solo_candidates.py` with
the project virtual environment to reproduce this versioned output. The
private row-level manifest and summary are in
`.local-data/feature-v4-solo-audit-01/`; the manifest SHA-256 is
`8952a310a6e47663c15416909dbe20a9385939429c4410afafb396dd6785b7ae`.
The script refuses to overwrite an existing audit directory.

| Check | Result |
| --- | ---: |
| Task/document candidates | 1,012 |
| Separate prompt diagnostics excluded from this audit | 339 |
| Source labels: benign / attack | 656 / 356 |
| Exact unique trusted-task/document pairs | 969 |
| Exact duplicate groups / redundant rows | 38 / 43 |
| Exact duplicate groups with conflicting source labels | 0 |
| AV-screened candidate rows | 32 |
| Quarantined candidate rows | 1 (`nvidia-12-clean`, R031) |
| Accepted labels / assigned split roles | 0 / 0 |

The manifest retains all 1,012 candidate IDs and hashes. Its status counts
are 968 canonical source-labeled development rows, 43 duplicate references,
and one quarantined row. Duplicate references are preserved for provenance;
they are not 43 independent examples. Source labels are distinct from AV's
32 blind-screen judgments, and the latter are explicitly **not** full
candidate approvals. No row is marked as task-scope or provenance verified.

Every task/document row passed the schema's explicit-task, nonempty-document,
source-declaration, and unassigned-role checks. The local source inventory
revisions and declared licenses matched the candidates, and hashes of ten
locally pinned NVIDIA/LLMail source files matched the inventory. This checks
local bytes and declarations; it is not a current remote license check or a
semantic verification of the source labels. A changed/malformed input makes
the script fail rather than silently enter the development manifest.

Using context, pair, template, author, generation-batch and exact-pair links,
the queue has 614 metadata-connected components; the largest contains all
128 LLMail attack rows. A conservative four-token-shingle near-copy pass
added four component merges, leaving 610 components, with a largest size of
128. These are grouping diagnostics rather than independent sampling units.
Near-copy similarity can both miss semantic duplicates and overconnect
repetitive text. No grouped train/selection/threshold split was assigned.

The existing strict corpus-v3 audit remains `pending`. This manifest is
development inventory only: no threshold, calibration set, final test,
detector promotion, or BRD 1%-FPR claim follows from it. The next bounded
work is to define a separately versioned source-label development policy
and run agent-level diagnostics under that narrower claim, as described in
`docs/archive/brd/FEATURE_V4_SOLO_REVIEW_PLAN.md`.
