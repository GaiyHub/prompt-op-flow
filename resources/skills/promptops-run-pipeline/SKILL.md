---
name: promptops-run-pipeline
description: Run the full PromptOps release pipeline for a change. Use when the user wants to execute connect, eval, patch, diff, gate, review, and publish in one flow.
---

# promptops-run-pipeline

Execute the complete PromptOps pipeline for a given change.

## When to use

- User says "run pipeline", "full pipeline", "release prompt", "deploy change"
- User wants to automate the whole flow from connect to publish

## Steps

1. Identify the `change_id`. If not provided, list recent changes and ask the user.
2. Check current status:

```bash
promptops --workspace <workspace> status --change <change_id>
```

3. Execute each pending step in order:
   - `connect` if change does not exist
   - `evaluate` baseline if not done
   - Apply patches or run `optimize` if needed
   - `evaluate` candidate if not done
   - `diff`
   - `gate`
   - `review --decision approve` if gate passes
   - `publish`
4. After each step, verify the result. Stop and ask the user if a step fails or requires human confirmation.
5. Report the final `publish` result including `productionVersionId`.

## Example

```bash
promptops --workspace ./ops status --change ch-xxx
promptops --workspace ./ops evaluate --change ch-xxx --samples samples.json --role baseline
promptops --workspace ./ops optimize --change ch-xxx
promptops --workspace ./ops evaluate --change ch-xxx --samples samples.json --role candidate
promptops --workspace ./ops diff --change ch-xxx
promptops --workspace ./ops gate --change ch-xxx
promptops --workspace ./ops review --change ch-xxx --decision approve --reviewer alice
promptops --workspace ./ops publish --change ch-xxx --publisher alice
```
