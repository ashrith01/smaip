# Open-model BRD implementation — local checkpoint

## Owner clarification

On October 30, 2026, the owner clarified that the agent should also use an open-source model. This supersedes the BRD v1.2 hosted-Codex choice. The implementation now uses optional local HF generation or a self-hosted vLLM endpoint. No OpenAI API key is required. The old `clients/codex.py` stub remains historical scaffolding and is not used by the new path.

## Current status — October 31, 2026

Returned protocol-4 paired run 02 verified all 279 r5 files and 24 episodes. Clean task success improved to 2/4 least privilege; no-defense and keyword remain 4/4. No declared attacker objective succeeded. The restored GPU passed the V2 feature smoke and first real V2 development collection/fitting run. All 152 training-bundle files, 66 Python sources, 36 documents, 72 raw vectors, both fits/calibrations and frozen test predictions were audited. The linear probe catches 0/6 development test attacks with 0/6 benign false alarms; mean pooling catches 4/6 with 1/6 false alarms. See `reports/V2_PROBE_DEVELOPMENT_01_ANALYSIS.md`. Development pipeline execution is verified; the independent corpus/evaluation, least-privilege utility condition and baseline susceptibility remain unmet.

External frozen validation 01 is now returned and audited: all 400
score-independently selected NVIDIA clean/injected pairs were scored with
unchanged development models/thresholds. Linear catches 0/400 attacks; mean
pooling catches 1/400 and falsely flags the same pair's clean control. All 164
bundle files, 67 source hashes, preparation replay, scores and classifications
were checked. Raw external data/vectors stay outside Git under ignored
`.local-data/`. These poor transfer results and label/independence limitations
are recorded in `reports/V2_EXTERNAL_FROZEN_01_ANALYSIS.md`. The next task is
larger reviewed training/calibration data plus a predeclared untouched final
evaluation protocol; this observed external set is now known regression
material. Local suite: **229 passed, 2 optional HF tests skipped**.

## Preserved baseline

Commit `9d13c05` preserves the verified v1 recovery, trained probe parameters and original training/rescore/parity evidence. Legacy Week 1–7 commands retain their meanings, including the historical `LP-only` linear-probe label. The evidence analyzers can validate the recorded engine hashes against this frozen commit when the current tree moves forward. Canonical v1 probe files are unchanged; new artifacts belong under `artifacts/v2/`.

## Implemented locally

- `smaip eval-contract`: schema-2 configurations independently declare topology, keyword, detector, gateway, model and call/token budgets. Structural least privilege and linear/mean probes have separate names. The output is explicitly a contract, not measured quality.
- `smaip brd-gate`: pass/fail/pending assessment of supplied versioned evidence. Missing real-model/data/performance evidence cannot pass. A tie in ASR cannot satisfy strict full-stack superiority. Performance budgets must be supplied rather than invented.
- `probes/low_fpr.py`: calibration-only threshold selection under an empirical FPR budget, frozen-threshold evaluation and confusion counts. Tiny benign samples are flagged as insufficient for a zero-event 1%-FPR confidence claim.
- `probes/manifest.py` and `smaip validate-corpus-v2`: explicit document labels; disjoint declared source/group/attack-family membership; normalized exact-duplicate checks; manifest hashes and sample counts. These checks do not substitute for label review, near-duplicate review or upstream license validation.
- `probes/protocol.py`: version-2 contract pins model/tokenizer commits, chat template and trusted context hashes, precision/execution device, layer convention, max length and single-document batching. Fast-tokenizer offsets identify only fully contained tool-content tokens. Oversized inputs are rejected rather than silently truncated. Both collection and scoring use the same extractor; mean reduction is fp32. Format-1 weights cannot be relabeled as format-2 weights.
- `python -m smaip.probes.pipeline_v2`: separate offline GPU collection, train-only logistic fitting, calibration-only thresholds and frozen test evaluation. The initial pipeline requires explicitly original development-corpus provenance, uses one preselected layer, saves raw vectors and emits format-2 probes. Tests verify test-feature changes cannot affect weights/thresholds, calibration changes cannot affect weights/train moments, frozen artifacts remain unchanged by evaluation, and tampered/incomplete data is rejected. The first real development run is returned and verified; this is not independent low-FPR acceptance.
- `hf-local` / `vllm-local`: opt-in generation backends. HF uses the cached pinned snapshot and the existing model loader, with greedy decoding and explicit token limits. vLLM uses a loopback self-hosted endpoint (SSH forwarding can expose a remote GPU locally), with no provider SDK or key. Neither backend loads weights/connects merely by being constructed.
- The chat API accepts these new explicit selectors when enabled. Cache keys include backend/model/configuration identity. Backend-reported token counts are retained on cache hits; absent counts are marked as estimates. New open-model paths reject nonzero temperature because their evaluation policy fixes greedy decoding. Backend failures return 503.
- `smaip agent-v2`: a bounded LangGraph pilot with model-proposed JSON actions, single-agent and reader/analyst/actor topologies, role-capability checks and in-memory tool effects. Quarantined raw content is not forwarded to a model. Gateway variants require an approval digest bound to the exact proposed action; a model cannot set it through arguments. Traces preserve model/backend usage, refused actions, quarantine and actual enabled detector scores.
- Agent protocol 3 uses strict Pydantic response models for each tool and `final`. Their shared JSON Schema drives HF token filtering with lm-format-enforcer 0.11.3 and vLLM JSON-schema requests. The same schema applies across roles/ablations; it constrains formatting and types, while leaving permission checks and factual quality separate. Model/action-schema hashes and decoding mode are recorded. The pinned helper adds a small dependency; no hosted provider is involved.
- Agent protocol 4 preserves the formatter's result and analyst prose separately in a strict, explicitly untrusted Pydantic `SummaryHandoff`. Roles are instructed to preserve user-requested formats and avoid padding absent metrics or creating scratch files. This is a local development repair, not a measured GPU utility gain; action proposals and capability/approval checks remain separate.

The new runtime only accesses local vendor fixtures and an in-memory workspace. It does not send real email, write user files or expose arbitrary execution. `POST /v2/agent/tasks` exposes the bounded pilot behind the existing authentication/body/rate guard. Approval currently uses an exact-digest confirmed rerun, not persisted graph resumption. No live web-fetch adapter, deployed persistent review/resume API, complete external benchmark adapter or independent V2 corpus has been added yet. The original 36-document corpus is development-only.

## What is tested versus pending

Local tests cover contract semantics, tie-aware low-FPR calibration without test fitting, group/family/text leakage rejection, content masks, old/new artifact incompatibility, self-hosted transport and exact cache usage, role separation, quarantine, bounded invalid model outputs and action-bound approval. Network calls are mocked in the transport tests; scripted model responses are explicitly labeled test inputs, not measured model quality.

The HF adapter has executed three GPU pilots and two paired development runs using the pinned Qwen snapshot. See the `reports/OPEN_MODEL_PILOT_*_ANALYSIS.md` and `reports/OPEN_AGENT_DEV_*_ANALYSIS.md` reports and raw `reports/runs/` directories. The V2 extractor passed its bounded GPU smoke and 36-document development collection. Two new format-2 development probes are saved under `reports/runs/probe-development-01/probes/`. Live vLLM validation and independent-corpus collection remain pending. No independent accuracy values, dollars-per-token numbers or model-driven attack-resistance gains are claimed. Existing V1 scores retain their recorded limitations.

The `agent-v2` CLI currently exposes the no-defense, keyword-screen, least-privilege-only and gateway-only pilot variants. Learned-detector/full-stack runs require explicitly constructed V2 probes in the runtime and new data/training; there is no silent fallback to V1 weights or phrase stubs.

## Validation recorded for this checkpoint

- Initial checkpoint suite: **193 passed, 2 optional HF tests skipped**. After pilot-01 orchestration repairs: **196 passed, 2 optional HF tests skipped**. Protocol-3 Pydantic/constrained-response integration: **213 passed, 2 optional HF tests skipped**. With paired development-case grading/runner: **220 passed, 2 optional HF tests skipped**. Protocol-4 handoff regression: **221 passed, 2 optional HF tests skipped**.
- `make week6 -o install`: all legacy evaluation gates passed using the already installed development environment.
- Mock `make week7-cpu -o install`: passed; vLLM bench correctly skipped without CUDA.
- Both V1 evidence analyzers passed against frozen source commit `9d13c05`; original probe hashes/results remain unchanged.
- The negative `brd-gate` check returned `pending` and exit code 1, as required for unmeasured contract input.
- No real model generation, Qwen weight loading/training, public deployment or hosted-provider call was executed locally. The latest local suite is **225 passed, 2 optional HF tests skipped**, including fitting/scoring checks on synthetic numeric test fixtures. Returned GPU evidence verifies protocol-4 development generation, the bounded feature smoke and first real V2 development training run. The local audit also replayed logistic fitting from the returned real feature vectors, without loading Qwen; coefficients agree to floating-point tolerance and calibration/test outputs reproduce exactly. Tokenizer-only/unit validation does not measure agent quality.

## Local commands

```bash
.venv/bin/python -m pytest
.venv/bin/python -m smaip.cli eval-contract --output reports/v2/eval_contract.json
.venv/bin/python -m smaip.cli brd-gate reports/v2/eval_contract.json
```

The last command must return exit code 1 and `pending`: a contract is not result evidence. It is a useful negative acceptance check.

To validate a future JSONL dataset, each row must have `id`, `text`, `label` (0/1), `split` (`train`, `calibration`, `test`), `group_id`, `source_id`, and a nonempty `attack_family` for positives. Labels explicitly refer to documents, not inherited poisoned-vendor status. A reviewed upstream/license manifest remains required before importing external data.

```bash
.venv/bin/python -m smaip.cli validate-corpus-v2 /path/to/reviewed-corpus.jsonl
```

## Historical manual GPU pilot — revision 3 completed

A separately named transfer bundle `reports/brd-open-model-v2-r3.tar.gz` contains the Pydantic/constrained-response code and the pinned 45 KB decoder wheel. It preserves earlier GPU checkouts and results. From the Mac:

```bash
scp "/Users/ashrithvadde/Documents/GitHub/smaip/reports/brd-open-model-v2-r3.tar.gz" root@45.63.76.130:/root/
ssh root@45.63.76.130
```

On the GPU:

```bash
test ! -e /root/smaip-open-model-v2-r3 || { echo "Choose a fresh extraction directory; preserve existing results."; exit 1; }
tar -xzf /root/brd-open-model-v2-r3.tar.gz -C /root
source /root/smaip/.venv/bin/activate
```

Use the virtual environment and HF cache path that succeeded previously. If those paths differ, reuse the previous values. Install only the bundled decoder wheel, offline and without resolving or upgrading other packages. Its dependencies (Pydantic, interegular, packaging, PyYAML) are already present in the returned GPU package list.

 Use a fresh checkout directory so the previous recovery checkout and all its evidence remain intact. Activate the same GPU Python environment as before, then:

```bash
cd /root/smaip-open-model-v2-r3
python -m pip install --no-index --no-deps vendor/lm_format_enforcer-0.11.3-py3-none-any.whl
bash scripts/gpu/open_model_pilot.sh
```

The script uses the already-cached Qwen2.5-3B snapshot `aa8e72537993ba99e69dfaafa59ed015b17504d1` in fp16, one visible GPU, and offline access. It runs clean Acme in both topologies first; if either is incomplete it skips the poisoned Helix tasks. Otherwise it runs Helix in both topologies. No probe model is loaded, so generation does not duplicate a detector's 3B model on the A16. The script installs nothing, does not retrain and produces only sandboxed effects. The explicit wheel-install command above adds just the pinned decoder, preserving Torch/Transformers/vLLM. Runtime has not been measured for this revised pilot.

Outputs include per-run JSON/model/tool traces, Pydantic-schema/decoder identity, phase termination, exit statuses, bundle verification, GPU metadata, the evaluation contract and package versions in `reports/v2/open-model-pilot-03.tar.gz`. An incomplete task is preserved as an observed outcome. A generation runtime exception is preserved in its log and stops further calls. No task failure is relabeled as a model success. If the pilot output exists already, choose a new `SMAIP_PILOT_OUTPUT` path.

Copy the result from a Mac Terminal:

```bash
scp root@45.63.76.130:/root/smaip-open-model-v2-r3/reports/v2/open-model-pilot-03.tar.gz "/Users/ashrithvadde/Documents/GitHub/smaip/reports/"
```

Inspect that returned pilot before scaling to larger model-driven evaluation or claiming a susceptible baseline. A strong model may ignore these original attacks even with defenses off; that outcome would leave the baseline-susceptibility criterion unproven.

## Remaining work in order

1. Preserve the completed protocol-4 regression/feature-smoke evidence and resolve the remaining actor utility failures. Keep this development suite out of independent final claims. Add API-level bounded agent review/resume and allowlisted read-only fetching after the local loop is verified.
2. Review and build the V2 corpus with enough independent benign cases, held-out attack families/sources and adaptive cases. The validator is ready; the corpus, provenance and license review are not complete.
3. The first development collection/fitting/calibration run is audited. Extend its provenance/acceptance checks for the reviewed independent corpus, then train new weights under the frozen independent-data protocol. Preserve old and development weights as historical evidence; development metrics cannot establish the final low-FPR requirement.
4. Wire the full model-driven ablation runner and result provenance into the acceptance gate. Add output-canary/model-input privacy policy, deployment-level approval lifecycle, real-model quality regression and performance budgets. Current mock/unit passes are software checks only.
5. Validate actual HF/vLLM API serving on the rental; repair/repeat the serving benchmark with request-level percentiles, token accounting, cache conditions and the owner's actual hourly rate. Keep vLLM serving and probe memory ownership explicit on the one-card host.
6. Complete architecture/threat documentation, reproducible release, demo/write-up and public publication only after the declared acceptance conditions are addressed.

References used for implementation: [Hugging Face fast-tokenizer offset mappings](https://huggingface.co/docs/transformers/main_classes/tokenizer), [vLLM self-hosted online serving](https://docs.vllm.ai/en/latest/serving/online_serving/), [lm-format-enforcer](https://github.com/noamgat/lm-format-enforcer), [vLLM structured outputs](https://docs.vllm.ai/en/latest/features/structured_outputs/). These document interfaces; they do not validate this implementation's model quality.
