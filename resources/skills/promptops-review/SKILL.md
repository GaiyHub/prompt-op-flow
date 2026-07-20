---
name: promptops-review
description: Submit a human review decision for a PromptOps change. Use when the user wants to approve, reject, or request changes on a gated change.
---

# promptops-review

Submit a review decision for a change.

## When to use

- User says "approve", "reject", "request changes", "review change"
- After gate has run

## Steps

1. Identify `change_id`, decision type, and reviewer identity.
2. Optionally collect comments or waiver reasons.
3. Run:

```bash
promptops --workspace <workspace> review \
  --change <change_id> \
  --decision <approve|approve_with_waiver|request_changes|reject> \
  --reviewer <name> \
  [--comment "<comment>"] \
  [--waiver-reason "<reason>"]
```

4. Report the new change status.

## Example

```bash
promptops --workspace ./ops review --change ch-xxx --decision approve --reviewer alice
```
