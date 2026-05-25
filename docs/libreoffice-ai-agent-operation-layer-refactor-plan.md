# LibreOffice AI Operation Layer Refactor Plan and Repo Scaffold

Simplified Chinese version: [libreoffice-ai-agent-operation-layer-refactor-plan.zh-CN.md](./libreoffice-ai-agent-operation-layer-refactor-plan.zh-CN.md)
Related architecture: [libreoffice-ai-agent-operation-layer-architecture.md](./libreoffice-ai-agent-operation-layer-architecture.md)
Related design specification: [libreoffice-ai-agent-operation-layer-design-spec.md](./libreoffice-ai-agent-operation-layer-design-spec.md)

## Summary

This plan reorganizes `./libreoffice-ai-agent` around a capability catalog as the single source of truth.

The immediate objective is not a surface rewrite. It is a control-model rewrite: remove duplicated registries, replace keyword-driven planning with capability retrieval, route execution through a policy-aware generic runtime, and make observation a required part of the loop.

## Planning Assumptions

- Keep the extension plus sidecar split.
- Keep Windows named pipes unless transport evidence forces a change later.
- Keep the current subproject location inside the main LibreOffice repository.
- Migrate existing Writer, Calc, and Impress flows first so parity does not regress while the new runtime is introduced.
- Treat the current MVP docs and code as migration input, not as the final architecture.

## Target Repository Layout

```text
libreoffice-ai-agent/
  README.md
  pyproject.toml
  docs/
    architecture.md
    development.md
    provider-config.md
    testing.md
  extension/
    src/
      loaia/
        bootstrap.py
        protocol_handler.py
        chat_controller.py
        sidebar_panel.py
        sidebar_actions.py
        snapshot/
          app.py
          writer.py
          calc.py
          impress.py
          draw.py
          math.py
          base.py
        execution/
          engine.py
          preflight.py
          observe.py
          approval.py
          undo.py
          bindings/
            dispatch.py
            routines.py
          generated/
            capability_registry.py
            safety_matrix.py
            binding_manifest.py
        history/
        broker/
        ui/
  sidecar/
    src/
      loaia_sidecar/
        main.py
        server.py
        orchestrator/
          engine.py
          session.py
          evaluator.py
        planner/
          retriever.py
          composer.py
          replan.py
          prompt_builder.py
          generated/
            capability_index.json
        providers/
        config/
        logging/
  shared/
    src/
      loaia_shared/
        schema/
        capabilities/
          catalog/
            app.yaml
            writer.yaml
            calc.yaml
            impress.yaml
            draw.yaml
            math.yaml
            base.yaml
          compiler.py
          manifest.py
          generated/
            descriptor_hashes.json
            docs_tables.json
  scripts/
    generate_capability_artifacts.py
    validate_capability_catalog.py
    build_capability_index.py
    verify_operator_flow.ps1
```

The current directories stay recognizable. The refactor adds a stable capability layer and splits planner and execution responsibilities more cleanly.

## Workstream Overview

| Workstream | Current pain | Target result |
|---|---|---|
| shared capability model | duplicated action, safety, and docs data | one catalog and generated artifacts |
| extension execution runtime | registry and safety logic drift | generated registry, generic executor, one preflight path |
| extension snapshot and observation | context is narrow and post-checks are inconsistent | reusable snapshot and probe modules |
| sidecar planning | keyword heuristics and handwritten routing | retrieval, composition, evaluation, replanning |
| provider integration | providers see an implicit tool surface | providers see bounded generated capability summaries |
| tests and docs | drift is discovered late | generated docs tables and CI drift checks |
| app coverage packs | each app expands differently | one pack model for Writer, Calc, Impress, Draw, Math, Base, and app-global capabilities |

## Module-by-Module Plan

### 1. Shared capability model

Current files to absorb or extend:

- `shared/src/loaia_shared/schema/actions.py`
- `shared/src/loaia_shared/types.py`
- `shared/src/loaia_shared/errors.py`

Target modules:

- `shared/src/loaia_shared/capabilities/catalog/`
- `shared/src/loaia_shared/capabilities/compiler.py`
- `shared/src/loaia_shared/capabilities/manifest.py`

Deliverables:

- descriptor schema and validation
- generated descriptor hashes
- generated docs tables
- generated runtime registry contracts

Done when:

- every current capability id exists in the catalog
- no runtime module defines a capability id that is absent from the catalog

### 2. Extension execution runtime

Current files to migrate:

- `extension/src/loaia/actions/registry.py`
- `extension/src/loaia/actions/executor.py`
- `extension/src/loaia/sidebar_actions.py`
- `extension/src/loaia/undo.py`

Target modules:

- `extension/src/loaia/execution/engine.py`
- `extension/src/loaia/execution/preflight.py`
- `extension/src/loaia/execution/observe.py`
- `extension/src/loaia/execution/bindings/`
- `extension/src/loaia/execution/generated/`

Deliverables:

- one preflight path for schema, policy, and scope validation
- one generic binding runtime for `uno-dispatch`, `uno-routine`, and `document-api`
- `App.ExecuteUnoCommand` routed through the same generated manifest as all other capabilities
- undo grouping and audit recording integrated into step execution

Done when:

- the extension no longer maintains a handwritten safety whitelist outside generated outputs
- `App.ExecuteUnoCommand` is exercised by automated tests and live verification

### 3. Snapshot and observation layer

Current files to migrate:

- `extension/src/loaia/context/`
- parts of `extension/src/loaia/chat_controller.py`

Target modules:

- `extension/src/loaia/snapshot/`
- `extension/src/loaia/execution/observe.py`

Deliverables:

- context snapshots for each app pack
- reusable precondition and postcondition probes
- observation summaries that the sidecar can replan from

Done when:

- every mutating capability has at least one postcondition probe
- planner continuation depends on observation output, not raw exception text alone

### 4. Sidecar orchestrator

Current files to split:

- `sidecar/src/loaia_sidecar/server.py`
- parts of `sidecar/src/loaia_sidecar/main.py`

Target modules:

- `sidecar/src/loaia_sidecar/orchestrator/engine.py`
- `sidecar/src/loaia_sidecar/orchestrator/session.py`
- `sidecar/src/loaia_sidecar/orchestrator/evaluator.py`

Deliverables:

- session state machine
- step-by-step orchestration
- evaluation of observation results
- bounded plan revision behavior

Done when:

- the transport server is thin and orchestration logic no longer lives in one large server module

### 5. Sidecar planning and retrieval

Current files to replace or reduce:

- `sidecar/src/loaia_sidecar/planner/policy.py`
- `sidecar/src/loaia_sidecar/planner/prompts.py`
- heuristic planning logic currently embedded in `sidecar/src/loaia_sidecar/server.py`

Target modules:

- `sidecar/src/loaia_sidecar/planner/retriever.py`
- `sidecar/src/loaia_sidecar/planner/composer.py`
- `sidecar/src/loaia_sidecar/planner/replan.py`
- `sidecar/src/loaia_sidecar/planner/prompt_builder.py`
- generated capability index under `planner/generated/`

Deliverables:

- capability retrieval index built from catalog data
- planner prompts generated from retrieved descriptors
- no keyword tables in the main control path
- plan revisions based on observation evidence

Done when:

- planner tests fail if a capability id is invented or if routing depends on handwritten keyword lists

### 6. Chat session, approval, and history

Current files to adapt:

- `extension/src/loaia/chat_controller.py`
- `extension/src/loaia/document_session.py`
- `extension/src/loaia/history/`
- `extension/src/loaia/session_store.py`
- `extension/src/loaia/audit.py`

Target result:

- chat controller becomes a session orchestrator for planning and step execution
- approval decisions attach to plan steps, not to ad hoc UI branches
- history persists plans, observations, approvals, and final outcomes

Done when:

- a resumed session can explain the last plan, the last executed step, and the last observation result

### 7. App coverage packs

Current state:

- Writer, Calc, and Impress exist as partial typed action slices
- Draw, Math, Base, and broader app-global coverage are missing or thin

Target packs:

- `app`
- `writer`
- `calc`
- `impress`
- `draw`
- `math`
- `base`

Deliverables per pack:

- descriptors
- snapshot probes
- postcondition probes
- binding tests
- live smoke coverage for representative operations

Done when:

- new pack support means adding catalog entries and probes, not a planner rewrite

### 8. Docs, scripts, and CI

Current assets to evolve:

- current docs under `../docs/`
- current verification scripts under `scripts/`

Target additions:

- `scripts/generate_capability_artifacts.py`
- `scripts/validate_capability_catalog.py`
- `scripts/build_capability_index.py`
- `scripts/verify_operator_flow.ps1`

Deliverables:

- generation command used in CI
- drift checks that compare catalog outputs to runtime files
- docs tables generated from catalog metadata
- operator smoke tests for plan -> execute -> observe

Done when:

- CI fails on catalog drift before runtime behavior diverges

## Phase Plan

### Phase 0. Freeze the current surface

- inventory every current action id, whitelist, prompt surface, and protocol command
- mark manual registries as migration targets
- stop expanding heuristic planners

### Phase 1. Build the catalog compiler

- define descriptor schema
- port all current Writer, Calc, and Impress action ids into descriptors
- generate manifests and registry outputs

### Phase 2. Migrate execution first

- route extension validation through generated artifacts
- replace duplicated safety checks
- enable `App.ExecuteUnoCommand` with catalog-backed dispatch aliases

### Phase 3. Migrate planning second

- build the retrieval index
- move provider prompts to retrieved capability summaries
- delete keyword-driven routing from the main path

### Phase 4. Require observation

- add postcondition probes for all mutating capabilities
- feed observation results back into evaluator and session history

### Phase 5. Expand app packs

- complete Draw, Math, Base, and app-global coverage
- add structural multi-step capabilities

### Phase 6. Remove legacy code paths

- remove stale registries, whitelists, and planner heuristics
- collapse dead compatibility shims once parity and tests are green

## First-Wave Migration Inventory

Port the current user-visible surface before adding new breadth.

### App-global

- session open and resume flows
- `App.ExecuteUnoCommand`
- shared approval and audit behavior

### Writer

- selection read and replace flows
- safe formatting flows
- paragraph and style flows

### Calc
- range read flows
- formula insert flows
- chart creation flows
- number format flows

### Impress

- selected text read and replace flows
- slide creation flows
- layout flows

After parity, start new pack work for Draw, Math, Base, and suite-level commands.

## Definition of Done

The pivot is complete only when all of the following are true.

- the catalog is the only place where capability ids, safety metadata, and bindings are authored
- planner routing no longer depends on handwritten keyword tables
- every mutating step emits an observation report
- `App.ExecuteUnoCommand` is safe, useful, and covered by automated tests
- docs, tests, and runtime registries are generated from the same source
- adding a new operation mostly means adding a descriptor, probes, and tests
