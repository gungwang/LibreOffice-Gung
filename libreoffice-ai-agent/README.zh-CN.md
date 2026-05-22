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
- `scripts/cleanup_build_profiles.ps1` 清理 `build/` 下较旧的手动命名 LibreOffice 验证 profile；它会跳过仍在使用的 profile，并通过 `-KeepNewest` 保留一小部分最近目录。配合 `-IncludeInstallProfiles` 时，同一个入口也会清理较旧的 `lo-profile-install-*` 目录
- `scripts/verify_protocol_actions.ps1` 安装 OXT，并在真实 LibreOffice 中验证 Writer 的“预览/批准应用”改写流程；默认检查本地启发式改写，配合 `-ExpectChangedText` 与 `-Provider`/`-Model` 也可以验证 provider 驱动的 Writer 改写提案
- `scripts/verify_sidebar_direct_answer.ps1` 安装 OXT，并在真实 LibreOffice 中验证“打开侧边栏 + 直接回答”流程，且不改动文档内容；配合 `-ExpectNonScaffoldAnswer` 与 `-Provider`/`-Model`，同一个脚本也可以强制验证 provider 驱动的直接回答路径
- `scripts/verify_sidebar_invalid_selection.ps1` 安装 OXT，并在真实 LibreOffice 中验证 `preview-selection` 的错误路径；默认检查 Writer“未选中文本”校验，配合 `-Scenario unsupported-document` 可验证 Calc 中“仅支持 Writer”的本地拒绝，配合 `-Scenario transport-error` 可通过一个隔离的不存在命名管道地址验证“sidecar 不可用”的错误显示流程

当前更完整的规划文档仍然放在上一级仓库的 `docs/` 目录中：

- [项目架构](../docs/libreoffice-ai-agent-architecture.zh-CN.md)
- [项目脚手架方案](../docs/libreoffice-ai-agent-repo-scaffold.zh-CN.md)
- [MVP 设计规格](../docs/libreoffice-ai-agent-mvp-design-spec.zh-CN.md)

当前状态：

- 这里已经从初始骨架进入可运行的 Windows 原型阶段
- 侧边栏基础界面、Writer 预览/批准应用流程、以及真实 LibreOffice 验证脚本都已就位
- 更完整的规划器和 Provider 执行能力还未完成，目前直接回答仍然是 scaffold 阶段的响应
