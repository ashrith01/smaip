# Prior art

Week 1 composes existing ideas and measures them together. It does not introduce a new detector. The keyword hook, the fixed linear probe, and `MockActivationProbe` are offline stand-ins so the ablation table runs without weights. A later week can replace the stand-ins with trained probes. The claim that is in scope now is the composition and the joint measurement: the same episodes report utility, attack success rate, false-positive rate, cost, and latency while layers are switched on one at a time.

## Indirect-prompt-injection exposure probes

Jianshuo Dong, Yiming Liu, Maosen Zhang, Nan Deng, Peng Xu, Xiaoping Zhang, Tianwei Zhang, Jie Zhang, and Han Qiu. "Your Agentic LLMs Secretly Encode Indirect Prompt-Injection Exposure in Hidden States." 2026. arXiv:2608.02657. https://arxiv.org/abs/2608.02657

Code: https://github.com/jianshuod/IPI-exposure-signal

The paper shows that a linear probe on pre-generation hidden states predicts indirect-prompt-injection exposure, including on attacks and tasks the probe was not trained on, and it uses that signal to gate a reasoning defense. SMAIP's `LP-only` ablation is named for that linear-probe layer. The Week 1 probe is a fixed phrase scorer, not a hidden-state probe, and it does not load `Qwen/Qwen2.5-3B`. `QwenActivationProbe` refuses to construct so a test run cannot download the model. `MockActivationProbe` is the default.

## AASE

Glen Messenger. "AASE: Activation-Based AI Safety Enforcement via Lightweight Probes." 2026. https://research.google/pubs/aase-activation-based-ai-safety-enforcement-via-lightweight-probes/ and https://doi.org/10.5281/zenodo.19209688

AASE monitors activations rather than input text. Its Agent Action Gating technique is the piece aimed at prompt injection, evaluated in that write-up on InjecAgent. SMAIP's `probe-only` ablation is the corresponding slot: a probe score checked before a mutating tool runs. Week 1 fills the slot with `MockActivationProbe`.

## OpenClaw

OpenClaw's gateway treats untrusted content (pages, mail, attachments) as a prompt-injection surface and keeps enforcement outside the model: tool policy, exec approvals, sandboxing, and allowlists. https://docs.openclaw.ai/gateway/security/prompt-injection

Related write-ups:

- Frank Li. "OpenClaw PRISM: A Zero-Fork, Defense-in-Depth Runtime Security Layer for Tool-Augmented LLM Agents." arXiv:2603.11853. https://arxiv.org/abs/2603.11853
- "Agent Privilege Separation in OpenClaw: A Structural Defense Against Prompt Injection." arXiv:2603.13424. https://arxiv.org/abs/2603.13424

The reader / actor split in this repo follows that structural idea. The reader can list and read local pages. The actor is the only role that can send, write, or delete, and only through the gateway. The orchestrator has no tools.

## CaMeL

Edoardo Debenedetti, Ilia Shumailov, Tianqi Fan, Jamie Hayes, Nicholas Carlini, Daniel Fabian, Christoph Kern, Chongyang Shi, Andreas Terzis, and Florian Tramèr. "Defeating Prompt Injections by Design." arXiv:2503.18813. https://arxiv.org/abs/2503.18813

Code: https://github.com/google-research/camel-prompt-injection

CaMeL extracts control and data flow from the trusted query so untrusted tool data cannot change the program flow, and it attaches capabilities that policies check at the tool call. SMAIP's planner reads only the user instruction. Page bytes become an untrusted `result` with provenance. They are not a `task`, and they are not an approval. That is the Week 1 slice of the CaMeL / dual-LLM idea, not a reimplementation of the CaMeL interpreter.

## AgentDojo

Edoardo Debenedetti, Jie Zhang, Mislav Balunović, Luca Beurer-Kellner, Marc Fischer, and Florian Tramèr. "AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents." NeurIPS 2024. arXiv:2406.13352. https://arxiv.org/abs/2406.13352

AgentDojo is the environment CaMeL and much of the later gateway work report utility and attack success against. SMAIP's harness reports the same kind of pair, plus false positives, cost, and latency, on a small synthetic suite. The AgentDojo tasks themselves are not vendored. See `DATA.md`.

## Tool gateways

The gateway here is a reference monitor in front of tools, in the same family as:

- Tianneng Shi, Jingxuan He, Zhun Wang, Hongwei Li, Linyu Wu, Wenbo Guo, and Dawn Song. "Progent: Programmable Privilege Control for LLM Agents." arXiv:2504.11703. https://arxiv.org/abs/2504.11703
- The OpenClaw gateway above, which mediates tools, approvals, and untrusted content for a running agent.

Progent's point is that over-broad tool access is what lets an injection become a side effect, and that a deterministic policy can block the call without rewriting the agent. SMAIP's gateway-only ablation is that layer: role allowlists, argument schemas, an audit log, a path block on `audit.log`, and an approval bit for `send`, `write`, and `delete`. The approval object is minted by trusted code. Page text cannot set it.

## FastAPI and vLLM

The HTTP shape follows the OpenAI-compatible server that vLLM builds on FastAPI.

- Woosuk Kwon, Zhuohan Li, Siyuan Zhuang, Ying Sheng, Lianmin Zheng, Cody Hao Yu, Joseph E. Gonzalez, Hao Zhang, and Ion Stoica. "Efficient Memory Management for Large Language Model Serving with PagedAttention." SOSP 2023. https://arxiv.org/abs/2309.06180
- vLLM OpenAI-compatible server: https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/
- FastAPI: https://fastapi.tiangolo.com/

`POST /v1/chat/completions`, `GET /health`, and `GET /metrics` are the Week 1 surface. The mock engine is the default. The Hugging Face and vLLM engines are stubs that return a fixed string and do not import those libraries, so a test cannot download a model. An exact-prompt cache records hits and misses on the metrics endpoint. That serving shell is what a later GPU worker can sit behind. It is not a serving-system result by itself.

Week 2 adds API keys, a per-key rate limit, request-size checks, and email/phone redaction before access logs. Those are ordinary serving controls on this same shell. They are not a new detector, and they do not change the claim in the next section: the novelty is composition and joint measurement.

## What is new here

Each of the pieces above is prior art. The Week 1 system is the composition: an OpenAI-compatible CPU-first server, a privilege-separated LangGraph (orchestrator, reader, analyst, actor) with structured task, result, and provenance messages, and a tool gateway whose approval bit page text cannot set, with keyword and probe hooks on the same path. The eval harness turns those layers on and off (`no-defense`, `keyword`, `LP-only`, `probe-only`, `gateway-only`, `full-stack`) and reports utility, ASR, FPR, cost, and latency on one suite. The novelty is that composition and that joint measurement.
