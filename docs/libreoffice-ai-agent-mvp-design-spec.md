# LibreOffice AI Agent MVP Design Specification

Simplified Chinese version: [libreoffice-ai-agent-mvp-design-spec.zh-CN.md](./libreoffice-ai-agent-mvp-design-spec.zh-CN.md)
Related architecture: [libreoffice-ai-agent-architecture.md](./libreoffice-ai-agent-architecture.md)
Related repo scaffold: [libreoffice-ai-agent-repo-scaffold.md](./libreoffice-ai-agent-repo-scaffold.md)

## 1. Purpose

This document is the build-ready specification for the first working release of the LibreOffice AI Agent project.

It narrows the broader architecture into a concrete MVP that developers can implement with minimal ambiguity.

This specification covers:

- the exact MVP scope
- the runtime components and their boundaries
- the first user-visible flows
- the request and tool proposal contract between the extension and the sidecar
- the initial action registry for Writer, Calc, and Impress
- approval rules, history storage, settings, logging, and acceptance criteria

## 2. MVP Release Target

The MVP release target is:

- Windows only
- shipped as a LibreOffice extension plus a local sidecar process
- supports Writer, Calc, and Impress
- uses selection-only context by default
- supports both remote APIs and local OpenAI-compatible model servers
- stores conversation history per document within the current LibreOffice profile

Implementation priority is still Writer first, but the MVP design must leave clear extension points for Calc and Impress so the project does not need to be redesigned after Writer.

## 3. Fixed Product Decisions

- Safe formatting-only actions apply immediately.
- Broader content edits require preview and explicit approval.
- Macro generation and macro execution are out of scope.
- API keys are user-provided.
- Local model integration uses any OpenAI-compatible local server.
- The sidecar never edits LibreOffice documents directly.
- The extension owns all document changes, user approvals, undo behavior, and history persistence.

## 4. MVP Success Definition

The MVP is successful only if a user can reliably do all of the following:

1. Open an AI sidebar panel inside LibreOffice.
2. Select a provider and a model.
3. Use one remote model or one local OpenAI-compatible model.
4. Ask a question about the current selection.
5. Receive either a direct answer or a structured action proposal.
6. Have safe formatting actions apply immediately.
7. Preview and approve broader edits before they change the document.
8. Undo the resulting document change predictably.
9. Close and reopen the same document in the same LibreOffice profile and recover the conversation history.

## 5. Supported User Scenarios

### Writer scenarios

- Summarize the selected paragraph.
- Rewrite the selected paragraph in a different tone.
- Turn the selected lines into a bulleted list.
- Apply Heading 1, Heading 2, or Heading 3 to the selected paragraph.
- Bold, italicize, or align the selection.

### Calc scenarios

- Explain the formula in the selected cell.
- Suggest and insert a formula into the selected range.
- Apply safe number formatting to the selected range.
- Create a chart from the current selected range.

### Impress scenarios

- Rewrite selected slide text.
- Turn selected bullets into a cleaner outline.
- Create a new slide from a supplied outline.
- Apply a layout change to the current slide.

## 6. User Experience Specification

### Entry points

The MVP must provide at least one stable entry point:

- AI sidebar deck and panel

Optional secondary entry points can be added later:

- menu item
- toolbar button

### Sidebar layout

The panel must contain these regions:

1. Header
- provider selector
- model selector
- privacy scope indicator
- broker connection state

2. Conversation view
- user messages
- model messages
- action cards
- approval cards
- error banners

3. Compose area
- prompt input box
- send button
- cancel button while streaming

4. Optional footer
- history scope summary
- last action status

### Panel states

- disconnected
- ready
- streaming
- approval required
- executing action
- completed
- error

### Interaction flows

#### Read-only answer flow

1. User selects content.
2. User submits a prompt.
3. Extension sends selection-only context to sidecar.
4. Sidecar returns a direct answer.
5. Extension renders the answer and appends it to history.

#### Safe formatting flow

1. User selects content.
2. User asks for a formatting operation.
3. Sidecar returns a safe formatting tool proposal.
4. Extension validates the proposal against the safe formatting whitelist.
5. Extension applies the change immediately.
6. Extension records the tool execution and exposes normal undo behavior.

#### Content edit flow

1. User selects content.
2. User asks for a rewrite or insert action.
3. Sidecar returns a structured tool proposal with preview text.
4. Extension shows a preview card.
5. User approves or rejects.
6. Extension applies the approved change and records it.

#### Context escalation flow

1. User asks for an operation without enough selected context.
2. Sidecar or extension determines more context is needed.
3. Extension asks for explicit permission to read a larger scope.
4. User approves or declines.
5. Extension continues only with approved scope.

## 7. Approval and Safety Policy

The system defines four action classes.

| Action Class | Examples | Auto Apply | Preview | Explicit Confirmation |
|---|---|---|---|---|
| Read-only | summarize selection, explain formula | Yes | No | No |
| Safe formatting-only | bold, heading, bullets, alignment, number format | Yes | No | No |
| Content edit | rewrite paragraph, insert summary, create slide text | No | Yes | Yes |
| Destructive or wide-scope | replace large range, sort overwrite, delete content | No | Yes | Yes |

### Safe formatting-only whitelist for phase 1

Writer:

- `Writer.ToggleBold`
- `Writer.ToggleItalic`
- `Writer.ToggleUnderline`
- `Writer.ApplyHeading1`
- `Writer.ApplyHeading2`
- `Writer.ApplyHeading3`
- `Writer.ApplyBullets`
- `Writer.AlignLeft`
- `Writer.AlignCenter`
- `Writer.AlignRight`

Calc:

- `Calc.ToggleBold`
- `Calc.ToggleItalic`
- `Calc.AlignLeft`
- `Calc.AlignCenter`
- `Calc.AlignRight`
- `Calc.ApplyNumberFormatCurrency`
- `Calc.ApplyNumberFormatPercent`
- `Calc.ApplyNumberFormatDate`

Impress:

- `Impress.ToggleBold`
- `Impress.ToggleItalic`
- `Impress.ApplyBullets`
- `Impress.AlignLeft`
- `Impress.AlignCenter`
- `Impress.AlignRight`

Anything outside this whitelist must not auto-apply in phase 1.

## 8. Runtime Components and Boundaries

### LibreOffice extension

Owns:

- sidebar UI
- document context extraction
- action validation and execution
- approval prompts
- undo grouping
- history persistence
- sidecar process lifecycle from the LibreOffice side

Must not own:

- vendor-specific provider logic
- direct remote API calling in multiple provider formats

### Local sidecar

Owns:

- provider adapters
- model selection
- streaming output
- intent routing
- tool proposal generation
- pre-check policy logic

Must not own:

- direct LibreOffice document mutation
- user approval UI
- document history persistence inside LibreOffice profile

## 9. Transport and Session Lifecycle

### Transport

- Windows named pipe

### Startup sequence

1. User opens the AI panel.
2. Extension checks whether the sidecar is running.
3. If not running, extension launches the sidecar.
4. Extension connects through a named pipe.
5. Extension sends a handshake request.
6. Sidecar returns version, capabilities, and provider availability.

### Request sequence

1. Extension builds a request envelope.
2. Sidecar returns stream chunks and then one final result envelope.
3. Final result is either direct answer, tool proposal list, consent escalation request, or error.

### Cancellation

- User can cancel a running request.
- Extension sends `CancelRequest`.
- Sidecar stops generation if provider supports cancellation, or discards late results otherwise.

## 10. Request and Response Contract

The first protocol version should be JSON over named pipes.

### Core request envelope

```json
{
  "type": "ChatRequest",
  "requestId": "req-123",
  "app": "writer",
  "document": {
    "canonicalUrl": "file:///C:/docs/example.odt",
    "profileId": "default"
  },
  "provider": "openai-compatible-local",
  "model": "qwen2.5-14b-instruct",
  "privacyScope": "selection-only",
  "context": {
    "selection": {
      "mimeType": "text/plain",
      "text": "Selected paragraph text"
    }
  },
  "userMessage": "Rewrite this in a professional tone.",
  "historySummary": []
}
```

### Final result types

- `DirectAnswer`
- `ToolProposal`
- `ConsentRequest`
- `ErrorResponse`

### Tool proposal shape

```json
{
  "type": "ToolProposal",
  "proposalId": "prop-456",
  "toolId": "Writer.ReplaceSelection",
  "safetyClass": "content-edit",
  "requiresApproval": true,
  "preview": {
    "summary": "Replace the selected paragraph with a rewritten version.",
    "before": "Original text",
    "after": "Rewritten text"
  },
  "arguments": {
    "replacementText": "Rewritten text"
  }
}
```

## 11. Context Extraction Rules

### Default rule

- only the current selection is sent to the model

### No-selection behavior

If nothing is selected, the extension must not silently send the full document.

Instead it must do one of the following:

- ask the user to select content first, or
- ask for explicit permission to use a larger scope

### Scope escalation options

- current paragraph
- current spreadsheet neighborhood around the selected cell
- current text box or current slide text region
- full current document or sheet only after explicit consent

### Context trimming

- trim whitespace and formatting noise where safe
- avoid sending hidden metadata not needed for the task
- cap oversized selections and request user confirmation before sending more

## 12. Initial Action Registry

### Writer actions

Read-only:

- `Writer.GetSelection`

Safe formatting-only:

- `Writer.ToggleBold`
- `Writer.ToggleItalic`
- `Writer.ToggleUnderline`
- `Writer.ApplyHeading1`
- `Writer.ApplyHeading2`
- `Writer.ApplyHeading3`
- `Writer.ApplyBullets`
- `Writer.AlignLeft`
- `Writer.AlignCenter`
- `Writer.AlignRight`

Content edits:

- `Writer.ReplaceSelection`
- `Writer.InsertBelowSelection`

### Calc actions

Read-only:

- `Calc.GetSelectedRange`
- `Calc.GetSelectedFormula`

Safe formatting-only:

- `Calc.ToggleBold`
- `Calc.ToggleItalic`
- `Calc.AlignLeft`
- `Calc.AlignCenter`
- `Calc.AlignRight`
- `Calc.ApplyNumberFormatCurrency`
- `Calc.ApplyNumberFormatPercent`
- `Calc.ApplyNumberFormatDate`

Content or structural edits:

- `Calc.InsertFormulaInSelection`
- `Calc.CreateChartFromSelection`
- `Calc.SortSelectedRange`

### Impress actions

Read-only:

- `Impress.GetSelectedText`

Safe formatting-only:

- `Impress.ToggleBold`
- `Impress.ToggleItalic`
- `Impress.ApplyBullets`
- `Impress.AlignLeft`
- `Impress.AlignCenter`
- `Impress.AlignRight`

Content or structural edits:

- `Impress.ReplaceSelectedText`
- `Impress.CreateSlideFromOutline`
- `Impress.ApplyLayoutToCurrentSlide`

## 13. History Storage Specification

History must be stored locally in the LibreOffice profile using SQLite.

Suggested location:

- `<LibreOfficeProfile>/loaia/history.sqlite3`

Suggested tables:

- `sessions`
- `messages`
- `events`

Suggested session key:

- `profile_id`
- `canonical_document_url`
- `app_type`

### What to store

- user message text
- model answer text
- tool proposal metadata
- approval and rejection events
- executed action metadata
- provider and model used
- timestamps

### What not to store

- raw API keys
- entire document snapshots by default
- full hidden office metadata that is not needed for history replay

## 14. Settings and Secret Storage

### Non-secret settings

Store in a profile-scoped settings file, for example:

- `<LibreOfficeProfile>/loaia/settings.json`

Settings include:

- default provider
- default model
- local endpoint URLs
- privacy defaults
- auto-apply formatting toggle
- log verbosity

### Secret storage

Remote provider API keys should be stored in:

- Windows Credential Manager

The extension and sidecar should reference secrets by logical provider name, not by embedding them into history or logs.

## 15. Logging and Audit

Three log streams are required.

### Extension log

- UI lifecycle
- action validation
- execution failures

### Sidecar log

- provider selection
- request routing
- streaming lifecycle
- provider errors

### Audit log

- approvals
- rejections
- executed actions
- document URL reference
- provider and model used

Suggested audit location:

- `<LibreOfficeProfile>/loaia/audit.jsonl`

## 16. Error Handling Requirements

The MVP must handle these failures clearly.

### Sidecar unavailable

- show disconnected state
- offer reconnect or restart

### Provider authentication failure

- show provider-specific error
- do not lose current prompt text

### Local endpoint unreachable

- show actionable local endpoint error
- allow switching provider without restarting LibreOffice

### Invalid tool proposal

- reject the proposal locally
- log the violation
- show a generic safe failure message

### Undo failure

- show warning
- preserve audit trail and visible action result details

## 17. Acceptance Criteria

### Phase 0 acceptance

- extension can open a visible AI panel
- extension can start and handshake with the sidecar
- mock provider can return one direct answer
- one Writer safe formatting action auto-applies successfully

### Phase 1 acceptance

- one remote provider works end to end
- one local OpenAI-compatible provider works end to end
- Writer selection summarize works
- Writer selection rewrite with preview and approval works
- per-document profile-scoped history is restored after reopening the document
- Calc supports at least one read scenario and one write scenario
- Impress supports at least one read scenario and one write scenario
- all approved write operations remain undoable through normal user workflow

## 18. Explicitly Out of Scope

- macro generation
- macro execution
- arbitrary shell execution
- arbitrary filesystem tools
- unrestricted UNO command dispatch
- full-document autonomous rewriting without approval
- multi-user collaboration sync
- mobile or LibreOfficeKit deployment

## 19. First Implementation Order

The first implementation order should be:

1. transport and handshake
2. sidebar shell UI
3. Writer selection extraction
4. local mock provider
5. safe Writer formatting action
6. Writer rewrite with preview
7. settings and secret storage
8. history store
9. Calc minimal slice
10. Impress minimal slice

This order minimizes risk while still honoring the requirement that the MVP cover Writer, Calc, and Impress.