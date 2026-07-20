---
name: promptops-evaluate
description: Run a baseline or candidate evaluation for a PromptOps change. Use when the user wants to score a prompt against eval samples.
---

# promptops-evaluate

Evaluate a prompt version against a set of samples.

## When to use

- User says "run eval", "evaluate prompt", "score samples"
- Required before diff/gate and after any patch

## Steps

1. Identify `change_id` and `role`: `baseline` or `candidate`.
2. Identify the samples file (JSON or YAML list of `EvalSample`).
3. Run:

```bash
promptops --workspace <workspace> evaluate --change <change_id> --samples <samples_file> --role <role>
```

4. Report `eval_run_id`, pass rate, and failed sample IDs.

## Example

```bash
promptops --workspace ./ops evaluate --change ch-xxx --samples samples.json --role baseline
```

## Sample file format

```json
[
  {"id": "s1", "input": "Where is my order?", "assertions": ["asks for order number"]},
  {"id": "s2", "input": "Refund", "assertions": ["policy", "empathy"]}
]
```
