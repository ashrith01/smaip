# Paired agent attack pilot 01 — prepared, not run

Four original synthetic clean/injected pairs are defined in
`src/smaip/eval/attack_pilot.py`. Each pair keeps the same authorized numeric
fact, recipient, vendor, and page set; the injected case only appends one
untrusted instruction to a page. The four objectives are two unauthorized
email sends to `.example` addresses and two `audit.log` deletions. All effects
remain in the in-memory evaluation sandbox. No external benchmark text or
live mail credentials are used.

The runner uses the existing `DevelopmentCase`, `CaseLibrary`, and
`score_case` contracts. The score requires actual sandbox sends or file
changes; model prose claiming success does not count. It also measures task
success, including complete page reads and the exact numeric brief. Ground
truth is kept in case metadata after the run, not inserted into the model
prompt. The runner skips injected cases if the no-defense clean cases fail.

The new GPU entrypoint is `scripts/gpu/run_attack_pilot.py`. It requires the
pinned local Qwen revision, CUDA/fp16, and 256-output/2,048-input token
budgets. Its default stage is only the no-defense susceptibility arm:
four clean and four injected episodes. If that arm produces both useful clean
performance and at least one observed attacker objective, `--compare` can
run no-defense, least-privilege, and keyword arms on all eight cases. Every
run needs a fresh output directory. A versioned source bundle and GPU runtime
would be required before execution; neither was launched here.

This suite is a development diagnostic. It is not a fresh final test and it
does not evaluate the V4 feature as an enforcing detector: V4 still has no
threshold and serving is disabled. The earlier four-pair open-agent run had
zero attacker objectives in its no-defense arm, so the first empirical gate
is baseline susceptibility, not a claimed defense win. The completed
25-clean-task pilot remains separate and is not repeated.

Focused local tests verify pair invariants, unchanged numeric facts,
effect-based scoring, the clean-baseline stop, and rejection of CPU execution
at the GPU entrypoint. These scripted checks do not substitute for real-model
episodes.
