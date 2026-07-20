---
name: promptops-fixture-demo
description: Seed demo fixtures into a PromptOps workspace for testing and demonstration. Use when the user wants to quickly set up sample agents and data.
---

# promptops-fixture-demo

Seed demo data into a PromptOps workspace.

## When to use

- User says "demo fixtures", "seed data", "create demo", "sample agent"
- When setting up a workspace for testing or demonstration

## Steps

1. Identify the workspace root. Default to `./promptops-workspace`.
2. Optionally specify agent name (default `support-agent`).
3. Run:

```bash
promptops --workspace <workspace> fixture-demo [--agent <agent_name>]
```

4. Confirm the fixture was created:
   - Agent profile YAML exists in workspace
   - Can be connected immediately with `promptops connect`

## Example

```bash
promptops --workspace ./ops fixture-demo --agent support-agent
```
