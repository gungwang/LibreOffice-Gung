# 架构说明

英文版: [architecture.md](./architecture.md)

这个子项目按照上一级仓库中的设计文档来实现 LibreOffice AI Agent，运行时分成两个核心部分：

- `extension/` 负责 LibreOffice 里的 UI、上下文提取、用户审批、历史记录和文档修改
- `sidecar/` 负责模型供应商适配、模型选择、规划和流式输出

完整设计请看上一级文档：

- [上级架构文档](../../docs/libreoffice-ai-agent-architecture.zh-CN.md)
- [上级 MVP 设计规格](../../docs/libreoffice-ai-agent-mvp-design-spec.zh-CN.md)

对当前子项目的具体解释：

- 这个目录是实际实现根目录
- `core/` 仍然是 LibreOffice 源码树，不属于这个子项目内部
- 扩展端不能把不同 AI 厂商的调用逻辑写死进去
- sidecar 不能直接改 LibreOffice 文档
