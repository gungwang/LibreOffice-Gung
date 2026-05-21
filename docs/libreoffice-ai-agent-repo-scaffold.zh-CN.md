# LibreOffice AI Agent 兄弟仓库脚手架方案

英文版: [libreoffice-ai-agent-repo-scaffold.md](./libreoffice-ai-agent-repo-scaffold.md)
详细 MVP 设计规格: [libreoffice-ai-agent-mvp-design-spec.zh-CN.md](./libreoffice-ai-agent-mvp-design-spec.zh-CN.md)

## 方案概述

这份文档回答两个问题：

- 新的兄弟仓库应该长什么样
- 第一阶段应该先搭哪些骨架，才能尽快做出可运行的版本

这里说的“脚手架”，可以理解为项目的基础骨架：目录结构、关键模块、测试位置、构建脚本、里程碑拆分。

## 建议的新仓库

- 仓库名：`libreoffice-ai-agent`
- 建议路径：`C:\AI\intel-ai\libreoffice-ai-agent`

这个仓库与 LibreOffice core 分开维护，但会产出两个交付物：

- 一个 LibreOffice 扩展包（`.oxt`）
- 一个运行在 Windows 本机的 AI 侧车进程

## 建议的顶层目录结构

```text
libreoffice-ai-agent/
  README.md
  LICENSE
  pyproject.toml
  .gitignore
  .editorconfig
  .github/
    workflows/
      ci.yml
  docs/
    architecture.md
    development.md
    provider-config.md
    testing.md
  extension/
    oxt/
      description.xml
      Addons.xcu
      ProtocolHandler.xcu
      Sidebar.xcu
      META-INF/
        manifest.xml
    src/
      loaia/
        __init__.py
        bootstrap.py
        protocol_handler.py
        sidebar_panel.py
        chat_controller.py
        context/
          __init__.py
          writer.py
          calc.py
          impress.py
        actions/
          __init__.py
          base.py
          registry.py
          writer.py
          calc.py
          impress.py
          app.py
        history/
          __init__.py
          store.py
          keys.py
        broker/
          __init__.py
          client.py
          transport.py
        ui/
          panel.ui
          icons/
    tests/
      unit/
      integration/
  sidecar/
    src/
      loaia_sidecar/
        __init__.py
        main.py
        server.py
        transport/
          __init__.py
          named_pipe.py
        providers/
          __init__.py
          base.py
          openai_compatible.py
          anthropic.py
          gemini.py
          openrouter.py
        planner/
          __init__.py
          router.py
          policy.py
          prompts.py
        models/
          __init__.py
          catalog.py
          capabilities.py
        config/
          __init__.py
          settings.py
          secrets.py
        logging/
          __init__.py
          audit.py
    tests/
      unit/
      integration/
  shared/
    src/
      loaia_shared/
        __init__.py
        schema/
          __init__.py
          messages.py
          actions.py
          history.py
        types.py
        errors.py
  test-fixtures/
    writer/
    calc/
    impress/
  scripts/
    build_oxt.ps1
    run_sidecar.ps1
    dev_install_oxt.ps1
    package_windows.ps1
```

## 语言与打包选择

### 主要语言

- 扩展和侧车都先用 Python

### 打包方式

- 用 `pyproject.toml` 管理依赖
- 从 `extension/oxt/` 生成 `.oxt`
- 侧车后续可再补 Windows 可执行打包

### 为什么这样分层

- 扩展和侧车逻辑分开，但仍能在一个仓库里一起版本化
- 可以把公共 schema 放到 `shared/`，避免复制粘贴
- 更容易建立清晰的测试边界

## 关键模块说明

### `extension/src/loaia/bootstrap.py`

作用：

- 扩展启动入口
- 面板和 broker 客户端的延迟启动逻辑

### `extension/src/loaia/protocol_handler.py`

作用：

- 注册 LibreOffice 命令和 UI 入口
- 打开 AI 侧边栏 deck 或 panel

### `extension/src/loaia/sidebar_panel.py`

作用：

- 负责面板 UI 组合和生命周期管理
- 显示 Provider 指示、模型选择、同意提示、消息列表

### `extension/src/loaia/chat_controller.py`

作用：

- 编排一次聊天请求的完整生命周期
- 读取上下文、调用 broker、渲染动作卡片、执行工具

### `extension/src/loaia/context/*.py`

作用：

- 每个应用一个上下文提取器
- 返回结构化、默认只包含选区的数据

### `extension/src/loaia/actions/registry.py`

作用：

- 作为中央动作注册表和校验入口
- 把动作 id 映射到具体实现函数和策略类型

### `sidecar/src/loaia_sidecar/server.py`

作用：

- 侧车请求分发器
- 管理当前活动请求和流式响应状态

### `sidecar/src/loaia_sidecar/providers/*.py`

作用：

- 每类 Provider 一个适配器
- 提供统一的请求和流式输出接口

### `sidecar/src/loaia_sidecar/planner/router.py`

作用：

- 决定返回直接答案还是工具提案
- 按 Provider、成本、模型能力选择模型

### `shared/src/loaia_shared/schema/messages.py`

作用：

- 定义通过命名管道交换的消息结构

## 初始消息契约

第一版应该先定义一套小而稳定的协议。

扩展发给侧车：

- `HandshakeRequest`
- `ChatRequest`
- `CancelRequest`
- `ProviderListRequest`
- `ModelListRequest`

侧车返回给扩展：

- `HandshakeResponse`
- `StreamChunk`
- `ToolProposal`
- `DirectAnswer`
- `ErrorResponse`

工具执行结果循环：

- `ToolExecutionResult`
- `ApprovalDecision`

## 建议的 Phase 0 待办列表

1. 创建仓库骨架。
2. 定义共享消息 schema。
3. 实现命名管道握手。
4. 做一个带 mock provider 的最小 sidecar。
5. 做一个能打开占位面板的 LibreOffice 命令入口。
6. 实现 Writer 选区提取。
7. 先实现两个动作：
   - `Writer.GetSelection`
   - `Writer.ToggleBold`
8. 增加一个假的 planner，能返回一个只读答案和一个格式动作。
9. 确认格式动作会立即自动应用。
10. 确认内容编辑类动作即使暂时只做 stub，也已经有预览流程预留。

## 建议的 Phase 1 待办列表

1. Provider 设置界面。
2. OpenAI 兼容 Provider 适配器。
3. 一个远程 Provider 适配器。
4. 带预览的 Writer 内容改写动作。
5. 按文档的历史记录存储。
6. 审计日志。
7. Undo 分组。
8. 基于本地 LibreOffice 实例的初始集成测试。

## 测试策略

### 单元测试

- 动作校验
- schema 序列化
- 使用 mock HTTP 的 Provider 适配器测试
- 策略逻辑测试

### 集成测试

- 命名管道握手
- 扩展到 broker 的请求流测试
- 历史记录存储行为测试

### 端到端测试

- Writer 选区总结
- Writer 改写并预览后应用
- Writer 格式动作自动应用
- Calc 选区解释
- Impress 选中文本改写

### 测试夹具策略

- 使用本地文档夹具，保证测试结果稳定
- CI 中绝不依赖真实厂商 API

## 构建与开发工作流

### 本地开发循环

1. 以调试模式启动本地 sidecar。
2. 构建扩展，或把扩展源码同步到 `.oxt` 包中。
3. 把扩展安装到一个专门的 LibreOffice 测试 profile。
4. 使用这个 profile 启动 LibreOffice。
5. 优先验证 Writer 场景。

### 早期必须提供的脚本

- `build_oxt.ps1`
- `dev_install_oxt.ps1`
- `run_sidecar.ps1`

## 发布产物

Phase 1 的发布输出建议包括：

- `libreoffice-ai-agent.oxt`
- `loaia-sidecar` 的 Windows 打包或 Python 运行包
- 说明支持哪些 Provider、哪些应用、哪些操作需要审批的 release note

## 建议里程碑

### Milestone A：骨架与传输

- 仓库已创建
- 扩展命令入口已存在
- 命名管道传输已跑通

### Milestone B：Writer 第一条闭环

- 面板可以打开
- 能读取 Writer 选区
- 只读回答可用
- 安全格式自动应用可用
- 改写预览可用

### Milestone C：历史和设置

- Provider 设置可持久化
- 按文档历史可用
- 审计日志可用

### Milestone D：Calc 支持

- 区域提取
- 公式解释与插入
- 从选区生成图表

### Milestone E：Impress 支持

- 选中文本提取
- 根据提纲生成幻灯片
- 布局应用

## 范围护栏

在 MVP 稳定之前，仓库应该明确延后这些能力：

- 宏生成
- 宏执行
- 任意文件系统工具
- 任意 shell 执行
- 全文档自主重写
- 大范围、未筛选的 UNO 命令分发

## 推荐的第一个可演示版本

第一场对外演示建议展示下面这条完整链路：

1. 在 Writer 中打开 AI 侧边栏。
2. 连接一个本地 OpenAI 兼容模型。
3. 总结当前选中的段落。
4. 改写当前选中的段落，并展示预览。
5. 通过安全格式动作立即应用加粗。
6. 关闭并重新打开同一文档后，展示会话历史已经按当前 LibreOffice profile 恢复。

只有这条链路足够稳定，才值得继续扩大范围。