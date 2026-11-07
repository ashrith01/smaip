# V2 GPU feature smoke 01 — passed

Reviewed October 31, 2026. Original archive: `reports/feature-smoke-01.tar.gz`.
SHA-256: `c963e232b6c10aa3f058272c6a5fdc7d3d40e1d62182f8884d3d06d7384d1e1d`.
Unmodified returned files, the helper source and the local audit inventory are
preserved under `reports/runs/feature-smoke-01/`.

## Verified evidence

The returned summary reports a passed run on the restored NVIDIA A16 using CUDA
13.0, Torch 2.13.0+cu130, Transformers 5.19.0 and float16 Qwen2.5-3B-Instruct at
revision `aa8e72537993ba99e69dfaafa59ed015b17504d1`. The helper-source hash matches
the exact local helper. The recorded source manifest matches the verified r5
bundle at `76481bfcf856f1f5b05ffe45d628aa28c9f8dfef`, including all 279 files.

Feature protocol fingerprint:
`e84129151cabbe6ba45e017c52310146af4c3606433d6fb30a34465bfc35ebe0`.
The protocol pins model/tokenizer revisions, chat template, trusted rendering
context, CUDA/float16 execution, single-document batches, a 512-token budget and
float32 pooling over fully contained tool-content tokens.

| Synthetic smoke document | Total tokens | Selected tool-content tokens |
| --- | ---: | ---: |
| Plain numeric report | 74 | 10 |
| Instruction in a tool result | 80 | 16 |
| Quoted policy, boundary marker and Unicode | 93 | 29 |

The archive contains 18 raw vectors: last-token and mean pooling for three
documents at layers 0, 18 and 35. Each vector has 2,048 dimensions. The local
audit verified all 36,864 scalar values are finite, the input text hashes,
token/mask lengths, selected token counts, rendering-hash consistency, protocol
identity, helper/source provenance and every archived member's checksum.

The verified helper reports literal-offset mask agreement on each input,
rejection of oversized content without truncation, and an independent model
forward for the first document. Its six reference-pooling comparisons report
maximum absolute error 0.0. This comparison was executed on the GPU; the local
audit checks returned evidence and does not rerun the model or reconstruct
reference hidden states that were not archived.

## Scope and next stage

This validates the extraction path on three synthetic smoke inputs and three
selected layers. It does not measure classification quality, certify every
layer/input, fit probe parameters or update Qwen weights. These smoke inputs
are not an independent training, calibration or final-test corpus.

The remaining preparation is local: create/review the V2 corpus and implement
collection, fitting and frozen-threshold calibration commands using this shared
extractor. Preserve raw vectors and source/protocol provenance in that pipeline.
Then collect the reviewed corpus on GPU, fit new probes, calibrate on a separate
split and evaluate once on held-out data. The actor utility failures from paired
run 02 and final model-driven defense evaluation remain separate pending work.
