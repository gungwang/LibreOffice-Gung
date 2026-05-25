# LibreOffice AI 操作层架构说明

英文版: [libreoffice-ai-agent-operation-layer-architecture.md](./libreoffice-ai-agent-operation-layer-architecture.md)
详细设计规格: [libreoffice-ai-agent-operation-layer-design-spec.zh-CN.md](./libreoffice-ai-agent-operation-layer-design-spec.zh-CN.md)
按模块拆解的重构计划: [libreoffice-ai-agent-operation-layer-refactor-plan.zh-CN.md](./libreoffice-ai-agent-operation-layer-refactor-plan.zh-CN.md)

## 概述

这份文档用“AI 操作层”架构替换之前偏 MVP 助手的设计。

核心目标不再是“只做少量安全助手能力”，而是“让 AI 在可控边界内广泛操作 LibreOffice”。实现方式有三个关键点：

- 一个单一真相来源的能力目录，也就是唯一权威的能力清单
- 一个 `plan -> execute -> observe` 循环，也就是先规划、再执行、再根据结果回看
- 一个清晰的安全边界，允许能力扩展，但不允许模型绕过白名单直接乱调 UNO

扩展加本地 sidecar 的拆分方式保留，但控制模型要重做。

## 产品目标

目标系统必须让 AI 代理可以在 Writer、Calc、Impress、Draw、Math、Base 以及全局应用级命令上，完成“发现能力、生成计划、执行动作、检查结果”这一整套闭环；同时每个命令都必须落在明确白名单内，并且带有类型化参数、前置条件、后置条件、撤销分组和审计记录。

## 已确定的产品决策

- 仍然先支持 Windows。
- 在进入 LibreOffice core 之前，继续以 `./libreoffice-ai-agent` 子项目方式推进。
- 只有扩展端可以真正修改 LibreOffice 状态。
- sidecar 负责编排、规划、能力检索、模型调用和计划修正。
- 共享能力目录是唯一权威来源，能力元数据、安全等级、绑定方式、planner 暴露面、文档表格、测试都从这里生成。
- planner 可以检索能力，但不能自己编造 capability id，也不能自己拼原始 UNO 命令。
- `App.ExecuteUnoCommand` 会变成真正可用的通用执行原语，但只能执行能力目录白名单中已有的命令。
- 系统默认支持多步执行。每一个会修改文档的步骤，都必须先产出观察结果，下一步才能继续。
- 是否需要人工确认，由策略等级和作用范围决定，而不是靠多个模块里的手写特例判断。

## 目标

- 把“广泛操作 LibreOffice”变成产品核心结果。
- 以后扩展能力时，主要是新增目录条目，而不是继续堆关键词分支。
- 支持多步计划，并且能根据观察结果调整后续动作。
- 所有写操作都必须可控、可撤销、可审计。
- 动作注册表、planner 检索面、安全矩阵、文档表格、漂移测试都从同一份数据生成。
- 保持 provider 无关，不把模型厂商逻辑塞进 LibreOffice 里。

## 非目标

- 不做无白名单保护的原始命令执行。
- 不再让硬编码关键词路由成为主规划方式。
- 不再维护多份彼此独立的动作表、安全表、文档表和测试表。
- 不允许没有观察和审批的大范围静默写入。
- 在操作层还没稳定前，不优先做跨平台。

## 架构原则

1. 能力、策略、绑定方式必须只有一个真相来源。
2. 规划从“能力检索”开始，不从“关键词分类”开始。
3. 没有明确前置条件和后置条件的执行，不算有效执行。
4. 每个写步骤都必须先被观察到，后续步骤才能继续。
5. 覆盖率扩展主要靠新增目录条目和探针，不靠继续加定制控制分支。
6. 撤销、审计、审批不是补充功能，而是运行时核心能力。

## 系统总览

```text
+-------------------------------+        named pipe        +-------------------------------+
| LibreOffice 扩展宿主          | <---------------------> | 本地 Sidecar 编排层          |
|                               |                         |                               |
| - UI 与审批                   |                         | - 能力检索                    |
| - 上下文快照                  |                         | - 计划生成                    |
| - 执行前校验                  |                         | - 重规划 / 结果评估           |
| - 单步执行                    |                         | - Provider 适配层             |
| - 后置检查                    |                         | - 会话编排                    |
| - 撤销与审计                  |                         | - 流式模型交互                |
+---------------+---------------+                         +---------------+---------------+
                |                                                                 |
                | UNO / 文档 API                                                 | Provider API
                v                                                                 v
+-------------------------------+                         +-------------------------------+
| LibreOffice 应用层            |                         | 远程或本地模型                |
| Writer / Calc / Impress       |                         | OpenAI-compatible /           |
| Draw / Math / Base / App      |                         | Anthropic / Gemini /          |
+-------------------------------+                         | OpenRouter / 本地服务         |
                ^                                         +-------------------------------+
                |
+-----------------------------------------------------------------------+
| 共享能力目录与编译器                                                  |
| - 能力描述符                                                          |
| - 生成的运行时注册表                                                  |
| - 生成的 planner 检索索引                                             |
| - 生成的策略矩阵                                                      |
| - 生成的文档表格和漂移测试                                            |
+-----------------------------------------------------------------------+
```

## 单一真相来源

唯一权威数据放在 `shared/src/loaia_shared/capabilities/catalog/` 下。

每个能力描述符都必须声明：

- 稳定的 capability id
- 所属应用范围
- 参数 schema，也就是参数结构定义
- 自然语言示例
- 执行绑定方式
- 安全等级
- 前置条件
- 观察探针和期望结果
- 撤销标签或补偿说明
- 审计字段

planner 提示面、动作注册表、安全白名单、审批矩阵、文档示例、漂移测试，都不允许再各自手写一份。

### 生成出的表面

| 生成产物 | 使用方 | 作用 |
|---|---|---|
| capability registry | extension | 校验 capability id 和参数 |
| execution binding map | extension | 把目录条目解析成 UNO dispatch、本地 routine 或组合步骤 |
| policy matrix | extension 和 sidecar | 保证两端的审批和安全规则一致 |
| retrieval index | sidecar | 让能力真正可发现、可搜索，不再靠关键词路由 |
| prompt surface | sidecar | 只把合法能力和示例暴露给模型 |
| docs tables | docs | 让架构文档和设计规格始终跟目录一致 |
| drift tests | CI | 运行时代码和目录不一致时立即失败 |

## 能力目录模型

一个 capability 就是“系统支持的一条最小可控能力”。

绑定类型：

- `uno-dispatch`：映射到白名单中的 `.uno:` 命令
- `uno-routine`：映射到本地类型化执行函数
- `document-api`：映射到更高层的 LibreOffice API 例程
- `composite-plan`：展开成一组固定的低层能力步骤

能力目录既要给机器用，也要给人看懂，所以结构元数据和语言示例必须放在一起。

### 示例描述符

```yaml
id: Writer.ApplyParagraphStyle
version: 1
app: writer
binding:
  kind: uno-dispatch
  dispatch_alias: writer.apply_paragraph_style
parameters:
  style_name:
    type: enum
    values: [Heading 1, Heading 2, Heading 3]
intent_tags: [format, style, heading]
examples:
  - "make this a heading"
  - "turn the selected paragraph into heading 2"
safety:
  class: targeted-format
  default_approval: auto
  allowed_scopes: [selection, paragraph]
preconditions:
  - probe: writer.has_text_selection
postconditions:
  - probe: writer.selection_paragraph_style_is
    expect_parameter: style_name
undo:
  label: "AI: Apply paragraph style"
audit:
  category: formatting
```

## 运行时组件

### 1. 共享能力目录与编译器

职责：

- 维护描述符 schema 和校验规则
- 生成运行时和文档需要的各种产物
- 提供稳定的 descriptor hash，让 planner 和 executor 指向同一个能力版本
- 提供本地开发和 CI 都能调用的生成脚本

### 2. LibreOffice 扩展操作宿主

职责：

- 抓取当前文档快照和选区上下文
- 用生成出的 registry 数据校验计划步骤
- 执行审批、范围限制和前置条件检查
- 执行 UNO dispatch 或本地 routine
- 跑后置探针，生成观察报告
- 负责撤销分组、审计和会话历史持久化

### 3. 本地 Sidecar 编排层

职责：

- 从生成好的索引里检索候选能力
- 根据当前目标和快照生成执行计划
- 调用 provider 对“候选能力集合”做推理
- 在每一步之后根据观察报告决定继续、重规划还是停止

sidecar 可以理解 LibreOffice 状态，但不能直接改 LibreOffice 文档。

### 4. Provider 适配层

职责：

- 统一不同模型厂商的调用与流式输出接口
- 输出结构化计划，而不是临时拼接的工具文本
- 除了 sidecar 提供的能力描述外，不直接理解 UNO 细节

### 5. 观察与存储层

职责：

- 持久化会话历史、执行计划、审批记录和观察报告
- 为每个已执行步骤保留追加式审计记录
- 存下足够的运行证据，便于复现失败和排查漂移

## `plan -> execute -> observe` 循环

1. 扩展抓取当前文档、选区和应用状态快照。
2. sidecar 根据应用类型、范围和目标，从能力目录索引里检索候选能力。
3. planner 生成有边界的 `ExecutionPlan`，每一步都必须引用合法 capability id，并带上预期观察结果。
4. 扩展先做执行前校验：descriptor hash、参数 schema、安全策略、范围限制、前置条件。
5. 扩展执行一个步骤。
6. 扩展跑后置探针，生成 `ObservationReport`。
7. sidecar 评估结果，决定继续、重规划、升级审批或直接失败退出。
8. 扩展把最终结果写入历史和审计日志。

这就是新的操作层核心原语。默认控制模型不再是“一次性盲执行”。

## 安全边界

安全是按 capability 定义的，不是按零散代码分支定义的。

| 安全等级 | 例子 | 默认行为 | 必要检查 |
|---|---|---|---|
| `read-only` | 解释公式、读取选区、读取样式 | 自动执行 | 范围校验 |
| `targeted-format` | 加粗、套样式、对齐 | 自动执行 | 前置条件 + 后置条件 |
| `targeted-write` | 改写选区、插入公式 | 预览或按策略审批 | 前置条件 + 后置条件 + 撤销 |
| `structural-write` | 建图表、建幻灯片、插表格 | 明确审批 | 前置条件 + 后置条件 + 审计 |
| `destructive-or-wide` | 删内容、覆盖排序、大范围替换 | 带范围摘要的明确确认 | 前置条件 + 后置条件 + 用户确认 |

策略矩阵由能力目录编译生成，extension 和 sidecar 使用的是同一份产物。

## `App.ExecuteUnoCommand`

`App.ExecuteUnoCommand` 不再只是名义上的逃生口，而要变成真正可用的通用执行器。

规则：

- planner 不能发送目录里不存在的任意命令字符串
- 一次调用可以引用 capability id，也可以引用白名单中的 dispatch alias
- 参数在进入 UNO 之前，必须先通过生成出的 schema 校验
- 所有会修改状态的 dispatch，都必须有前置条件和后置条件
- executor 返回的是结构化观察结果，不只是成功或异常文本
- 没有目录元数据的命令，在执行前就要被拒绝

这样既能把命令覆盖做宽，又不会退化成无控制的任意执行。

## 覆盖模型

功能覆盖通过“应用能力包”来扩展。每个 pack 提供自己的描述符、探针和测试。

初始迁移顺序：

1. app 全局 pack
2. Writer pack
3. Calc pack
4. Impress pack
5. Draw pack
6. Math pack
7. Base pack

架构并不要求所有 pack 第一天全部完成，但要求所有新 pack 都使用同一套目录、策略和观察契约。

## 架构检查点

1. 能力目录编译器已经存在，并能生成运行时产物。
2. 手写注册表和安全列表已经被生成产物替换。
3. planner 主路径里不再有关键词启发式控制。
4. 每个写步骤都会产出观察报告。
5. `App.ExecuteUnoCommand` 和专用动作走同一套策略与观察边界。
6. 后续扩展覆盖范围时，主要工作变成“迁移目录条目”，而不是“重写 planner”。

这就是这次项目转向需要达到的架构门槛。
