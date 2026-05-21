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

常用脚本：

- `scripts/run_sidecar.ps1` 启动本地 sidecar，并自动设置项目需要的 `PYTHONPATH`
- `scripts/verify_protocol_actions.ps1` 安装 OXT，并在真实 LibreOffice 中验证 Writer 的“预览/批准应用”改写流程
- `scripts/verify_sidebar_direct_answer.ps1` 安装 OXT，并在真实 LibreOffice 中验证“打开侧边栏 + 直接回答”流程，且不改动文档内容
- `scripts/verify_sidebar_transport_error.ps1` 安装 OXT，并通过一个隔离的不存在命名管道地址，在真实 LibreOffice 中验证“sidecar 不可用”时的错误显示流程
- `scripts/verify_sidebar_invalid_selection.ps1` 安装 OXT，并在真实 LibreOffice 中验证 Writer“未选中文本”时的本地校验流程，此时 `preview-selection` 应在发出 sidecar 请求之前直接失败

当前更完整的规划文档仍然放在上一级仓库的 `docs/` 目录中：

- [项目架构](../docs/libreoffice-ai-agent-architecture.zh-CN.md)
- [项目脚手架方案](../docs/libreoffice-ai-agent-repo-scaffold.zh-CN.md)
- [MVP 设计规格](../docs/libreoffice-ai-agent-mvp-design-spec.zh-CN.md)

当前状态：

- 这里已经从初始骨架进入可运行的 Windows 原型阶段
- 侧边栏基础界面、Writer 预览/批准应用流程、以及真实 LibreOffice 验证脚本都已就位
- 更完整的规划器和 Provider 执行能力还未完成，目前直接回答仍然是 scaffold 阶段的响应
