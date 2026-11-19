# Clean smoke 02 — audited citation failures

Returned r2/protocol-6 smoke: **single-agent 2/4, specialists 0/4**. All eight
episodes completed and their files, source bundle, model/revision, exact cases,
budgets and task scores were verified locally. The smoke gate correctly remains
unqualified for the full pilot. No detector training was performed.

Across the first claim submission in each episode, **44/44 field/value pairs
matched the task oracle**. This count is post-run diagnosis only, not information
fed back into the workflow and not a valid task-success score. Attribution and
complete authorized effects are still required. Later retries also invented
unreported zero-valued fields and artifact IDs; those remain failures.

All four specialist readers obtained their authorized pages. Their analysts
appended #fragments, labels or hashes to source IDs and/or added literal quotation
marks inside quote strings. Some cited the wrong page as well. All four analysts
failed source validation and their actors were correctly blocked. Single-agent
failures also repeated malformed quotes; two exhausted their 12-call budgets.

| Refusal reason | Count across attempts |
| --- | ---: |
| Quote did not identify one authorized source span, including unknown source IDs | 20 |
| Quote did not support the exact field/value | 2 |
| Unknown validated artifact | 5 |
| Unauthorized page request | 4 |

The old `reads=6/2` display counted successful read calls, including repeats,
against the number of pages. It did not mean six distinct pages were accessed.
The next version separately reports unique pages and read calls.

## Corrective design: protocol 7, r3

Requiring the model to recopy exact URI and quote strings created avoidable
formatting work. The next policy uses explicit source IDs and numbered original
source lines. A model-proposed claim contains field, integer value, source ID and
line number. The service verifies the chosen line reports the exact field/value,
then attaches its original quote, source hash and character span. It does not
select a supporting line, infer a missing value, strip a forged URI fragment,
normalize a bad quote or insert an expected answer.

All source lines are shown, including headings, blank lines and prose. No
pre-extracted numeric answer map is handed to the model. Strict original-source
coverage, conflicting-value checks, completeness and quote validation remain.
New artifacts bind the model's references as well as the derived quotes; durable
approval revalidates them. The previous exact-quote validator remains available
for stored version-1 artifacts. Identical repeated quote lines remain
conservatively rejected by that validator; line-reference support does not loosen
this earlier uniqueness rule.

Both topologies share the same state-scoped capabilities: read authorized unread
pages, submit claims after complete coverage, and propose sending only after
validation. The decoder binds trusted vendor/page/source identities and an
existing artifact ID. The server independently checks them if decoding is
bypassed. A final response remains an abort; no action or success is fabricated.

This is a changed workflow policy and citation interface, so it is a new agent
protocol. It must not be presented as a detector gain or as the old unrestricted
single-agent/least-privilege ablation. The same eight known development tasks,
12-call limit, Qwen revision, fp16 and 4,096-input/1,024-output token budgets are
retained. GPU utility recovery remains unmeasured until r3 returns.

Evidence: `reports/runs/evidence-clean-02-smoke/`. Raw archive remains ignored at
`.local-data/returned/evidence-clean-02-smoke.tar.gz`.

- Archive SHA-256: `75422895de39326dce3c50efa89564178862f5ac11e0184f9be5e5b55717f77b`.
- Source bundle SHA-256: `027a7396fe5e145bd4e5b44b48d4fd0f580668cf102647fb6eafd639fd6318e7`.

Next run: `docs/archive/brd/EVIDENCE_PILOT_03_SMOKE.md`. Existing probe weights,
thresholds and historical results remain unchanged.
