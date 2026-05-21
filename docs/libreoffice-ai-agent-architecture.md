# LibreOffice AI Agent Architecture

Simplified Chinese version: [libreoffice-ai-agent-architecture.zh-CN.md](./libreoffice-ai-agent-architecture.zh-CN.md)
Detailed MVP design specification: [libreoffice-ai-agent-mvp-design-spec.md](./libreoffice-ai-agent-mvp-design-spec.md)

## Summary

This document defines the target architecture for a Windows-only LibreOffice AI chat and agent system delivered first as an in-repo implementation subproject at `./libreoffice-ai-agent` and integrated into LibreOffice through an extension plus a local sidecar process.

The system goal is to let users invoke common Writer, Calc, and Impress functionality through a chat panel while keeping document changes safe, reversible, privacy-aware, and provider-agnostic.

## Fixed Product Decisions

- Application scope for phase 1: Writer + Calc + Impress
- Delivery path: in-repo `./libreoffice-ai-agent` subproject, kept separate from LibreOffice core under `./core`
- Privacy default: selection-only context sharing
- Credential model: user-provided API keys and local open-source model endpoints
- Local model strategy: any OpenAI-compatible local server
- Platform scope: Windows only
- Phase 1 exclusions: macro generation and macro execution
- Approval policy: safe formatting-only actions apply immediately; broader edits require preview and approval
- History policy: conversation history is stored per document within the current LibreOffice profile

## Goals

- Provide a native-feeling AI chat panel inside LibreOffice
- Support multiple model providers without changing LibreOffice-side code for each provider
- Execute high-confidence office actions through typed tools instead of fragile UI automation
- Keep write operations safe, explicit, and undo-friendly
- Reuse the same agent contract across Writer, Calc, and Impress

## Non-Goals

- Full autonomous control of every LibreOffice feature in phase 1
- Raw click automation over the visible UI
- Macro authoring or execution in phase 1
- Cross-platform support in phase 1
- Direct integration into LibreOffice core before the extension MVP proves product value

## Architectural Principles

1. Keep AI vendor logic outside LibreOffice.
2. Expose typed office capabilities, not arbitrary internal access.
3. Default to minimum document context.
4. Make every non-trivial write operation inspectable and reversible.
5. Optimize for a narrow but robust MVP before broad command coverage.

## High-Level Architecture

```text
+---------------------------+        named pipe        +---------------------------+
| LibreOffice OXT Extension | <---------------------> | Local AI Sidecar Broker   |
|                           |                         |                           |
| - Sidebar chat panel      |                         | - Provider adapters       |
| - Document context read   |                         | - Model selection         |
| - Tool execution          |                         | - Streaming responses     |
| - Consent / preview UI    |                         | - Planning / tool choice  |
| - History binding         |                         | - Policy pre-checks       |
+---------------------------+                         +---------------------------+
           |                                                          |
           | UNO / document APIs                                       |
           v                                                          v
+---------------------------+                         +---------------------------+
| LibreOffice document apps |                         | Remote or local models    |
| Writer / Calc / Impress   |                         | OpenAI-compatible /       |
|                           |                         | Anthropic / Gemini /      |
| - Commands                |                         | OpenRouter / local hosts  |
| - Selection model         |                         |                           |
| - Undo stack              |                         +---------------------------+
| - Sidebar surfaces        |
+---------------------------+
```

## Main Components

### 1. LibreOffice Extension

The extension is responsible for in-process office behavior.

Responsibilities:

- Register a sidebar deck and panel for the AI chat UI
- Show conversation, action previews, provider state, and consent prompts
- Read current document context using UNO and higher-level document APIs
- Execute approved actions through a tool registry
- Apply undo-safe changes
- Persist per-document conversation history in the LibreOffice profile
- Launch and connect to the local sidecar broker

Initial implementation language:

- Python via `pyuno`

Rationale:

- Fastest iteration path for extension behavior
- Good fit for the initial UNO integration and sidecar contract
- Avoids embedding fast-moving AI SDK code in LibreOffice core

### 2. Local AI Sidecar Broker

The sidecar is an external local process started on demand by the extension.

Responsibilities:

- Load provider settings and model catalogs
- Manage API credentials and local endpoint settings
- Normalize provider requests and responses
- Stream model output to the extension
- Translate user intent into tool proposals
- Run policy checks before tool proposals are emitted
- Produce structured plans and action cards instead of free-form automation

The sidecar does not directly edit LibreOffice documents.

### 3. Provider Adapter Layer

The provider layer lives entirely in the sidecar.

Supported adapter classes:

- OpenAI-compatible HTTP adapter
- Anthropic adapter
- Gemini adapter
- OpenRouter adapter

OpenAI-compatible local servers are the preferred local model interface in phase 1.

Examples:

- local LM Studio endpoint
- local vLLM endpoint
- local text-generation web UI endpoint
- local llama.cpp server exposing an OpenAI-compatible API

### 4. Action Registry

The action registry is the core safety boundary.

Each action is:

- Named
- Typed
- Scope-limited
- Parameter-validated
- Mapped to UNO commands, document APIs, or small multi-step office routines

Examples:

- `Writer.GetSelection`
- `Writer.ReplaceSelection`
- `Writer.ApplyParagraphStyle`
- `Writer.ToggleBold`
- `Calc.GetSelectedRange`
- `Calc.InsertFormulaInSelection`
- `Calc.CreateChartFromSelection`
- `Impress.GetSelectedText`
- `Impress.CreateSlideFromOutline`
- `Impress.ApplyLayout`
- `App.ExecuteUnoCommand`

`App.ExecuteUnoCommand` must be backed by a whitelist only. The model never gets arbitrary command execution.

### 5. Context Extractor

The context extractor turns the active office state into a compact structured payload.

Writer context:

- selected text
- paragraph and style metadata
- cursor location summary
- document language and document type

Calc context:

- selected address range
- visible values or formulas for the selected range
- sheet name
- number format metadata

Impress context:

- selected text or objects
- slide index and layout
- notes presence

Phase 1 default:

- only the current selection is sent to the model

Escalation path:

- current paragraph
- current shape or slide section
- current selected range neighborhood
- explicit full-document or full-sheet consent

### 6. Conversation and History Store

Conversation history is stored per document inside the current LibreOffice profile.

Keying model:

- profile id
- canonical document URL
- app type

Stored items:

- user prompts
- model responses
- tool proposals
- approved tool executions
- provider and model metadata
- consent events

History should not store raw API keys.

## Interaction Model

### Chat Surface

The preferred UX is a sidebar panel. The panel header shows:

- selected provider
- selected model
- privacy scope indicator
- connected or disconnected broker state

### Action Semantics

Actions are grouped into four behavior classes.

| Class | Examples | Approval Behavior |
|---|---|---|
| Read-only | summarize selection, explain formula | immediate |
| Safe formatting-only | bold, heading, bullet list style, alignment | immediate |
| Content edits | rewrite paragraph, insert summary, create slide text | preview + approval |
| Destructive or wide-scope | replace large range, sort with overwrite, delete content | preview + explicit confirmation |

### Undo Contract

Every write operation must be grouped so the user can undo the resulting change in a predictable way.

## Data Flow

### Startup

1. User opens LibreOffice.
2. Extension starts lazily when the AI panel is opened.
3. Extension starts the sidecar if not running.
4. Extension and sidecar perform handshake over a named pipe.
5. Extension loads provider settings and document-scoped conversation history.

### Standard Request

1. User submits a prompt in the chat panel.
2. Extension captures selection-only context.
3. Extension sends request envelope to sidecar.
4. Sidecar selects provider and model.
5. Sidecar returns either:
   - a direct read-only answer, or
   - one or more structured tool proposals
6. Extension evaluates proposal class.
7. Extension auto-applies safe formatting-only actions, or shows preview for broader edits.
8. Extension executes approved tools and logs results.
9. Extension updates the conversation thread and persists history.

## Transport

Windows-only phase 1 transport:

- named pipes

Reasons:

- avoids local HTTP listener by default
- fits same-machine sidecar use
- reduces accidental exposure to other processes

## Settings Model

### Extension-side Settings

- enabled apps: Writer, Calc, Impress
- privacy defaults
- auto-apply formatting toggle
- local history retention limit
- logging verbosity

### Sidecar-side Settings

- providers enabled
- provider credentials or local endpoint URLs
- default remote model
- default local model
- request timeout
- token budget and cost controls

Secrets should be stored in Windows Credential Manager or an encrypted profile-scoped store.

## Security and Privacy

- Selection-only context by default
- Full-document context requires explicit user consent
- No macro execution in phase 1
- No arbitrary shell or filesystem tools in phase 1
- No unrestricted UNO command execution
- Audit trail for approvals and executed actions
- Clear provider visibility in the UI before each request

## Command and Capability Sources

The initial action registry should be derived from LibreOffice’s built-in command metadata and document APIs.

Primary sources:

- `GenericCommands.xcu`
- `WriterCommands.xcu`
- `CalcCommands.xcu`
- `DrawImpressCommands.xcu`

These provide labels and command identifiers, but the agent layer must still define curated higher-level actions over them.

## Phase Plan

### Phase 0: Technical Spike

- Prove extension packaging
- Prove sidebar panel registration
- Prove named pipe sidecar handshake
- Prove one Writer read tool and one Writer formatting tool

### Phase 1: Writer MVP

- sidebar chat panel
- provider selection
- local OpenAI-compatible endpoint support
- remote provider support
- selection-only context
- safe formatting auto-apply
- preview-and-approve content edits
- per-document conversation history

### Phase 2: Calc MVP

- selected range extraction
- formula explanation and insertion
- chart creation from selection
- safe formatting and number-format tools

### Phase 3: Impress MVP

- selected text and object extraction
- slide content rewrite
- create slide from outline
- layout actions

### Phase 4: Broader Coverage

- larger whitelisted command registry
- better intent-to-action routing
- richer multi-step workflows across apps

## Main Risks and Mitigations

### Risk: Sidebar extension registration is slower than expected

Mitigation:

- keep the action contract independent from the initial UI host
- temporary fallback to a modeless docked or launcher-based UI if needed

### Risk: Natural-language requests map poorly to command-level actions

Mitigation:

- build a curated high-level action registry first
- map to commands only after the high-level action is chosen

### Risk: Unsafe or surprising edits reduce trust

Mitigation:

- auto-apply only safe formatting-only actions
- preview broader edits
- always support undo

### Risk: Provider churn destabilizes the integration

Mitigation:

- isolate provider code in the sidecar
- keep a stable extension-to-sidecar contract

## Recommended MVP Quality Bar

The first release is successful only if it can do the following reliably:

- connect to one remote provider and one local OpenAI-compatible endpoint
- read current selection in Writer
- summarize and rewrite selected text
- apply safe formatting immediately
- show preview for broader content changes
- persist per-document conversation history
- undo applied changes predictably

If this slice is not robust, expanding into Calc and Impress should be delayed.