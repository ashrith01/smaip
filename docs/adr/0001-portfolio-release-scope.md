# ADR 0001: Bound the portfolio release claim

Status: accepted, 2026-11-07; research-track commitment superseded by
[ADR 0002](0002-close-as-completed-study.md) on 2026-11-13.

## Context

The original BRD asks for independent low-FPR detector evidence, full-stack
attack superiority, and serving benchmarks. The current saved V4 features and
source labels are development evidence; the latest real-model pilot measured
clean tasks only. GPU inference and a new independent final dataset are not
currently available.

## Decision

Release SMAIP as a reproducible research and engineering portfolio project
with a CPU-only scripted guardrail demo, audited real-model clean-task results,
historical failed probe transfer, and explicitly limited V4 development
results. Do not call the V4 probe a validated or deployed defense. Preserve
the BRD acceptance work as an open, separately reported research track.

Keep raw external data, private reviews, Qwen snapshots, and local model
artifacts outside the published Git tree. Do not silently update historical
weights, thresholds, scores, or failed runs.

## Consequences

The repository can be complete as a portfolio case study while the BRD gate
remains unpassed. A later release claiming attack reduction or 1%-FPR
operation needs new grouped data, a frozen threshold, and real agent tests.
