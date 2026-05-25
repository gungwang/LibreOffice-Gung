# LibreOffice AI Agent Implementation Scaffold Proposal

Simplified Chinese version: [libreoffice-ai-agent-repo-scaffold.zh-CN.md](./libreoffice-ai-agent-repo-scaffold.zh-CN.md)
Detailed MVP design specification: [libreoffice-ai-agent-mvp-design-spec.md](./libreoffice-ai-agent-mvp-design-spec.md)

> Archived MVP reference.
>
> The active operator-mode documents are:
>
> - [LibreOffice AI Operation Layer Architecture](./libreoffice-ai-agent-operation-layer-architecture.md)
> - [LibreOffice AI Operation Layer Design Specification](./libreoffice-ai-agent-operation-layer-design-spec.md)
> - [LibreOffice AI Operation Layer Refactor Plan](./libreoffice-ai-agent-operation-layer-refactor-plan.md)
>
> Use the operator-mode documents for new planning and implementation work.

## Proposed Subproject

- Subproject directory name: `libreoffice-ai-agent`
- Suggested location: `./libreoffice-ai-agent`

This implementation subproject stays in the current top-level repository, remains separate from LibreOffice core under `./core`, and produces two deliverables:

- a LibreOffice extension package (`.oxt`)
- a local sidecar broker process for Windows

## Proposed Top-Level Layout

```text
libreoffice-ai-agent/
  README.md
  LICENSE
  pyproject.toml
  .gitignore
  .editorconfig
  .github/
    workflows/
      ci.yml
  docs/
    architecture.md
    development.md
    provider-config.md
    testing.md
  extension/
    oxt/
      description.xml
      Addons.xcu
      ProtocolHandler.xcu
      Sidebar.xcu
      META-INF/
        manifest.xml
    src/
      loaia/
        __init__.py
        bootstrap.py
        protocol_handler.py
        sidebar_panel.py
        chat_controller.py
        context/
          __init__.py
          writer.py
          calc.py
          impress.py
        actions/
          __init__.py
          base.py
          registry.py
          writer.py
          calc.py
          impress.py
          app.py
        history/
          __init__.py
          store.py
          keys.py
        broker/
          __init__.py
          client.py
          transport.py
        ui/
          panel.ui
          icons/
    tests/
      unit/
      integration/
  sidecar/
    src/
      loaia_sidecar/
        __init__.py
        main.py
        server.py
        transport/
          __init__.py
          named_pipe.py
        providers/
          __init__.py
          base.py
          openai_compatible.py
          anthropic.py
          gemini.py
          openrouter.py
        planner/
          __init__.py
          router.py
          policy.py
          prompts.py
        models/
          __init__.py
          catalog.py
          capabilities.py
        config/
          __init__.py
          settings.py
          secrets.py
        logging/
          __init__.py
          audit.py
    tests/
      unit/
      integration/
  shared/
    src/
      loaia_shared/
        __init__.py
        schema/
          __init__.py
          messages.py
          actions.py
          history.py
        types.py
        errors.py
  test-fixtures/
    writer/
    calc/
    impress/
  scripts/
    build_oxt.ps1
    run_sidecar.ps1
    dev_install_oxt.ps1
    package_windows.ps1
```

## Language and Packaging Choices

### Primary Language

- Python for both the extension and the sidecar

### Packaging

- `pyproject.toml` for dependency management
- `.oxt` built from `extension/oxt/`
- optional Windows executable packaging for the sidecar in a later step

### Why this layout

- keeps extension and sidecar separate but versioned together
- allows shared schemas without copy-paste
- supports strong test boundaries

## Key Modules

### `extension/src/loaia/bootstrap.py`

- extension bootstrap entry point
- lazy startup for panel and broker client

### `extension/src/loaia/protocol_handler.py`

- registers LibreOffice commands and UI entry points
- opens the AI sidebar deck or panel

### `extension/src/loaia/sidebar_panel.py`

- panel composition and lifecycle
- provider indicator, model picker, consent UI, message list

### `extension/src/loaia/chat_controller.py`

- orchestrates request lifecycle
- gets context, calls broker, renders action cards, executes tools

### `extension/src/loaia/context/*.py`

- one extractor per app
- returns structured selection-only payloads

### `extension/src/loaia/actions/registry.py`

- central action registry and validator
- maps action ids to implementation functions and policy classes

### `sidecar/src/loaia_sidecar/server.py`

- sidecar request dispatcher
- owns session state for active requests and streaming

### `sidecar/src/loaia_sidecar/providers/*.py`

- one adapter per provider family
- unified request and streaming interface

### `sidecar/src/loaia_sidecar/planner/router.py`

- selects direct answer vs tool proposal
- chooses model based on provider, cost, and capability settings

### `shared/src/loaia_shared/schema/messages.py`

- typed message envelopes exchanged over the named pipe

## Initial Message Contract

The first version should define a small stable protocol.

Extension to sidecar:

- `HandshakeRequest`
- `ChatRequest`
- `CancelRequest`
- `ProviderListRequest`
- `ModelListRequest`

Sidecar to extension:

- `HandshakeResponse`
- `StreamChunk`
- `ToolProposal`
- `DirectAnswer`
- `ErrorResponse`

Tool result loop:

- `ToolExecutionResult`
- `ApprovalDecision`

## Suggested Phase 0 Backlog

1. Create repository skeleton.
2. Define shared message schema.
3. Implement named pipe handshake.
4. Implement minimal sidecar with a mock provider.
5. Build a LibreOffice command entry point that opens a placeholder panel.
6. Implement Writer selection extraction.
7. Implement two actions:
   - `Writer.GetSelection`
   - `Writer.ToggleBold`
8. Add a fake planner that returns one read answer and one formatting action.
9. Confirm formatting actions auto-apply immediately.
10. Confirm content edits still require preview plumbing even if the edit action itself is stubbed.

## Suggested Phase 1 Backlog

1. Provider settings UI.
2. OpenAI-compatible provider adapter.
3. One remote provider adapter.
4. Writer content rewrite action with preview.
5. Per-document history store.
6. Audit log.
7. Undo grouping.
8. Initial integration tests against a local LibreOffice instance.

## Testing Strategy

### Unit tests

- action validation
- schema serialization
- provider adapters with mocked HTTP
- policy logic

### Integration tests

- named pipe handshake
- extension to broker request flow
- history store behavior

### End-to-end tests

- Writer selection summarize
- Writer rewrite with preview and apply
- Writer formatting auto-apply
- Calc selected range explanation
- Impress selected text rewrite

### Test fixture policy

- use local document fixtures for deterministic tests
- never require live vendor APIs in CI

## Build and Developer Workflow

### Local development loop

1. Start local sidecar in debug mode.
2. Build or sync extension sources into the `.oxt` package.
3. Install extension into a local LibreOffice test profile.
4. Launch LibreOffice with that profile.
5. Exercise Writer-first scenarios.

### Scripts to provide early

- `build_oxt.ps1`
- `dev_install_oxt.ps1`
- `run_sidecar.ps1`

## Release Outputs

Phase 1 release assets:

- `libreoffice-ai-agent.oxt`
- `loaia-sidecar` Windows package or Python runner bundle
- release notes documenting supported providers, supported apps, and approval behavior

## Suggested Milestones

### Milestone A: Skeleton and transport

- repository created
- extension command entry point exists
- named pipe transport works

### Milestone B: Writer-first loop

- panel opens
- Writer selection is read
- direct answer works
- safe formatting auto-apply works
- rewrite preview works

### Milestone C: History and settings

- provider settings persisted
- per-document history works
- audit log works

### Milestone D: Calc support

- range extraction
- formula explanation and insertion
- chart generation from selection

### Milestone E: Impress support

- selected text extraction
- slide generation from outline
- layout application

## Scope Guardrails

The repository should explicitly defer the following until after the MVP is stable:

- macro generation
- macro execution
- arbitrary filesystem tools
- arbitrary shell execution
- full-document autonomous rewrites
- broad unrestricted UNO command dispatch

## Recommended First Working Demo

The first public demo should show:

1. Open AI sidebar in Writer.
2. Connect to a local OpenAI-compatible model.
3. Summarize the selected paragraph.
4. Rewrite the selected paragraph with preview.
5. Apply bold formatting immediately through a safe formatting action.
6. Show that conversation history comes back when the same document is reopened from the same LibreOffice profile.

That demo is the right quality bar before expanding further.