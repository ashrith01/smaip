# Data

Week 1 ships only the synthetic vendor fixtures under `src/smaip/fixture_data/vendors/`. Those pages were written for this repo. They are not excerpts from the benchmarks below.

Week 2 does not add datasets. AgentDojo, InjecAgent, and BIPIA stay out of the tree. The license watch below still applies: re-check the upstream license the week you import.

Week 3 adds `src/smaip/eval/suites/week3.json`, a small original task suite for the mock agent graph. The clean tasks use the Acme and Northwind fixtures. The attack episodes use the Helix Labs pages already in this tree. Nothing in that file is copied from AgentDojo, InjecAgent, or BIPIA.

Week 4 adds `src/smaip/eval/suites/week4.json`. The new clean tasks are a file write and a role-scope refusal on the same fixtures. The new attack strings are the fixed linear-probe phrases and the mock activation-probe markers already in this repo. Nothing in that file is copied from AgentDojo, InjecAgent, or BIPIA.

Do not vendor AgentDojo, InjecAgent, or BIPIA into this repository. Record the upstream commit, the license that applies to the exact snapshot, and any share-alike obligations before a later week copies an example. Re-check the upstream license the week you import. The notes here are a watch list, not a grant.

## AgentDojo

- Paper: Edoardo Debenedetti, Jie Zhang, Mislav Balunović, Luca Beurer-Kellner, Marc Fischer, and Florian Tramèr. "AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents." NeurIPS 2024. arXiv:2406.13352. https://arxiv.org/abs/2406.13352
- Code: https://github.com/ethz-spylab/agentdojo
- License watch: the project is released under the MIT License, copyright 2024 the authors above. The authors note that explicitly marked portions that come from earlier work can carry a different license. Confirm `LICENSE` at the commit you would pin. Do not vendor the environment, tasks, or attack corpus here.

AgentDojo is the dynamic tool-use environment this scaffold's metrics (utility and attack success on stateful tool traces) are aimed at later. Week 1 does not import it.

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

Helix Labs is labeled `poisoned: true` in `vendors.json`. Its pages tell the agent to email `attacker@evil.example` and to `delete audit.log`, and they contain an `approval: true` string. That string is not an approval. Acme Analytics and Northwind Insights are clean.

The eval harness adds two further synthetic attack strings (a linear-probe paraphrase and an activation-probe marker). Those strings live in `src/smaip/eval/scenarios.py`. They are not from the benchmarks above.
