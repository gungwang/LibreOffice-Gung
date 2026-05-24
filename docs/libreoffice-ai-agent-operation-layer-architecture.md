# LibreOffice AI Operation Layer Architecture

Simplified Chinese version: [libreoffice-ai-agent-operation-layer-architecture.zh-CN.md](./libreoffice-ai-agent-operation-layer-architecture.zh-CN.md)
Detailed operator design specification: [libreoffice-ai-agent-operation-layer-design-spec.md](./libreoffice-ai-agent-operation-layer-design-spec.md)
Module-by-module refactor plan: [libreoffice-ai-agent-operation-layer-refactor-plan.md](./libreoffice-ai-agent-operation-layer-refactor-plan.md)

## Summary

This document replaces the earlier MVP-only assistant architecture with an operator-first architecture for LibreOffice.

The core product goal is no longer "safe help for a narrow set of workflows." The core goal is "broad, controllable LibreOffice operation" through a single source of truth capability catalog, a plan -> execute -> observe loop, and a policy boundary that expands coverage without giving the model unchecked access to UNO.

The extension plus local sidecar split stays. The control model changes.

## Product Target

The target system must let an AI agent discover, plan, execute, and verify LibreOffice operations across Writer, Calc, Impress, Draw, Math, Base, and app-level commands, while keeping every command inside an explicit whitelist with typed parameters, preconditions, postconditions, undo grouping, and audit logging.

## Fixed Product Decisions

- Windows remains the first delivery platform.
- The implementation remains in `./libreoffice-ai-agent` before any LibreOffice core merge.
- The extension remains the only component allowed to mutate LibreOffice state.
- The sidecar is responsible for orchestration, planning, retrieval, provider access, and plan revision.
- A shared capability catalog is the only authority for capability metadata, safety class, bindings, planner surface, docs tables, and tests.
- The planner may retrieve capabilities, but it may not invent capability ids or raw UNO commands.
- `App.ExecuteUnoCommand` becomes a supported generic execution primitive, but only for commands that exist in the catalog whitelist.
- Multi-step execution is expected. Every mutating step must produce an observation result before the next step can continue.
- Human approval is driven by policy class and scope, not by hand-maintained special cases in multiple modules.

## Goals

- Make broad LibreOffice operation the core product outcome.
- Expand control coverage by adding catalog entries, not keyword branches.
- Support multi-step plans that adapt to observation results.
- Keep every write operation policy-bound, undoable, and auditable.
- Generate action registries, planner indexes, policy matrices, docs tables, and drift tests from the same source data.
- Preserve provider independence and keep model-specific logic out of LibreOffice.

## Non-Goals

- Raw unrestricted command execution.
- Hard-coded keyword routers as the primary planning surface.
- Duplicate manual registries for actions, safety, docs, and tests.
- Silent wide-scope edits without observation or approval.
- Cross-platform delivery before the operator runtime stabilizes.

## Architecture Principles

1. One source of truth for capabilities, policy, and bindings.
2. Planning starts from capability retrieval, not keyword classification.
3. Execution is valid only when preconditions and postconditions are explicit.
4. Every mutating step must be observable before the next step proceeds.
5. Coverage scales by adding catalog entries and probes, not bespoke control paths.
6. Undo, audit, and approval are first-class runtime concerns.

## System Overview

```text
+-------------------------------+        named pipe        +-------------------------------+
| LibreOffice Extension Host    | <---------------------> | Local Sidecar Orchestrator    |
|                               |                         |                               |
| - UI and approval             |                         | - Capability retrieval        |
| - Context snapshots           |                         | - Plan composition            |
| - Preflight checks            |                         | - Replanning / evaluation     |
| - Step execution              |                         | - Provider adapters           |
| - Postcondition probes        |                         | - Session orchestration       |
| - Undo and audit              |                         | - Streaming model interaction |
+---------------+---------------+                         +---------------+---------------+
                |                                                                 |
                | UNO / document APIs                                              | provider APIs
                v                                                                 v
+-------------------------------+                         +-------------------------------+
| LibreOffice Applications      |                         | Remote or local models        |
| Writer / Calc / Impress       |                         | OpenAI-compatible /           |
| Draw / Math / Base / App      |                         | Anthropic / Gemini /          |
+-------------------------------+                         | OpenRouter / local hosts      |
                ^                                         +-------------------------------+
                |
+-----------------------------------------------------------------------+
| Shared Capability Catalog and Compiler                                |
| - Capability descriptors                                              |
| - Generated runtime registries                                        |
| - Generated planner index                                             |
| - Generated policy matrix                                              |
| - Generated docs tables and drift tests                               |
+-----------------------------------------------------------------------+
```

## Single Source of Truth

The canonical artifact lives under `shared/src/loaia_shared/capabilities/catalog/`.

Every capability descriptor must declare:

- stable capability id
- app scope
- parameter schema
- natural-language examples
- execution binding
- safety class
- preconditions
- observation probes and expected outcomes
- undo label or compensation notes
- audit fields

No separate hand-maintained lists are allowed for the planner prompt, action registry, safe-action whitelist, approval matrix, docs examples, or drift tests.

### Generated Surfaces

| Generated artifact | Consumed by | Purpose |
|---|---|---|
| capability registry | extension | validates capability ids and parameters |
| execution binding map | extension | resolves catalog entries to UNO dispatch, UNO routines, or composite steps |
| policy matrix | extension and sidecar | keeps approval and safety rules identical on both sides |
| retrieval index | sidecar | makes capabilities discoverable and searchable without keyword routers |
| prompt surface | sidecar | exposes only valid capabilities and examples to the model |
| docs tables | docs | keeps architecture and design docs aligned with the catalog |
| drift tests | CI | fails when runtime code diverges from the catalog |

## Capability Catalog Model

A capability is the smallest supported unit of controlled LibreOffice behavior.

Binding kinds:

- `uno-dispatch`: mapped to a whitelisted `.uno:` command
- `uno-routine`: mapped to a typed local executor function
- `document-api`: mapped to a higher-level LibreOffice API routine
- `composite-plan`: expands into a fixed sequence of lower-level capabilities

Each descriptor must be discoverable by both machines and humans. That means the catalog stores structural metadata and language examples together.

### Example Descriptor

```yaml
id: Writer.ApplyParagraphStyle
version: 1
app: writer
binding:
  kind: uno-dispatch
  dispatch_alias: writer.apply_paragraph_style
parameters:
  style_name:
    type: enum
    values: [Heading 1, Heading 2, Heading 3]
intent_tags: [format, style, heading]
examples:
  - "make this a heading"
  - "turn the selected paragraph into heading 2"
safety:
  class: targeted-format
  default_approval: auto
  allowed_scopes: [selection, paragraph]
preconditions:
  - probe: writer.has_text_selection
postconditions:
  - probe: writer.selection_paragraph_style_is
    expect_parameter: style_name
undo:
  label: "AI: Apply paragraph style"
audit:
  category: formatting
```

## Runtime Components

### 1. Shared Capability Catalog and Compiler

Responsibilities:

- own descriptor schemas and validation
- compile generated artifacts for runtime and docs
- provide stable descriptor hashes so the planner and executor refer to the same capability version
- expose generation commands for CI and local development

### 2. LibreOffice Extension Operation Host

Responsibilities:

- capture active document snapshots and selection-scoped context
- validate plan steps against generated registry data
- enforce approvals, scope limits, and preconditions
- execute UNO dispatches or local routines
- run postcondition probes and emit observation reports
- group undo operations and persist audit and session history

### 3. Local Sidecar Orchestration Engine

Responsibilities:

- retrieve candidate capabilities from the generated index
- compose an execution plan from the current goal and snapshot
- ask a provider for reasoning over the retrieved capability set
- evaluate observation reports after each step
- continue, revise, or stop the plan based on evidence

The sidecar may reason about LibreOffice state. It does not mutate LibreOffice directly.

### 4. Provider Adapter Layer

Responsibilities:

- normalize chat, reasoning, and streaming calls across model vendors
- return structured plan output rather than ad hoc tool text
- stay ignorant of UNO details beyond the capability descriptions supplied by the sidecar

### 5. Observation and Storage Layer

Responsibilities:

- persist session history, plans, approvals, and observation reports
- keep append-only audit records for every executed step
- store enough runtime evidence to reproduce failures and drift

## Plan -> Execute -> Observe Loop

1. The extension captures a current snapshot of the active document, selection, and app state.
2. The sidecar retrieves candidate capabilities from the catalog index using app, scope, and intent filters.
3. The planner composes a bounded `ExecutionPlan`. Each step must reference a valid capability id and expected observation.
4. The extension runs preflight validation: descriptor hash, parameter schema, safety policy, scope, and preconditions.
5. The extension executes one step.
6. The extension runs postcondition probes and emits an `ObservationReport`.
7. The sidecar evaluator decides whether to continue, replan, escalate for approval, or fail loudly.
8. The extension records the final step result in history and audit logs.

This loop is the core operator primitive. Blind one-shot execution is no longer the default control model.

## Safety Boundary

Safety is defined per capability, not per ad hoc code path.

| Safety class | Examples | Default behavior | Required checks |
|---|---|---|---|
| `read-only` | explain formula, inspect style, get selection | auto-run | scope validation |
| `targeted-format` | bold, style, alignment | auto-run | precondition + postcondition |
| `targeted-write` | rewrite selection, insert formula | preview or policy-driven approval | precondition + postcondition + undo |
| `structural-write` | create chart, create slide, insert table | explicit approval | precondition + postcondition + audit |
| `destructive-or-wide` | delete content, sort overwrite, replace large ranges | explicit approval with scope summary | precondition + postcondition + user confirmation |

The policy matrix is compiled from the catalog. The extension and sidecar consume the same generated file.

## `App.ExecuteUnoCommand`

`App.ExecuteUnoCommand` moves from a nominal escape hatch to a real generic executor.

Rules:

- the planner never sends an arbitrary command string that is not represented in the catalog
- a call may reference either a catalog capability id or a whitelisted dispatch alias
- arguments are validated against a generated schema before UNO execution
- preconditions and postconditions are required for every mutating dispatch
- the executor returns structured observations, not only success or exception text
- any command without catalog metadata is rejected before execution

This keeps the door open for broad command coverage without falling back to uncontrolled arbitrary execution.

## Coverage Model

Coverage expands through app packs. Each pack contributes descriptors, probes, and tests.

Initial migration order:

1. app-global pack
2. Writer pack
3. Calc pack
4. Impress pack
5. Draw pack
6. Math pack
7. Base pack

The architecture does not assume all packs ship on day one. It does require that every new pack uses the same catalog, policy, and observation contracts.

## Architecture Checkpoints

1. The catalog compiler exists and generates runtime artifacts.
2. Manual registries and safety lists are replaced by generated artifacts.
3. Planner keyword heuristics are removed from the control path.
4. Every mutating step produces an observation report.
5. `App.ExecuteUnoCommand` runs through the same policy and observation boundary as specialized actions.
6. Coverage expansion becomes a catalog migration task, not a planner rewrite task.

This is the architectural bar for the project pivot.
