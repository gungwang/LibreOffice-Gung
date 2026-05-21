# LibreOffice AI Agent

英文版: [README.md](./README.md)

这个目录是 LibreOffice AI 项目的实际实现目录，包含扩展、侧车进程和共享协议代码。

当前目标：

- 先做 Windows 版本的 LibreOffice AI 侧边栏体验
- 把模型供应商相关逻辑放在 LibreOffice core 之外
- 通过“类型化动作层”支持 Writer、Calc、Impress
- 默认只发送当前选中内容，作为隐私边界

主要目录：

- `extension/` LibreOffice 扩展代码和 OXT 打包资源
- `sidecar/` 本地 broker 进程，负责 Provider 调用、规划和流式输出
- `shared/` 共享消息 schema 和通用类型
- `docs/` 当前子项目自己的实现和开发文档
- `scripts/` 开发和打包脚本

当前更完整的规划文档仍然放在上一级仓库的 `docs/` 目录中：

- [项目架构](../docs/libreoffice-ai-agent-architecture.zh-CN.md)
- [项目脚手架方案](../docs/libreoffice-ai-agent-repo-scaffold.zh-CN.md)
- [MVP 设计规格](../docs/libreoffice-ai-agent-mvp-design-spec.zh-CN.md)

当前状态：

- 这里还是初始骨架
- 代码目前以占位结构和协议定义为主
- 后续实现建议从传输层、侧边栏基础 UI、以及第一批 Writer 动作开始
