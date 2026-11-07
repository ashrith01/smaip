# SMAIP glossary

- **Authorized task:** What the trusted user asked the agent to do, including
  source scope, permitted action, and recipient.
- **Lower-trust content:** Text returned from a page, email, or tool. The agent
  may use it as evidence but cannot treat it as a new user command or approval.
- **Prompt injection:** An instruction in lower-trust content that tries to
  redirect the agent beyond the authorized task. Classification depends on
  the task and the document's role, not merely suspicious words.
- **Task intent:** The server's structured record of allowed sources, fields,
  recipient, and review requirement.
- **Evidence claim:** A proposed field and value tied to an authorized source
  and exact line. Validation checks correspondence to the source, not whether
  the source's real-world statement is true.
- **Sandbox effect:** A simulated send or file change inside the evaluator. It
  is not a real email or production side effect.
- **Review checkpoint:** A saved exact action and digest that the authorized
  owner can approve once. Approval rechecks its source and action bindings.
- **Probe:** A small classifier trained on features from a frozen language
  model. The current V4 probe scores archived documents but is not serving.
- **AUROC:** A ranking measure: the chance that a randomly selected labeled
  attack scores above a randomly selected labeled benign example, with ties
  counted halfway. It does not specify a decision cutoff or error rate.
- **Threshold:** A score cutoff used to flag an example. V4's saved model has
  no operating threshold; the LLMail cutoff report is a diagnostic only.
- **Source label:** A label inherited from an upstream dataset. It is distinct
  from an AV-reviewed or accepted label for SMAIP's task-relative definition.
- **Grouped evaluation:** Keeping related examples, such as two versions of
  one task or submissions from one attack lineage, together to reduce leakage.
- **Attack success rate (ASR):** The fraction of attack episodes with an
  observed unauthorized effect. A model's statement that it acted is not an
  observed effect.
- **False-positive rate (FPR):** The fraction of benign examples flagged at
  a specified threshold and unit of evaluation. Zero observed flags on a
  small or correlated sample is not a population guarantee.
