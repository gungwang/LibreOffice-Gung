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

Useful scripts:

- `scripts/run_sidecar.ps1` starts the local named-pipe sidecar with the project `PYTHONPATH`
- `scripts/cleanup_build_profiles.ps1` prunes stale hand-named LibreOffice verification profiles under `build/` while skipping active profiles and keeping a small recent set via `-KeepNewest`
- `scripts/verify_protocol_actions.ps1` installs the OXT and live-verifies the Writer preview/apply protocol flow; by default it checks deterministic local rewrites, and with `-ExpectChangedText` plus `-Provider`/`-Model` it also validates provider-backed Writer proposals
- `scripts/verify_sidebar_direct_answer.ps1` installs the OXT and live-verifies the open-sidebar plus direct-answer flow without changing the document; with `-ExpectNonScaffoldAnswer` plus `-Provider`/`-Model` it can force a provider-backed direct-answer check through the same runner
- `scripts/verify_sidebar_invalid_selection.ps1` installs the OXT and live-verifies preview-selection error paths; by default it checks the Writer no-selection validation, with `-Scenario unsupported-document` it validates the Calc Writer-only rejection without changing the sheet, and with `-Scenario transport-error` it validates the sidecar-unavailable error path against an isolated missing pipe address

Canonical planning documents currently live in the parent repository docs folder:

- [Project Architecture](../docs/libreoffice-ai-agent-architecture.md)
- [Project Repo Scaffold](../docs/libreoffice-ai-agent-repo-scaffold.md)
- [MVP Design Specification](../docs/libreoffice-ai-agent-mvp-design-spec.md)

Status:

- this has moved from an initial scaffold into a working Windows-first prototype
- the sidebar shell, Writer preview/apply flow, and live LibreOffice verification scripts are in place
- planner/provider execution beyond the scaffold responses is still incomplete
