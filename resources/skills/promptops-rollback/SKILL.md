---
name: promptops-rollback
description: Roll back a published PromptOps change to a previous version. Use when the user wants to revert a prompt release.
---

# promptops-rollback

Roll back a published profile to a previous version.

## When to use

- User says "rollback", "revert", "undo release", "go back to previous version"
- After a bad publish

## Steps

1. Identify `change_id` or `platform_agent_id`.
2. Determine the target version (previous baseline or a specific version ID).
3. Run:

```bash
promptops --workspace <workspace> rollback --change <change_id> --to <version_id>
```

4. Confirm the rollback succeeded and report the new production version.

## Example

```bash
promptops --workspace ./ops rollback --change ch-xxx --to apv-previous
```

## Note

Rollback support depends on the target platform adapter. The mock adapter supports it; HTTP/Shenji adapters would need platform-specific rollback logic.
