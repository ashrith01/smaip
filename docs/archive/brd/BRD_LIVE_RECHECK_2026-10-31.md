# Live BRD recheck — October 31, 2026

Source: [BRD: Secure Multi-Agent Inference Platform](https://brd-secure-multi-agent-inference-y62m.pages.grok.bot/).

All 19 sections were read from the rendered document in Chrome on October 31,
2026. The public web-fetch tool could not retrieve it, but Chrome displayed the
actual document without an authentication prompt. The page identifies version
**1.2 (decisions locked)**, dated **October 26, 2026, America/Chicago**. It retains
the version and key requirements used in the saved alignment assessment. This is
a rendered-content recheck, not a byte-for-byte comparison with an earlier export.
The source page was not edited. Its novelty/prior-art assertions are not newly
verified by reading the BRD.

## Confirmed requirements and implications

| Live section | Confirmed requirement | Consequence for current work |
| --- | --- | --- |
| §5 success criteria | Report the clean single-agent baseline; multi-agent utility within five percentage points. | The prepared 25-task/two-topology pilot is diagnostic. It is not statistical proof of noninferiority. |
| §5/12 | Full-stack ASR must beat keyword, least privilege and probe-only; include all ablations and adaptive attacks. | Zero-ASR ties in archived pilots do not meet the superiority requirement. The clean protocol-5 pilot is not a completed defense matrix. |
| §5/9 FR-3/12 | AUROC and TPR at 1% FPR; tool-result-token activations from Qwen2.5-3B; layer selection and held-out families/sources. | Keep the backbone frozen; improve/retrain probes under a versioned feature/split protocol. Independent low-FPR and adaptive evidence remains missing. |
| §6 out of scope | Base-LLM domain fine-tuning is excluded from v1; probe training is the training scope. | Do not turn the next experiment into Qwen SFT or a larger-base-model training job. |
| §9 FR-2 | LangGraph orchestrator, specialists, structured provenance and a single mediated tool gateway. | New protocol 5 tests authority/evidence in a Python loop. Wiring that real-model path through the required orchestration architecture remains work; the old LangGraph fixture path alone does not establish completion. |
| §8/9/10/12 | Local inference service plus observable generations, repeated serving/cache/concurrency measurements and actual GPU cost. | Direct HF-engine pilot calls do not complete the API-serving benchmark or the cost/latency gate. |
| §11 | PII policy before model/logs, output protection and flagged-action confirmation. | Trusted-recipient tokens and durable sandbox review address part of this. General model-input redaction, output leak checks and full integration remain open. |
| §13 | License-confirmed datasets and external defense comparisons. | The candidate inventory is not a substitute for native benchmark/adaptive evaluation or the specified defense baselines. |
| §16/19 | Reproducibility, results, demo and eventual public delivery; private until results. | No publishing or visibility change is authorized merely by this review. |

## BRD requirements versus experimental proposals

The BRD gives no numeric minimum probe recall, absolute clean-utility floor,
dataset size, minimum number of training-source streams, or blanket human review
requirement for every pilot training label. Proposed 50%/80% recall floors,
the 1,012-document pilot, three eligible task-source streams and the candidate
queue's default human-review requirement come from the research/experiment
design. They must not be described as original BRD mandates.

The schema-3 candidate audit enforces the selected conservative pilot policy. Its
pending status does not itself mean the BRD demands another dataset or a human
label on every row. The unresolved concerns are label/task correctness, actual
source/lineage independence and evaluation contamination. Any policy revision
must name its narrower scientific claim and preserve honest reviewer provenance;
renaming sources or auto-claiming human approval would not resolve those concerns.

The live page still names hosted Codex for the agent loop in §§15/19. The owner's
subsequent open-model-only instruction remains the active implementation choice.
This documented override does not require returning to a hosted model or adding
an OpenAI API credential.

## Next action remains unchanged

Run the prepared bounded clean protocol-5 pilot, diagnose factual/tool failures,
then continue reviewed corpus and feature work. Its source bundle and commands
are in [the implementation runbook](IMPLEMENTATION_NEXT_STEPS_2026-10-31.md).
No new GPU run was performed during this BRD recheck. The previous SSH attempt
reached the supplied server but its available key was rejected.
