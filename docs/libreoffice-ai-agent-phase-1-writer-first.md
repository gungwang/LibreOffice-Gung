# LibreOffice AI Agent Phase 1 Writer-First Scope

## Goal

Ship one stable Writer-first path before expanding into Calc or Impress.

Phase 1 is complete when a Windows user can install the extension, open the sidebar, configure a provider and model, preview a Writer rewrite, approve it, recover from common provider or sidecar failures, and reopen LibreOffice without losing sidebar settings or recent conversation context.

## In Scope

- Writer-only document actions for direct answers and ReplaceSelection preview/apply.
- Sidebar settings for provider, model, API-key status, and visible error states.
- Persistent extension-side settings and recent conversation history that survive LibreOffice restarts.
- Provider-backed Writer rewrite proposals with a predictable structured rewrite contract.
- A small release smoke matrix that can be run before packaging or sharing a build.

## Out Of Scope

- Calc or Impress editing workflows.
- Multi-document orchestration, background indexing, or document-wide autonomous edits.
- Streaming UI polish, token accounting, telemetry dashboards, or advanced audit reporting.
- Cross-platform support outside the current Windows-first validation path.

## Shipping Rules

- Writer preview/apply stays approval-gated.
- Provider logic stays in the sidecar.
- The extension may persist only the minimum local state needed for settings and recent history.
- If the sidecar or provider is unavailable, the sidebar must show a clear failure state instead of silently degrading.

## Release Smoke Matrix

| Scenario | What to verify | Expected result |
| --- | --- | --- |
| Install | Build OXT, install into a clean profile, open Writer sidebar | Sidebar opens and settings controls render |
| Direct answer | Submit a question that should not edit the document | Direct answer is shown, no pending proposal is created |
| Preview and apply | Select Writer text, request a rewrite, approve it | Preview appears first, approval updates the selection |
| Provider failure | Run with missing or invalid provider credentials | Sidebar shows a clear provider error state |
| Sidecar failure | Run with the sidecar stopped or pipe unavailable | Sidebar shows a clear transport error state |
| Restart persistence | Save settings, send one request, restart LibreOffice | Provider/model settings and recent activity are restored |

## Deferred Expansion Gate

Do not start Calc or Impress feature work until all smoke-matrix rows pass on the Writer path and the rewrite contract is stable enough that provider-backed proposals behave predictably across repeated runs.