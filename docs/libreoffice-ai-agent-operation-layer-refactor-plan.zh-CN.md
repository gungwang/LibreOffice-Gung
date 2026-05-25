# LibreOffice AI 操作层重构计划与仓库骨架

英文版: [libreoffice-ai-agent-operation-layer-refactor-plan.md](./libreoffice-ai-agent-operation-layer-refactor-plan.md)
相关架构文档: [libreoffice-ai-agent-operation-layer-architecture.zh-CN.md](./libreoffice-ai-agent-operation-layer-architecture.zh-CN.md)
相关设计规格: [libreoffice-ai-agent-operation-layer-design-spec.zh-CN.md](./libreoffice-ai-agent-operation-layer-design-spec.zh-CN.md)

## 概述

这个计划的目标，是把 `./libreoffice-ai-agent` 重组成“能力目录是唯一真相来源”的结构。

这里要先重做的不是界面，而是控制模型：删掉重复注册表，去掉关键词式规划，统一走带策略保护的通用执行运行时，并把“观察结果”变成强制环节。

## 规划假设

- 保留 extension + sidecar 的拆分方式。
- 除非后续有明确证据，否则继续用 Windows named pipe。
- 继续保持子项目位于主 LibreOffice 仓库内。
- 先迁移 Writer、Calc、Impress 现有流程，保证引入新运行时后不回退。
- 现在的 MVP 文档和代码是迁移输入，不再当作最终架构目标。

## 目标仓库结构

```text
libreoffice-ai-agent/
  README.md
  pyproject.toml
  docs/
    architecture.md
    development.md
    provider-config.md
    testing.md
  extension/
    src/
      loaia/
        bootstrap.py
        protocol_handler.py
        chat_controller.py
        sidebar_panel.py
        sidebar_actions.py
        snapshot/
          app.py
          writer.py
          calc.py
          impress.py
          draw.py
          math.py
          base.py
        execution/
          engine.py
          preflight.py
          observe.py
          approval.py
          undo.py
          bindings/
            dispatch.py
            routines.py
          generated/
            capability_registry.py
            safety_matrix.py
            binding_manifest.py
        history/
        broker/
        ui/
  sidecar/
    src/
      loaia_sidecar/
        main.py
        server.py
        orchestrator/
          engine.py
          session.py
          evaluator.py
        planner/
          retriever.py
          composer.py
          replan.py
          prompt_builder.py
          generated/
            capability_index.json
        providers/
        config/
        logging/
  shared/
    src/
      loaia_shared/
        schema/
        capabilities/
          catalog/
            app.yaml
            writer.yaml
            calc.yaml
            impress.yaml
            draw.yaml
            math.yaml
            base.yaml
          compiler.py
          manifest.py
          generated/
            descriptor_hashes.json
            docs_tables.json
  scripts/
    generate_capability_artifacts.py
    validate_capability_catalog.py
    build_capability_index.py
    verify_operator_flow.ps1
```

现有目录大体还能看出来原样，但这次重构会新增一个稳定的能力层，并把 planner 和 executor 的职责拆得更清楚。

## 工作流总览

| 工作流 | 当前问题 | 目标结果 |
|---|---|---|
| 共享能力模型 | 动作、安全、文档信息分散重复 | 一份目录生成所有产物 |
| extension 执行运行时 | registry 和安全逻辑会漂移 | 生成式 registry + 通用 executor + 单一路径 preflight |
| extension 快照与观察 | 上下文窄，后置检查不一致 | 可复用的快照与探针模块 |
| sidecar 规划 | 关键词启发式太重 | 检索、组合、评估、重规划 |
| provider 集成 | provider 看到的是隐式工具面 | provider 只看到有边界的能力摘要 |
| 测试与文档 | 漂移总是晚发现 | 目录生成文档表格和 CI 漂移检查 |
| 应用能力包 | 每个应用扩展方式不一样 | Writer、Calc、Impress、Draw、Math、Base、App 统一按 pack 扩展 |

## 按模块拆解的计划

### 1. 共享能力模型

需要吸收或扩展的现有文件：

- `shared/src/loaia_shared/schema/actions.py`
- `shared/src/loaia_shared/types.py`
- `shared/src/loaia_shared/errors.py`

目标模块：

- `shared/src/loaia_shared/capabilities/catalog/`
- `shared/src/loaia_shared/capabilities/compiler.py`
- `shared/src/loaia_shared/capabilities/manifest.py`

交付物：

- 描述符 schema 与校验
- 生成的 descriptor hash
- 生成的文档表格
- 生成的运行时 registry 契约

完成标准：

- 当前所有 capability id 都已经进入目录
- 运行时模块里不再出现“目录里没有定义的 capability id”

### 2. Extension 执行运行时

需要迁移的现有文件：

- `extension/src/loaia/actions/registry.py`
- `extension/src/loaia/actions/executor.py`
- `extension/src/loaia/sidebar_actions.py`
- `extension/src/loaia/undo.py`

目标模块：

- `extension/src/loaia/execution/engine.py`
- `extension/src/loaia/execution/preflight.py`
- `extension/src/loaia/execution/observe.py`
- `extension/src/loaia/execution/bindings/`
- `extension/src/loaia/execution/generated/`

交付物：

- 一条统一的 preflight 路径，负责 schema、策略和范围校验
- 一条统一的 binding 运行时，支持 `uno-dispatch`、`uno-routine`、`document-api`
- `App.ExecuteUnoCommand` 通过同一份生成 manifest 执行，而不是额外特判
- 单步执行时集成 undo group 和审计记录

完成标准：

- extension 侧不再单独维护手写安全白名单
- `App.ExecuteUnoCommand` 有自动化测试和 live 验证

### 3. 快照与观察层

需要迁移的现有文件：

- `extension/src/loaia/context/`
- `extension/src/loaia/chat_controller.py` 中的一部分逻辑

目标模块：

- `extension/src/loaia/snapshot/`
- `extension/src/loaia/execution/observe.py`

交付物：

- 每个 app pack 的上下文快照
- 可复用的前置探针和后置探针
- 能被 sidecar 用来重规划的观察摘要

完成标准：

- 每个写能力至少有一个后置探针
- planner 是否继续，不再只看异常文本，也看观察输出

### 4. Sidecar 编排层

需要拆分的现有文件：

- `sidecar/src/loaia_sidecar/server.py`
- `sidecar/src/loaia_sidecar/main.py` 中的一部分逻辑

目标模块：

- `sidecar/src/loaia_sidecar/orchestrator/engine.py`
- `sidecar/src/loaia_sidecar/orchestrator/session.py`
- `sidecar/src/loaia_sidecar/orchestrator/evaluator.py`

交付物：

- 会话状态机
- 分步执行编排
- 观察结果评估
- 有边界的计划修正行为

完成标准：

- transport server 变薄，编排逻辑不再堆在一个巨大 `server.py` 里

### 5. Sidecar 规划与检索

需要替换或缩减的现有文件：

- `sidecar/src/loaia_sidecar/planner/policy.py`
- `sidecar/src/loaia_sidecar/planner/prompts.py`
- 目前嵌在 `sidecar/src/loaia_sidecar/server.py` 里的启发式规划逻辑

目标模块：

- `sidecar/src/loaia_sidecar/planner/retriever.py`
- `sidecar/src/loaia_sidecar/planner/composer.py`
- `sidecar/src/loaia_sidecar/planner/replan.py`
- `sidecar/src/loaia_sidecar/planner/prompt_builder.py`
- `planner/generated/` 下的生成索引

交付物：

- 由目录数据构建出的能力检索索引
- 基于候选描述符生成的 planner prompt
- 主路径中不再有关键词表
- 基于观察证据的计划修正

完成标准：

- planner 测试会在“编造 capability id”或“依赖手写关键词列表”时失败

### 6. 聊天会话、审批与历史

需要调整的现有文件：

- `extension/src/loaia/chat_controller.py`
- `extension/src/loaia/document_session.py`
- `extension/src/loaia/history/`
- `extension/src/loaia/session_store.py`
- `extension/src/loaia/audit.py`

目标结果：

- chat controller 变成围绕“计划和单步执行”的会话编排器
- 审批记录挂在 plan step 上，不再挂在零散 UI 分支上
- 历史里能保存计划、观察、审批和最终结果

完成标准：

- 恢复一个旧会话时，系统能说明上一份计划、上一步执行和上一次观察结果是什么

### 7. 应用能力 pack

当前状态：

- Writer、Calc、Impress 已经有部分类型化动作
- Draw、Math、Base 和更广义 app-global 覆盖还很薄或缺失

目标 pack：

- `app`
- `writer`
- `calc`
- `impress`
- `draw`
- `math`
- `base`

每个 pack 的交付物：

- 描述符
- 快照探针
- 后置探针
- binding 测试
- 代表性 live smoke test

完成标准：

- 支持新 pack 的主要工作，是加目录条目和探针，而不是重写 planner

### 8. 文档、脚本与 CI

需要演进的现有资产：

- `../docs/` 下的现有文档
- `scripts/` 下的现有验证脚本

目标新增：

- `scripts/generate_capability_artifacts.py`
- `scripts/validate_capability_catalog.py`
- `scripts/build_capability_index.py`
- `scripts/verify_operator_flow.ps1`

交付物：

- 在 CI 里运行的生成命令
- 用来比较目录输出和运行时文件的漂移检查
- 由目录元数据生成的文档表格
- 覆盖 `plan -> execute -> observe` 的操作层 smoke test

完成标准：

- 目录漂移会先在 CI 失败，而不是拖到运行时才暴露

## 分阶段推进

### Phase 0：冻结当前表面

- 盘点当前 action id、白名单、prompt surface、协议命令
- 把所有手写 registry 标记成迁移对象
- 停止继续扩张启发式 planner

### Phase 1：先建立目录编译器

- 定义描述符 schema
- 把现有 Writer、Calc、Impress action id 迁入描述符
- 生成 manifest 和 registry 输出

### Phase 2：先迁执行路径

- 让 extension 校验改走生成产物
- 替换重复安全检查
- 用目录支持 `App.ExecuteUnoCommand`

### Phase 3：再迁规划路径

- 构建检索索引
- 把 provider prompt 改成基于候选能力摘要
- 删掉主路径里的关键词式路由

### Phase 4：强制引入观察闭环

- 给所有写能力补齐后置探针
- 把观察结果写回 evaluator 和会话历史

### Phase 5：扩展应用 pack

- 补齐 Draw、Math、Base 和 app-global 覆盖
- 增加结构化多步能力

### Phase 6：移除旧代码路径

- 删除旧 registry、旧 whitelist、旧 planner heuristic
- 在通过对等验证和测试后，清掉兼容层

## 第一波迁移清单

先把当前用户可见表面迁平，再扩新范围。

### App-global

- 会话打开与恢复流程
- `App.ExecuteUnoCommand`
- 通用审批与审计行为

### Writer

- 选区读取和替换流程
- 安全格式流程
- 段落与样式流程

### Calc

- 区域读取流程
- 公式插入流程
- 图表创建流程
- 数字格式流程

### Impress

- 已选文字读取和替换流程
- 幻灯片创建流程
- 布局流程

做完对等迁移后，再进入 Draw、Math、Base 和套件级命令的新 pack 工作。

## 完成定义

只有同时满足下面几点，这次转向才算完成。

- capability id、安全元数据、绑定方式只在目录里编写一次
- planner 主路径不再依赖手写关键词表
- 每个写步骤都会发出观察报告
- `App.ExecuteUnoCommand` 既安全又实用，并有自动化测试覆盖
- 文档、测试、运行时 registry 都从同一份数据生成
- 新增一个操作时，主要工作变成“补描述符、探针和测试”
