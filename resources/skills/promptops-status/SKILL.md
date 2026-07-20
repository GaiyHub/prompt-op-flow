---
name: promptops-status
description: Show the current status and execution plan of a PromptOps change. Use when the user wants to know what has been done and what step is next.
---

# promptops-status

Show the status and next steps for a change.

## When to use

- User says "status", "where are we", "what's next", "plan"
- Before deciding the next action

## Steps

1. Identify `change_id`. If not provided, list changes and ask.
2. Run:

```bash
promptops --workspace <workspace> status --change <change_id>
```

3. Summarize:
   - Current status
   - Completed steps
   - Next runnable step
   - Any blockers

## Example

```bash
promptops --workspace ./ops status --change ch-xxx
```
