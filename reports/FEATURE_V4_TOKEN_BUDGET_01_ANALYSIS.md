# Feature V4 tokenizer-budget audit 01

The returned tokenizer-only archive
`.local-data/returned/token-budget-v4-01.tar.gz` has SHA-256
`516450afc39e4ff9175863c64230bd58468387b0b015b9092cde4865e3e8154b`.
It was independently re-audited against the exact source bundle
`reports/smaip-feature-v4-token-budget-r1.tar.gz` (SHA-256
`eb5f57933570e29e8a927a1309c0143d5d32c798c041b11bc8e055eb3c84f443`).
All 1,012 unreviewed task-document candidates and two eligible source streams
were verified. The bundle omitted labels, and the GPU job loaded no model
weights or trained probe.

| Rendering | Median tokens | P95 | Maximum | >512 | >1,024 | >2,048 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Fixed inspection + assistant boundary | 122 | 466 | 784 | 37 | 0 | 0 |
| Source-adapted trusted task + document + boundary | 269 | 715 | 1,033 | 72 | 2 | 0 |
| Trusted task only + boundary | 153 | 293 | 293 | 0 | 0 | 0 |

All NVIDIA task/document renderings fit within 380 tokens. The two
task/document cases above 1,024 are LLMail annotated attack candidates at
1,031 and 1,033 tokens. A **2,048-token no-truncation cap** covers every
current candidate and leaves space for future similarly sized development
documents. This is a corpus-specific engineering choice, not a deployment
latency or memory guarantee. A longer future input must be refused or handled
under a separately measured protocol; no silent truncation is allowed.

The candidate queue remains a feasibility source, not an approved training
set: 1,012 rows have no review records or split roles; the queue has only two
eligible task-document streams, with unknown template lineage. The proposed
three-stream/human-review default is an experimental safeguard, not an
original BRD requirement. Feature collection can remain forward-only and
label-free while review and split decisions are made separately. A versioned
collector is prepared in `scripts/gpu/collect_feature_v4.py` and documented
in `docs/brd/FEATURE_V4_COLLECTION.md`. It will not fit or evaluate a probe.
