---
name: promptops-diff
description: Generate a semantic diff between baseline and candidate prompts for a PromptOps change. Use when the user wants to compare prompt versions or analyze change risk.
---

# promptops-diff

Generate a semantic diff report for a change.

## When to use

- User says "diff prompts", "semantic diff", "compare versions", "what changed"
- After candidate eval and before gate

## Steps

1. Identify `change_id`.
2. Choose analyzer implementation: `heuristic` (default) or `qoder-cli`.
3. Run:

```bash
promptops --workspace <workspace> diff --change <change_id> --impl <implementation>
```

4. Report `diff_id`, max risk level, and number of findings.

## Example

```bash
promptops --workspace ./ops diff --change ch-xxx --impl heuristic
```
