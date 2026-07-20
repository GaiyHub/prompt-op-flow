---
name: promptops-interactive-tuning
description: Run an interactive feedback-optimize-eval loop to iteratively improve a prompt. Use when the user wants to tune a prompt through multiple rounds of human feedback and automatic optimization.
---

# promptops-interactive-tuning

Iteratively improve a prompt using human feedback and the optimizer.

## When to use

- User says "tune prompt", "iterative tuning", "interactive tuning", "feedback loop"
- User wants to refine a prompt over multiple rounds

## Steps

1. Ensure the change exists and has a baseline eval:

```bash
promptops --workspace <workspace> status --change <change_id>
```

2. If baseline eval is missing, run it:

```bash
promptops --workspace <workspace> evaluate --change <change_id> --samples <samples_file> --role baseline
```

3. Loop until the user is satisfied:
   a. Collect human feedback via `feedback` command or ask the user.
   b. Run optimizer:

```bash
promptops --workspace <workspace> optimize --change <change_id> --section systemPrompt --impl <rule-based|qoder-cli>
```

   c. Run candidate eval:

```bash
promptops --workspace <workspace> evaluate --change <change_id> --samples <samples_file> --role candidate
```

   d. Run diff and gate:

```bash
promptops --workspace <workspace> diff --change <change_id>
promptops --workspace <workspace> gate --change <change_id>
```

   e. Show results and ask whether to continue tuning, approve, or reject.

4. If the user approves, proceed to review and publish.

## Stopping conditions

- Gate passes and user confirms
- User explicitly says "stop", "publish", or "approve"
- User rejects the change
