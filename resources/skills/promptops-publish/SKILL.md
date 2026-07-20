---
name: promptops-publish
description: Publish an approved PromptOps change to production. Use when the user wants to release a candidate prompt after gate and review.
---

# promptops-publish

Publish an approved change to the target platform.

## When to use

- User says "publish", "release", "deploy", "push to production"
- After review decision is `approved` or `approved_with_waiver`

## Steps

1. Identify `change_id` and publisher identity.
2. Verify the change is approved and all required evidence exists.
3. Run:

```bash
promptops --workspace <workspace> publish --change <change_id> --publisher <name>
```

4. Report `productionVersionId`, published profile hash, and any warnings.

## Example

```bash
promptops --workspace ./ops publish --change ch-xxx --publisher alice
```
