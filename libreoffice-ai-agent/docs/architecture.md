# Architecture

Simplified Chinese version: [architecture.zh-CN.md](./architecture.zh-CN.md)

This subproject follows the parent repository design documents and implements the LibreOffice AI Agent as two cooperating runtime parts:

- `extension/` for LibreOffice-side UI, context extraction, approvals, history, and document mutation
- `sidecar/` for provider adapters, model selection, planning, and streaming

For the full design source, see:

- [Parent Architecture Doc](../../docs/libreoffice-ai-agent-architecture.md)
- [Parent MVP Design Spec](../../docs/libreoffice-ai-agent-mvp-design-spec.md)

Local interpretation for this subproject:

- this directory is the implementation root
- `core/` remains the LibreOffice source tree outside this subproject
- the extension must never embed vendor-specific provider logic
- the sidecar must never mutate LibreOffice documents directly
