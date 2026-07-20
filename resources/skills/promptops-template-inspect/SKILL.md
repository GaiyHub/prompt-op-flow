---
name: promptops-template-inspect
description: Inspect built-in and custom pipeline templates for PromptOps. Use when the user wants to see available templates, their steps, and bindings.
---

# promptops-template-inspect

Inspect available pipeline templates.

## When to use

- User says "show templates", "inspect template", "pipeline templates", "template steps"
- When choosing or debugging a template

## Steps

1. Run:

```bash
promptops --workspace <workspace> template-inspect --id <template_id>
```

2. If no template ID is provided, list built-in templates:
   - `interactive-release`
   - `ci-regression`
3. Summarize:
   - Template ID and version
   - Step list and types
   - Required evidence
   - Human confirmation points

## Example

```bash
promptops --workspace ./ops template-inspect --id interactive-release
```
