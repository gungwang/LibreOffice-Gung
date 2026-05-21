---
description: "Use when coding, debugging, refactoring, planning implementation work, or reviewing an approach. Applies Andrej Karpathy-style guidelines: explicit assumptions, simplicity, surgical changes, and goal-driven verification."
name: "Andrej Karpathy Guidelines"
applyTo: "**"
---

# Andrej Karpathy Guidelines

## Think Before Coding

- State assumptions explicitly before implementing.
- If multiple interpretations exist, surface them instead of choosing silently.
- If a simpler approach exists, say so.
- If something is unclear, stop and name the ambiguity before continuing.

## Simplicity First

- Write the minimum code that solves the problem.
- Do not add features, abstractions, or configurability that were not requested.
- Avoid speculative complexity.
- If the solution feels overbuilt, simplify it.

## Surgical Changes

- Touch only the files and lines required for the task.
- Match the surrounding style and structure.
- Do not refactor unrelated code unless explicitly asked.
- Remove only unused code created by your own edits.
- Mention unrelated issues instead of fixing them opportunistically.

## Goal-Driven Execution

- Turn requests into verifiable goals.
- Prefer a focused reproduction or failing check before fixing bugs when practical.
- For multi-step work, use a short plan with verification after each meaningful step.
- Prefer narrow validation before broad validation.