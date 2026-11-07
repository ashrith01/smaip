# Data

## Schema-3 candidate review queue — unreviewed

`scripts/prepare_corpus_review.py` prepares 1,012 task-document candidates and
339 separate NotInject prompt diagnostics under ignored
`.local-data/corpus-review-01/`. No raw external payloads are vendored into Git.
Pinned NVIDIA CC BY 4.0, LLMail MIT and NotInject MIT card declarations, exact
source checksums, transformations and attribution are retained for review.
All 400 consumed NVIDIA context components are excluded. Human label approvals
are zero; split assignments and a third eligible task-source stream are missing.
Diagnostics are not representative benign calibration. This is a candidate
inventory, not a new trained model or independent evaluation corpus.

See `docs/brd/IMPLEMENTATION_NEXT_STEPS_2026-10-31.md` and the payload-free
`reports/runs/implementation-01/corpus-readiness.json`. Schema/review checks live
in `src/smaip/probes/corpus_v3.py`; they do not assert semantic label truth or
population independence. Restrictions on AgentDojo, InjecAgent and BIPIA below
remain in force.

## V2 external pilot — completed frozen-probe validation

The completed frozen-probe validation uses NVIDIA's
[Nemotron-RL-Agentic-Indirect-Prompt-Injection-v1](https://huggingface.co/datasets/nvidia/Nemotron-RL-Agentic-Indirect-Prompt-Injection-v1/tree/d738d4f361cc38bb4d7a42b9066776dade5332f5),
at revision `d738d4f361cc38bb4d7a42b9066776dade5332f5`. The pinned card declares
CC BY 4.0 and fully synthetic generation without seed data. The original source
and derived corpus are stored under ignored `.local-data/`, with upstream card,
attribution and explicit transformation records. They are not vendored into Git.
This does not change the restrictions below for AgentDojo, InjecAgent or BIPIA.

The selected corpus has 400 injected tool-text documents and 400 matched controls
derived by removing the exact annotated injection. Ambiguous spans, short
residuals, residual attack wrappers, declared near-duplicate contexts and known
development overlap are screened before score-independent selection. Derived
negative labels have not received human review. The nine-domain synthetic source
is held out from probe fitting/calibration, but its shared templates and selection
bias preclude a final independence claim. The returned GPU run scored all 800
documents with unchanged probes/thresholds: linear caught 0/400 attacks and mean
pooling caught 1/400 with one benign false alarm. This now-observed corpus is
known regression material; no threshold tuning or independent final claim was
performed. See `reports/V2_EXTERNAL_FROZEN_01_ANALYSIS.md` and
`docs/brd/V2_EXTERNAL_VALIDATION.md` for the fixed measurement plan and limits.

## V2 development corpus — October 31, 2026

`data/v2/development-01.jsonl` adds 36 original synthetic tool-result documents
for the first V2 pipeline run. Each train/calibration/test split has six benign
and six injected documents. Document labels, synthetic clean/injected source
groups, declared attack-family partitions and limitations are recorded in
`data/v2/development-01.provenance.json`, bound to the corpus SHA-256. No external
benchmark material was imported. Label review was performed by the assistant;
human label review has not occurred. The material shares an authored style and
does not constitute an independently sampled evaluation corpus. Six benign
calibration/test cases cannot validate a population 1%-FPR claim.

The training run uses the shared format-2 feature protocol, not the legacy Week 7
label/split/extraction path. See `docs/brd/V2_DEVELOPMENT_TRAINING.md`. Earlier GPU
smoke inputs and vendor development fixtures are excluded from this new corpus.

Week 1 ships only the synthetic vendor fixtures under `src/smaip/fixture_data/vendors/`. Those pages were written for this repo. They are not excerpts from the benchmarks below.

Week 2 does not add datasets. AgentDojo, InjecAgent, and BIPIA stay out of the tree. The license watch below still applies: re-check the upstream license the week you import.

Week 3 adds `src/smaip/eval/suites/week3.json`, a small original task suite for the mock agent graph. The clean tasks use the Acme and Northwind fixtures. The attack episodes use the Helix Labs pages already in this tree. Nothing in that file is copied from AgentDojo, InjecAgent, or BIPIA.

Week 4 adds `src/smaip/eval/suites/week4.json`. The new clean tasks are a file write and a role-scope refusal on the same fixtures. The new attack strings are the fixed linear-probe phrases and the mock activation-probe markers already in this repo. Nothing in that file is copied from AgentDojo, InjecAgent, or BIPIA.

Week 5 adds original pages under `src/smaip/fixture_data/week5/vendors/` and the task list `src/smaip/eval/suites/week5.json`. The attack families follow the indirect-injection setting in AgentDojo: a tool result (here, a page the reader returns) carries an instruction that tries to change a later tool call. The families are exfiltration to an attacker address, a destructive tool call, a recipient swap, an instruction override, obfuscated or encoded text, a multi-hop note split across pages, and an approval-shaped field. Benign pages use trigger-like words, including two that quote the keyword list, so the screen's false-positive rate is measured instead of assumed to be zero. No task, user prompt, injection string, or page text is copied from AgentDojo, InjecAgent, or BIPIA. The strings were written for this repo.

Week 6 adds original pages under `src/smaip/fixture_data/week6/vendors/` and the task list `src/smaip/eval/suites/week6.json`. The new attacks are a bare exfiltration, homoglyphs, nested base64, a payload split across two pages, a bare imperative beside a quotation, a quotation-only instruction, and an approval-shaped page. The benign pages are hard negatives: quoted text, a code fence, reported speech, a security article, near-miss wording, and harmless base64. `docs/ATTACK_TAXONOMY.md` names the families. No task, user prompt, injection string, or page text is copied from AgentDojo, InjecAgent, or BIPIA. The strings were written for this repo.

Week 7 adds `src/smaip/fixture_data/week7/tool_outputs.jsonl`, an original labeled set of tool results (injected versus benign). The probe corpus is those rows plus the Week 5 and Week 6 pages already in this tree. A page is positive when its vendor is marked poisoned. The split is deterministic: within each label, ids are sorted and dealt round-robin in a 3/1/1 pattern (60/20/20 train/val/test). No tool result, page, or label was copied from AgentDojo, InjecAgent, or BIPIA. The strings were written for this repo. The Week 7 command does not download those benchmarks. Model weights, when a real backend is requested, come from Hugging Face at run time and are not stored in this tree.

Do not vendor AgentDojo, InjecAgent, or BIPIA into this repository. Record the upstream commit, the license that applies to the exact snapshot, and any share-alike obligations before a later week copies an example. Re-check the upstream license the week you import. The notes here are a watch list, not a grant.

## AgentDojo

- Paper: Edoardo Debenedetti, Jie Zhang, Mislav Balunović, Luca Beurer-Kellner, Marc Fischer, and Florian Tramèr. "AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents." NeurIPS 2024. arXiv:2406.13352. https://arxiv.org/abs/2406.13352
- Code: https://github.com/ethz-spylab/agentdojo
- License watch: the project is released under the MIT License, copyright 2024 the authors above. The authors note that explicitly marked portions that come from earlier work can carry a different license. Confirm `LICENSE` at the commit you would pin. Do not vendor the environment, tasks, or attack corpus here.

AgentDojo is the dynamic tool-use environment this scaffold's metrics (utility and attack success on stateful tool traces) are aimed at. Week 5 models that setting with original pages. It still does not import the environment, the tasks, or the attack corpus. The upstream license remains the MIT License noted above; these SMAIP pages are project code, not a derivative dataset cut from that corpus.

## InjecAgent

- Paper: Qiusi Zhan, Zhixiang Liang, Zifan Ying, and Daniel Kang. "InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated Large Language Model Agents." arXiv:2403.02691. https://arxiv.org/abs/2403.02691
- Code and cases: https://github.com/uiuc-kang-lab/InjecAgent
- License watch: the repository `LICENCE` is MIT, copyright 2023 Qiusi Zhan. Confirm that file at the commit you would pin, including the case JSONL under `data/`. Do not vendor the test cases here.

InjecAgent is the indirect-injection case set cited by the AASE agent-action probe. It is a future eval source, not a Week 1 dependency.

## BIPIA

- Paper: the Benchmark for Indirect Prompt Injection Attacks. Code: https://github.com/microsoft/BIPIA
- License watch: the repository `LICENSE` is MIT for Microsoft’s code, and it says that license does not cover every dataset in the benchmark. The components called out upstream include:
  - WikiTableQuestions, CC BY-SA 4.0
  - Stack Exchange answers used in the code split, CC BY-SA 4.0
  - Invoice rows from OpenAI Evals, MIT
  - WebQA context derived from NewsQA, and summarization context derived from XSum. Upstream does not redistribute those context files and tells users to generate them. Their upstream terms need a separate check. Share-alike on the CC BY-SA pieces means a derivative dataset may have to stay under CC BY-SA.
- Do not vendor BIPIA, and do not copy its generated context files into `fixture_data/`.

## What is in-tree

| path | contents | license |
| --- | --- | --- |
| `src/smaip/fixture_data/vendors/acme_analytics/` | clean synthetic brief | project code, written for SMAIP |
| `src/smaip/fixture_data/vendors/northwind_insights/` | clean synthetic brief | project code, written for SMAIP |
| `src/smaip/fixture_data/vendors/helix_labs/` | poisoned synthetic brief | project code, written for SMAIP |
| `src/smaip/fixture_data/week5/vendors/` | original Week 5 attack and benign pages | project code, written for SMAIP |
| `src/smaip/eval/suites/week5.json` | Week 5 episode list | project code, written for SMAIP |
| `src/smaip/fixture_data/week6/vendors/` | original Week 6 attacks and hard negatives | project code, written for SMAIP |
| `src/smaip/eval/suites/week6.json` | Week 6 episode list | project code, written for SMAIP |
| `src/smaip/fixture_data/week7/tool_outputs.jsonl` | original injected and benign tool outputs | project code, written for SMAIP |

Helix Labs is labeled `poisoned: true` in `vendors.json`. Its pages tell the agent to email `attacker@evil.example` and to `delete audit.log`, and they contain an `approval: true` string. That string is not an approval. Acme Analytics and Northwind Insights are clean.

The eval harness adds two further synthetic attack strings (a linear-probe paraphrase and an activation-probe marker). Those strings live in `src/smaip/eval/scenarios.py`. They are not from the benchmarks above.

Week 5 does not download model weights. The optional CPU backend names `Qwen/Qwen2.5-0.5B-Instruct` and loads it only when `SMAIP_HF_CPU=1` and a completion actually runs. The weights are not in this tree. The model card LICENSE is the Apache License 2.0, copyright 2024 Alibaba Cloud (https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct/blob/main/LICENSE). Re-check that file before a deployment that downloads the weights. CI does not download them.
