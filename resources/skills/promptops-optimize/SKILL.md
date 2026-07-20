---
name: promptops-optimize
description: Optimize a prompt section for a PromptOps change. Use when the user wants to auto-generate a patch from baseline eval failures and feedback.
---

# promptops-optimize

Generate a patch proposal by optimizing a prompt section.

## When to use

- User says "optimize prompt", "auto patch", "improve prompt"
- Baseline eval exists and there are failures or feedback

## Steps

1. Identify `change_id` and target section (default `systemPrompt`).
2. Choose optimizer implementation: `rule-based` (default) or `qoder-cli`.
3. Run:

```bash
promptops --workspace <workspace> optimize --change <change_id> --section <section> --impl <implementation>
```

4. Report `patch_id`, reason, expected improvement, and risks.

## Example

```bash
promptops --workspace ./ops optimize --change ch-xxx --section systemPrompt --impl qoder-cli
```
