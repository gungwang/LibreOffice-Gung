---
description: "Use when creating or updating Markdown documentation files. Maintain paired English and Simplified Chinese versions for user-facing docs, and keep the Chinese version easy to understand with brief explanations for technical terms."
name: "Bilingual Markdown Docs"
applyTo: "docs/**/*.md,README*.md,**/README*.md"
---

# Bilingual Markdown Documentation

- Maintain both English and Simplified Chinese versions for user-facing Markdown documentation.
- Use a stable naming pattern such as `foo.md` and `foo.zh-CN.md`.
- Keep the structure and section order closely aligned between the two versions.
- Do not make the Chinese version a literal word-for-word translation when that hurts readability.
- Explain technical terms briefly in Chinese, either inline or in a short terminology section.
- When one language version changes, update the paired version in the same task when practical.
- Prefer documentation links between paired files so readers can switch languages easily.
