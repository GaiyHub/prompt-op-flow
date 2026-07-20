---
name: promptops-show-change
description: Show detailed information about a specific PromptOps change. Use when the user wants to inspect a change, its patches, evals, and evidence.
---

# promptops-show-change

Show detailed information about a change.

## When to use

- User says "show change", "inspect change", "change details", "view change"
- When detailed evidence is needed

## Steps

1. Identify `change_id`.
2. Run:

```bash
promptops --workspace <workspace> show-change --change <change_id>
```

3. Summarize:
   - Change metadata
   - Baseline and candidate profile refs
   - Eval runs
   - Patches
   - Diff / gate / review / publish results

## Example

```bash
promptops --workspace ./ops show-change --change ch-xxx
```
