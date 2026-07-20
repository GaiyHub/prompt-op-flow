---
name: promptops-gate
description: Run gate checks for a PromptOps change. Use when the user wants to validate whether a candidate prompt meets release criteria.
---

# promptops-gate

Run release gate checks for a change.

## When to use

- User says "run gate", "gate check", "validate change", "release criteria"
- After candidate eval and diff

## Steps

1. Identify `change_id` and stage (default `candidate`).
2. Run:

```bash
promptops --workspace <workspace> gate --change <change_id> --stage <stage>
```

3. Report `gate_report_id`, outcome (`passed`, `needs_review`, `blocked`), and any issues.
4. If blocked, show issues and ask whether to request changes, reject, or override with waiver.

## Example

```bash
promptops --workspace ./ops gate --change ch-xxx --stage candidate
```
