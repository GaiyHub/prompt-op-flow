---
name: promptops-list-changes
description: List all PromptOps changes in a workspace. Use when the user wants to see existing changes or find a change ID.
---

# promptops-list-changes

List changes in the workspace.

## When to use

- User says "list changes", "show changes", "all changes", "find change"
- When `change_id` is not provided and needs to be selected

## Steps

1. Run:

```bash
promptops --workspace <workspace> list-changes
```

2. Present the list with change ID, agent, status, and created time.
3. If the user needs to select one, ask for the ID.

## Example

```bash
promptops --workspace ./ops list-changes
```
