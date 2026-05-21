# Testing

Simplified Chinese version: [testing.zh-CN.md](./testing.zh-CN.md)

Test layers:

- unit tests for schemas, policies, and action validation
- integration tests for extension-side and sidecar-side transport contracts
- end-to-end tests for Writer, Calc, and Impress happy paths

Rules:

- avoid live vendor APIs in CI
- prefer mock providers and local fixtures
- preserve deterministic document fixtures for regressions
