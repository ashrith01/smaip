# Independent detector data: source gate

Historical planning record. The [study closure decision](../../adr/0002-close-as-completed-study.md)
supersedes this acquisition plan as an active project commitment.

Checked 2026-11-12. This is a source-screening record for checklist step 9,
not an acquired or accepted evaluation set. No new case text was downloaded,
reviewed, scored, or assigned to a split in this pass.

## Candidate source

The [AgentDojo repository](https://github.com/ethz-spylab/agentdojo) is a
candidate for task-contextual attack cases and corresponding clean task
contexts. Its benchmark is built around agent tasks and attacks, and its
[root license](https://github.com/ethz-spylab/agentdojo/blob/089ed468cf3ed0322acc66b0211f26d9d90dbf60/LICENSE)
is MIT. The repository's `main` branch resolved to commit
`089ed468cf3ed0322acc66b0211f26d9d90dbf60` when checked. Recheck the
licenses of exact files selected, including any embedded third-party
material, before importing. Compatibility with SMAIP's raw-document V4
feature input and task-relative labels has not yet been established.

Do not treat the repo as a final holdout merely because its files have not
been downloaded here. Before opening or scoring its cases, freeze a selection
rule, grouping keys, source/file revision manifest, permitted transformations,
and separate roles for development, threshold calibration, and final test.
Keep related variants of an attack, task, source document, and author in the
same group. Review benign controls and attack labels against the authorized
task; source labels alone are not accepted human truth. Check overlap against
SMAIP fixtures, the previously observed NVIDIA and LLMail material, and any
public expansions of those sources.

## Sources that do not meet the gate as a whole

- The NVIDIA and LLMail rows already scored by SMAIP are development material.
  Their present or future AV reviews do not make them fresh final tests.
- [BIPIA](https://github.com/microsoft/BIPIA#project-data) combines several
  source datasets with different terms, and its Web QA and Summarization data
  require separate source downloads and usage review. It needs a per-component
  license and task-fit decision before use.
- The [e2a prompt-injection family](https://github.com/tokencanopy/e2a-bench/blob/main/dataset/prompt-injection/README.md)
  expands LLMail and AgentDojo payloads into multiple email renderings. Those
  descendants must be linked to their original payload/scenario; rendered
  variants are not independent rows and LLMail-derived examples overlap an
  already observed SMAIP source.

Step 9 remains open. The next action is a prospective, versioned acquisition
protocol, followed by a private source snapshot, license/provenance audit,
human task-relative label review, overlap/grouping audit, and frozen split
manifest before model selection or threshold testing.
