# Implemented changes and next pilot — October 31, 2026

Later execution update: the r1 GPU pilot completed and was audited at **0/25 in
both topologies**, with no source reads. The analysis is in
`reports/archive/EVIDENCE_CLEAN_01_ANALYSIS.md`. The r2 smoke then scored 2/4 single-agent
and 0/4 specialist successes; its citation failures are analyzed in
`reports/archive/EVIDENCE_CLEAN_02_SMOKE_ANALYSIS.md`. The **r3 numbered-source smoke** then
passed an audited 8/8 with 44 citations reconstructed; see
`reports/archive/EVIDENCE_CLEAN_03_SMOKE_ANALYSIS.md`. The full clean pilot subsequently
completed across two segments on November 1, with **22/25 single-agent and
23/25 specialist successes**; all original records and failures are preserved.
See `reports/archive/EVIDENCE_CLEAN_03_COMPLETED_ANALYSIS.md`. The clean diagnostic is
complete; the next stage is reviewed corpus and feature preparation.
The r1 commands and preparation status below are retained as the earlier record;
the dated launch runbooks describe completed experiments. Existing source and
evidence is preserved; do not repeat these as a new independent evaluation.

The first local changes in the research plan are implemented. Existing V1/V2
weights, thresholds, historical protocol-4 runs and measured failures are
preserved. **No new detector improvement or GPU result is claimed.**

| Work | Implemented and locally tested | Remaining limit |
| --- | --- | --- |
| P0 acceptance | Recomputes task effects and saved-vector predictions from hash-bound files; rejects zero quality; checks exact one-sided 95% binomial FPR upper bound. | Absolute utility/recall and performance budgets are unspecified. Independent-final, performance and adaptive adapters remain unfinished; release cannot pass. |
| P1 authority/evidence | Opt-in protocol 5: explicit task sources, exact numeric quote/value validation, deterministic artifact; actor proposes only the artifact ID. | Labeled-integer domain. Source correspondence is not real-world truth or general semantic safety. |
| P1 durable review | Owner-bound SQLite checkpoint, action digest, expiry and transactional one-use resolution; no model rerun on approval. | In-memory sandbox sends; no real-email exactly-once integration. |
| P2 data workflow | Schema 3 separates task/content/provenance/lineage/labels/split roles; hash-bound reviews and named holdout checks. | Candidates remain unreviewed and unassigned; the reviewed training corpus is incomplete. |
| Next GPU pilot | Source bundle for 25 original clean tasks × two topologies, identical model/policy/budgets. | GPU execution pending; cannot establish security or five-point noninferiority. |

`reports/runs/implementation-01/bound-evidence/` reproduces archived utility:
single-agent 4/4, least privilege 2/4, keyword 4/4, all observed attack objectives
zero. It reproduces last-token recall 0/6 and mean recall 4/6 with one benign FP.
Both gate dispositions remain **fail**. Missing matrix arms are not invented.
Hashes establish artifact consistency, not independent execution attestation.

## Runtime and review contract

Historical `/v1` and `/v2` behavior remains available. New `/v3/agent/tasks` takes
trusted `vendor`, `recipient`, explicit `pages`, optional `required_fields` and
`subject`, plus backend/topology. Review is required. Both new routes use the
existing authentication, rate and body-size guard. A shared server needs distinct
authenticated keys; unauthenticated local mode has a shared local owner.

The model reads authorized pages and proposes `submit_claims`. Each claim needs
an allowed field, strict integer, authorized source ID and one exact quoted
numeric line. Missing coverage, conflicting/missing facts, invented values and
unsupported quotes fail. The service renders the body; the actor receives its ID
and can propose `send_summary`. The configured recipient is represented to the
model by a token. Arbitrary recipient/body/subject and write/delete tools are not
capabilities of this task. This policy is common to both new pilot topologies;
it is not a renamed historical seven-arm ablation. Legacy defense flags are
rejected in this clean pilot.

The response returns an exact pending preview and `review_id`/`action_digest`.
Resolve it as the same authenticated owner with
`POST /v3/agent/reviews/{review_id}/resolve`:

```json
{"action_digest":"<digest returned with preview>","decision":"approve"}
```

Use `decline` to reject. Resolution revalidates saved authority, source hashes,
claims and action, without another model call. Changed/expired/already-resolved
reviews conflict; another owner receives not-found. Expiry defaults to 15 minutes.
`SMAIP_REVIEW_DB` selects private persistent storage. Snapshots contain source text
and are stored with private file permissions. Tests cover restart, concurrent
resolution, replay, expiry, decline, owner separation and checkpoint tampering.

## Prepared candidate queue

Private output: `.local-data/corpus-review-01/prepared/`. Payload-free accounting:
`reports/runs/implementation-01/corpus-readiness.json`.

| Source | Pinned revision | Task candidates | Separate diagnostics |
| --- | --- | ---: | ---: |
| NVIDIA Nemotron indirect injection, declared CC BY 4.0 | `d738d4f361cc38bb4d7a42b9066776dade5332f5` | 453 controls + 228 attacks | 0 |
| Microsoft LLMail-Inject, declared MIT | `1063bdf01ec8762b812d5e06ee768a06faa5a6f7` | 203 benign emails + 128 attacks | 0 |
| NotInject, declared MIT | `847ae76cf8fea5ed325429e569ae8cfef022d2e0` | 0 | 339 benign prompts |

The 1,012 task candidates contain 656 benign candidates and 356 attacks, with
**zero human-approved labels**. Only two eligible task/tool source streams are
available; NotInject does not satisfy the third training stream. Readiness stays
pending until a third eligible independent stream, label/provenance review and
group-wise split assignment are available. Declared licenses, exact bytes, cards,
attribution and transformations are recorded for review, without asserting a
completed legal review.

All 400 previously scored NVIDIA context components, including alternative
members, are excluded before sampling from 835 remaining groups. Controls are
exact attack-span deletions, not upstream human annotations. Native system/user
tasks are retained. LLMail attacks exactly match positive `attack_attempt`
annotations and retain real team/scenario IDs. The raw sample uses a contiguous
8 MiB prefix: 5,367 complete submissions and five teams, not a random population
sample. Failed upstream compromises never become benign labels. Email tasks are
explicit single-email projections of native summarize-emails queries; benign FP
emails receive a recorded task adaptation. NotInject retains its native prompt
role. Unknown template/generator metadata remains null.

`candidates.jsonl` holds content; `review-queue.jsonl` holds proposed labels and
candidate hashes; `reviews.jsonl` starts empty. Review residual instructions, task
fit, duplicates, provenance and transformations. One adjudicated decision uses:

```json
{"id":"<candidate ID>","candidate_sha256":"<fingerprint>","reviewer_id":"<actual reviewer>","reviewer_type":"human","decision":"accept","label":0,"task_scope_verified":true,"provenance_verified":true,"note":"<actual adjudication>"}
```

Use `reject`/`ambiguous` when appropriate. Assistant reviews must say `assistant`;
they do not satisfy the default human-review requirement. Any candidate edit,
including split assignment, needs a new hash and review. Do not batch-approve or
invent lineage IDs. Previously observed material stays `regression`. Named
in-distribution/source-held-out/family-held-out policies enforce their declared
connections; normalized exact and shingle near-duplicates cannot cross assigned
roles. Mechanical checks do not prove population independence.

After review/assignment, create a fresh audit:

```bash
cd /Users/ashrithvadde/Documents/GitHub/smaip
.venv/bin/python -m smaip.probes.corpus_v3 \
  --corpus .local-data/corpus-review-01/prepared/candidates.jsonl \
  --reviews .local-data/corpus-review-01/prepared/reviews.jsonl \
  --policy .local-data/corpus-review-01/prepared/split-policy.json \
  --output .local-data/corpus-review-01/prepared/audit-after-review.json
```

Targets: 128/128 fitting, 128/128 selection, 400 benign/100 attacks for threshold
development. These are not statistical calibration or final testing. The new
feature protocol, saved-vector selection grid and independent-final evaluation
remain subsequent work. Schema 3 alone cannot reinterpret format-2 weights.

## Run the clean GPU pilot

The source bundle includes original fixtures, with no external corpus or weights.
It runs the pinned offline Qwen 3B, fp16 CUDA, 12 calls/episode, 1,024 output and
4,096 input tokens. Both topologies share the new task policy. Review is explicitly
disabled for sandbox benchmark sends; human review behavior is tested separately.

From the Mac:

```bash
cd /Users/ashrithvadde/Documents/GitHub/smaip
scp reports/smaip-task-evidence-pilot-r1.tar.gz \
  reports/smaip-task-evidence-pilot-r1.tar.gz.sha256 root@64.177.116.166:/root/
ssh root@64.177.116.166
```

On the GPU:

```bash
cd /root
sha256sum -c smaip-task-evidence-pilot-r1.tar.gz.sha256
test ! -e /root/smaip-task-evidence-pilot-r1
tar -xzf smaip-task-evidence-pilot-r1.tar.gz
cd /root/smaip-task-evidence-pilot-r1
source /root/smaip/.venv/bin/activate
tmux new -s smaip-evidence
bash scripts/gpu/run_evidence_pilot.sh
```

Run the final `bash` command inside tmux. Preflight verifies source hashes, cached
model, CUDA and structured schema. Limits: 3,600-second process timeout, at most
600 model calls and 614,400 generated tokens. These are ceilings, not wall-time or
cost estimates. Normal failure/timeout preserves partial runs and a return
archive. VM termination/forced kills can prevent archiving; flushed runs remain.

After completion, from the Mac:

```bash
cd /Users/ashrithvadde/Documents/GitHub/smaip
mkdir -p .local-data/returned
scp root@64.177.116.166:/root/smaip-task-evidence-pilot-r1/reports/v3/evidence-clean-01.tar.gz \
  .local-data/returned/evidence-clean-01.tar.gz
.venv/bin/python scripts/analyze_evidence_pilot.py \
  --archive .local-data/returned/evidence-clean-01.tar.gz \
  --bundle reports/smaip-task-evidence-pilot-r1.tar.gz \
  --output .local-data/returned/evidence-clean-01.audit.json
```

The auditor validates source/run hashes, exact cases, topology/budgets and sandbox
effects, and rejects changed scores or unsafe archive members. Diagnose clean
failures before more feature collection. No proposed absolute utility/recall floor
has been silently adopted. Software tests are distinct from model quality,
security and release acceptance. Two existing optional HF tests remain skipped
without their separately enabled model environment.

BRD alignment uses saved v1.2 plus the owner's open-model-only override. The live
BRD was initially inaccessible, but all 19 live sections were successfully read
in Chrome on October 31 and still identify v1.2, October 26. See
`BRD_LIVE_RECHECK_2026-10-31.md` for confirmed requirements and remaining gaps.
The human-review/three-source defaults above are experimental policy choices,
not original BRD mandates. The already exported r1 bundle retains its earlier
documentation snapshot; its pinned runtime code is unchanged. Research sources
and later experiment ordering are in `IMPROVEMENT_PLAN_2026-10-31.md`.
