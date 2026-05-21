# 测试说明

英文版: [testing.md](./testing.md)

测试分层：

- 单元测试：schema、策略、动作校验
- 集成测试：extension 与 sidecar 之间的传输契约
- 端到端测试：Writer、Calc、Impress 的主流程

基本规则：

- CI 里不要依赖真实厂商 API
- 优先使用 mock provider 和本地夹具
- 文档夹具要尽量可重复、可回归
