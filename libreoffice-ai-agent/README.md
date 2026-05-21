# LibreOffice AI Agent

Simplified Chinese version: [README.zh-CN.md](./README.zh-CN.md)

This directory contains the AI extension and local sidecar project for LibreOffice.

Current goals:

- ship a Windows-first LibreOffice AI sidebar experience
- keep model-provider logic outside LibreOffice core
- support Writer, Calc, and Impress through a typed action layer
- keep selection-only context as the default privacy boundary

Main areas:

- `extension/` LibreOffice extension code and OXT packaging assets
- `sidecar/` local broker process for provider access, planning, and streaming
- `shared/` shared message schemas and common types
- `docs/` project-local documentation for implementation and onboarding
- `scripts/` development and packaging scripts

Canonical planning documents currently live in the parent repository docs folder:

- [Project Architecture](../docs/libreoffice-ai-agent-architecture.md)
- [Project Repo Scaffold](../docs/libreoffice-ai-agent-repo-scaffold.md)
- [MVP Design Specification](../docs/libreoffice-ai-agent-mvp-design-spec.md)

Status:

- this is an initial scaffold
- code is mostly placeholder structure and contracts
- implementation should begin with transport, sidebar shell UI, and the first Writer actions
