---
name: promptops-accept-drift
description: Accept detected drift as the new baseline for a PromptOps change. Use when the remote production profile has changed and the user wants to update the local baseline.
---

# promptops-accept-drift

Accept detected drift as the new baseline.

## When to use

- User says "accept drift", "drift baseline", "remote changed", "sync baseline"
- After drift detection reports that the remote profile differs from baseline

## Steps

1. Identify `change_id`.
2. Confirm the drift with the user before overwriting baseline.
3. Run:

```bash
promptops --workspace <workspace> accept-drift --change <change_id>
```

4. Report the new baseline version ID.

## Example

```bash
promptops --workspace ./ops accept-drift --change ch-xxx
```

## Note

This updates the existing change in place: it creates a new baseline version, updates `change.sourceVersionId`, resets status to `open`, and clears `targetVersionId` so the pipeline can restart from the new baseline.
