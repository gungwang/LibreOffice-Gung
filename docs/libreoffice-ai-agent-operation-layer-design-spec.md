# LibreOffice AI Operation Layer Design Specification

Simplified Chinese version: [libreoffice-ai-agent-operation-layer-design-spec.zh-CN.md](./libreoffice-ai-agent-operation-layer-design-spec.zh-CN.md)
Related architecture: [libreoffice-ai-agent-operation-layer-architecture.md](./libreoffice-ai-agent-operation-layer-architecture.md)
Related refactor plan: [libreoffice-ai-agent-operation-layer-refactor-plan.md](./libreoffice-ai-agent-operation-layer-refactor-plan.md)

## 1. Purpose

This document is the build-ready specification for the operator-first refactor of the LibreOffice AI Agent project.

The previous MVP design optimized for a narrow assistant flow. This specification defines the runtime contracts, module boundaries, safety model, and rollout sequence for a system whose core goal is broad LibreOffice operation through a controlled AI runtime.

## 2. Release Sequence

The pivot ships in three tracks.

### Track A. Operator foundation

- capability catalog and compiler
- generated runtime registries
- plan -> execute -> observe session loop
- generic `App.ExecuteUnoCommand` with whitelist enforcement
- migration of current Writer, Calc, and Impress capabilities into the catalog

### Track B. Coverage expansion

- additional catalog packs for Draw, Math, Base, and app-global operations
- multi-step structural capabilities
- broader observation probes and repair paths

### Track C. Full-suite operator maturity

- suite-wide coverage targets
- richer plan revision behavior
- stronger drift tests, telemetry, and operational tooling

This document specifies Track A in detail and defines the contracts that Tracks B and C must follow.

## 3. Success Criteria

The refactor is successful only if all of the following are true.

1. A capability compiler generates extension registries, planner indexes, policy matrices, docs tables, and drift tests from one catalog.
2. The planner returns an `ExecutionPlan` whose steps all reference catalog capability ids.
3. Every mutating step returns an `ObservationReport` before the next step can continue.
4. `App.ExecuteUnoCommand` can execute any whitelisted `.uno:` command with typed parameters, preconditions, postconditions, and undo grouping.
5. Legacy keyword-routing tables are removed from the main planning path.
6. Existing Writer, Calc, and Impress user-facing flows still work after migration to the new runtime.

## 4. Canonical Artifacts

### 4.1 Capability descriptors

Location:

- `shared/src/loaia_shared/capabilities/catalog/`

Contents:

- app-scoped capability descriptors
- common aliases and dispatch bindings
- safety metadata
- observation probes
- natural-language examples

### 4.2 Shared schemas

Location:

- `shared/src/loaia_shared/schema/`
- `shared/src/loaia_shared/capabilities/`

Contents:

- request and response envelopes
- `ExecutionPlan`
- `PlanStep`
- `ObservationReport`
- descriptor validation schemas

### 4.3 Generated outputs

Location:

- extension generated registry modules
- sidecar generated retrieval index
- generated docs fragments or validation tables
- generated drift tests

### 4.4 Runtime stores

Location:

- current extension state root for history and audit

Contents:

- sessions
- message history
- plan history
- approval decisions
- execution logs
- observation logs

## 5. Session and Transport Contract

The transport remains JSON over Windows named pipes.

### 5.1 Session lifecycle

1. The extension opens or resumes an operation session for the active document.
2. The extension captures a `ContextSnapshot`.
3. The sidecar retrieves candidate capabilities for the active app and goal.
4. The sidecar returns an `ExecutionPlan` or a `DirectAnswer` if no operation is required.
5. The extension validates and executes one plan step at a time.
6. The extension emits an `ObservationReport` after each step.
7. The sidecar either continues, replans, asks for approval, or stops.

### 5.2 Core message types

Extension to sidecar:

- `HandshakeRequest`
- `ChatRequest`
- `CapabilitySearchRequest`
- `StepExecutionResult`
- `ObservationReport`
- `ApprovalDecision`
- `CancelRequest`

Sidecar to extension:

- `HandshakeResponse`
- `ExecutionPlan`
- `DirectAnswer`
- `ApprovalRequest`
- `PlanRevision`
- `ErrorResponse`
- `StreamChunk`

### 5.3 `ExecutionPlan` shape

```json
{
  "type": "ExecutionPlan",
  "sessionId": "sess-123",
  "goal": "Create a chart from the selected range and place it below the table.",
  "steps": [
    {
      "stepId": "step-1",
      "capabilityId": "Calc.CreateChartFromSelection",
      "descriptorHash": "sha256:...",
      "parameters": {
        "chart_type": "column"
      },
      "targetScope": "selection",
      "approvalMode": "explicit",
      "expectedObservation": {
        "probe": "calc.chart_count_delta",
        "comparison": "equals",
        "value": 1
      },
      "onFailure": "replan"
    }
  ]
}
```

### 5.4 `ObservationReport` shape

```json
{
  "type": "ObservationReport",
  "sessionId": "sess-123",
  "stepId": "step-1",
  "outcome": "satisfied",
  "preconditions": [
    {
      "probe": "calc.has_selection",
      "status": "passed"
    }
  ],
  "postconditions": [
    {
      "probe": "calc.chart_count_delta",
      "status": "passed",
      "actual": 1,
      "expected": 1
    }
  ],
  "summary": "A chart was created below the selected range."
}
```

## 6. Capability Catalog Specification

Every descriptor must define the following fields.

- `id`: stable capability id
- `version`: descriptor version
- `app`: app scope such as `writer`, `calc`, `impress`, `draw`, `math`, `base`, or `app`
- `title`: short human-readable name
- `description`: planner-facing description
- `intent_tags`: searchable intent labels
- `examples`: natural-language examples for retrieval and prompting
- `parameters`: typed input schema
- `binding`: `uno-dispatch`, `uno-routine`, `document-api`, or `composite-plan`
- `safety`: class, default approval, allowed scope, and wide-scope thresholds
- `preconditions`: required probes before execution
- `postconditions`: required probes after execution
- `undo`: undo group label or compensation notes
- `audit`: category and logging hints

### 6.1 Binding rules

- `uno-dispatch` binds to a whitelisted dispatch alias or a catalog-owned `.uno:` command.
- `uno-routine` binds to a typed extension executor function.
- `document-api` binds to a higher-level LibreOffice API routine when a raw dispatch is insufficient.
- `composite-plan` expands into a fixed lower-level sequence compiled from catalog data.

### 6.2 Compiler outputs

The compiler must generate:

- descriptor hash manifest
- extension capability registry
- extension safety matrix
- execution binding map
- sidecar retrieval index
- prompt-ready capability summaries
- docs tables and drift tests

The runtime must reject a plan step if the descriptor hash received from the sidecar does not match the locally generated manifest.

## 7. Planning Engine Specification

The sidecar planning engine is split into retrieval, composition, and evaluation.

### 7.1 Retrieval

Inputs:

- app type
- current context snapshot
- user goal
- policy constraints

Retrieval data:

- descriptor title and description
- intent tags
- examples
- app scope
- safety class
- parameter names

Retrieval rules:

- no hand-written keyword router decides the final capability set
- hard filters may narrow by app or policy, but not by a duplicated manual tool list
- retrieval returns a bounded candidate set for the planner, not the entire catalog

### 7.2 Plan composition

Planner rules:

- never invent a capability id
- never invent a raw UNO command
- every step must carry `descriptorHash`
- every mutating step must carry `expectedObservation`
- every step must declare `onFailure`
- the default maximum plan length for one turn is bounded and configurable

### 7.3 Evaluation and replanning

After each `ObservationReport`, the evaluator chooses one of these actions.

- continue with the next step
- revise parameters for the current goal
- request user approval for wider scope
- stop and surface a failure summary

## 8. Execution Engine Specification

The extension execution engine validates and runs one step at a time.

### 8.1 Preflight

The executor must verify:

- descriptor hash matches local manifest
- capability exists in generated registry
- parameters match generated schema
- requested scope is allowed
- approval requirements are satisfied
- precondition probes pass

### 8.2 Step execution

Execution order:

1. open undo group
2. resolve binding
3. execute UNO dispatch or typed routine
4. collect raw execution result
5. run postcondition probes
6. emit `ObservationReport`
7. close undo group and audit result

### 8.3 `App.ExecuteUnoCommand`

`App.ExecuteUnoCommand` is a first-class catalog capability for generic dispatch execution.

Allowed parameter shapes:

- `dispatchAlias` for common catalog-owned commands
- optional typed `arguments`
- optional `targetScope`
- required expected observation metadata

Rules:

- a raw `.uno:` string may be stored in catalog metadata, but user or model input does not bypass the catalog
- every command path must still pass policy, precondition, and postcondition checks
- failures return structured observation mismatches, not opaque true-or-false results

## 9. Observation Engine Specification

The observation engine turns runtime evidence into control feedback.

### 9.1 Snapshot and probes

Probe families include:

- selection probes
- document structure probes
- formatting probes
- object-count probes
- cursor or insertion-point probes
- app-specific probes such as chart count, slide count, or formula text

### 9.2 Observation outcomes

- `satisfied`
- `unchanged`
- `partial`
- `failed`
- `unknown`

`unknown` is allowed only when the probe itself is unavailable. It is not a substitute for missing catalog metadata.

### 9.3 Replanning trigger

The sidecar must receive enough evidence to answer:

- did the step change the intended target
- did it change too much
- should the same step be retried
- should the goal be decomposed differently

## 10. Safety and Approval Model

Safety comes from catalog data plus runtime checks.

| Safety class | Examples | Default approval | Runtime gates |
|---|---|---|---|
| `read-only` | inspect selection, explain formula | auto | scope validation |
| `targeted-format` | style, alignment, bold | auto | precondition + postcondition |
| `targeted-write` | rewrite selection, insert formula | preview or policy-driven approval | precondition + postcondition + undo |
| `structural-write` | create chart, create slide, insert table | explicit approval | precondition + postcondition + audit |
| `destructive-or-wide` | delete objects, overwrite large ranges | explicit approval with scope summary | precondition + postcondition + user confirmation |

Wide-scope thresholds such as affected cell count, paragraph count, or slide count must live in the catalog or policy compiler outputs, not in scattered handwritten conditionals.

## 11. Module Specifications

### 11.1 `shared/src/loaia_shared`

Deliver:

- capability descriptor schemas
- compiler and manifest builder
- shared transport and plan schemas
- generated artifact contracts

### 11.2 `extension/src/loaia`

Deliver:

- snapshot and probe modules
- execution engine with preflight and observation
- generated capability registry consumption
- approval runtime
- audit and history integration

### 11.3 `sidecar/src/loaia_sidecar`

Deliver:

- thin transport server
- retrieval engine
- planner and evaluator
- session orchestrator
- provider adapters that consume generated capability summaries

### 11.4 `scripts/` and tests

Deliver:

- catalog generation command
- drift-check command
- index-build command
- unit tests for descriptor validation, policy compilation, execution preflight, and observation evaluation
- integration and live tests for end-to-end operator sessions

## 12. Rollout Plan

### Phase 0. Inventory and freeze

- enumerate current capability ids
- map current registries, whitelists, and planner lists
- stop adding new hand-maintained capability surfaces

### Phase 1. Catalog compiler

- add descriptor schema and compiler
- generate manifests and registries
- port existing Writer, Calc, and Impress capabilities into the catalog

### Phase 2. Execution migration

- swap extension runtime to generated registry and policy matrix
- route existing actions through the new preflight and observation flow
- enable `App.ExecuteUnoCommand`

### Phase 3. Planning migration

- replace keyword routing with capability retrieval and plan composition
- keep the provider-facing reasoning surface bounded to retrieved capabilities

### Phase 4. Observation-driven loop

- require observation reports after each mutating step
- enable evaluation and replanning

### Phase 5. Coverage expansion

- add Draw, Math, Base, and broader app-global packs
- add structural capabilities and richer probes

## 13. Acceptance Tests

The refactor is not complete until the following checks exist.

- catalog validation tests
- generated-registry drift tests
- planner contract tests that reject invented capability ids
- executor tests for schema, policy, preconditions, and postconditions
- live tests for representative `App.ExecuteUnoCommand` flows
- end-to-end multi-step plan tests with observation-driven continuation or replanning
