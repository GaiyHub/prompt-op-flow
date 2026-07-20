---
name: promptops-connect
description: Connect a remote agent profile into PromptOps to start a new change. Use when the user wants to onboard an agent, create a new prompt change, or begin the PromptOps pipeline.
---

# promptops-connect

Start a new PromptOps change by connecting a remote agent profile.

## When to use

- User says "connect agent", "onboard agent", "start a change", "create a change"
- User mentions a platform + agent ID, e.g., "mock:support-agent"
- Beginning of any PromptOps workflow

## Steps

1. Determine the workspace root. Default to `./promptops-workspace` if not specified.
2. Determine platform and agent ID from user input (format `platform:agent-id`).
3. Determine the reason for the change.
4. Run the connect command:

```bash
promptops --workspace <workspace> connect --platform <platform> --agent <agent_id> --reason "<reason>"
```

5. Capture and report the returned `change_id` and `baseline_version_id`.

## Example

```bash
promptops --workspace ./ops connect --platform mock --agent support-agent --reason "add order number check"
```

Output:

```text
change_id: ch-xxx
baseline_version_id: apv-xxx
```
