# Development

Simplified Chinese version: [development.zh-CN.md](./development.zh-CN.md)

Suggested development order:

1. transport handshake between extension and sidecar
2. sidebar shell UI
3. Writer selection extraction
4. mock provider and local OpenAI-compatible provider
5. safe formatting action path
6. preview-and-approve content edit path
7. history store and audit log
8. Calc and Impress minimum slices

Working assumptions:

- Python 3.11+
- Windows development first
- local LibreOffice test profile for extension install and debugging
