# LibreOffice AI 操作层设计规格

英文版: [libreoffice-ai-agent-operation-layer-design-spec.md](./libreoffice-ai-agent-operation-layer-design-spec.md)
相关架构文档: [libreoffice-ai-agent-operation-layer-architecture.zh-CN.md](./libreoffice-ai-agent-operation-layer-architecture.zh-CN.md)
相关重构计划: [libreoffice-ai-agent-operation-layer-refactor-plan.zh-CN.md](./libreoffice-ai-agent-operation-layer-refactor-plan.zh-CN.md)

## 1. 文档目的

这份文档是 LibreOffice AI Agent 从“助手型 MVP”转向“操作层系统”之后的可落地设计规格。

之前的 MVP 设计主要优化的是窄场景助手流程。这份规格定义的是：当项目目标改成“让 AI 在可控边界内广泛操作 LibreOffice”之后，运行时契约、模块边界、安全模型和推进顺序应该是什么。

## 2. 发布阶段

这次转向分三条主线推进。

### Track A：操作层基础版

- 能力目录和编译器
- 生成式运行时注册表
- `plan -> execute -> observe` 会话循环
- 带白名单保护的通用 `App.ExecuteUnoCommand`
- 把当前 Writer、Calc、Impress 能力迁移到目录中

### Track B：覆盖率扩展

- 给 Draw、Math、Base 和 app 全局操作增加目录 pack
- 增加多步结构化能力
- 增加更丰富的观察探针和修复路径

### Track C：全套件成熟版

- 面向整个 LibreOffice 套件的覆盖目标
- 更强的计划修正能力
- 更严格的漂移测试、遥测和运维工具

这份文档详细定义 Track A，同时给出 Track B 和 Track C 必须遵守的契约。

## 3. 成功标准

只有同时满足下面几点，这次重构才算成功。

1. 能力编译器可以从一份目录生成 extension registry、planner index、policy matrix、文档表格和漂移测试。
2. planner 返回的 `ExecutionPlan` 中，每一步都引用目录里的 capability id。
3. 每一个会修改状态的步骤，在继续下一步之前都必须先返回 `ObservationReport`。
4. `App.ExecuteUnoCommand` 可以安全执行白名单内的 `.uno:` 命令，并且具备类型化参数、前置条件、后置条件和撤销分组。
5. 主规划路径里已经移除关键词路由表。
6. Writer、Calc、Impress 当前已有的用户可见流程，在迁移到新运行时后仍然可用。

## 4. 规范中的权威产物

### 4.1 能力描述符

位置：

- `shared/src/loaia_shared/capabilities/catalog/`

内容：

- 各应用的能力描述符
- 通用 alias 和 dispatch 绑定
- 安全元数据
- 观察探针
- 自然语言示例

### 4.2 共享 schema

位置：

- `shared/src/loaia_shared/schema/`
- `shared/src/loaia_shared/capabilities/`

内容：

- 请求与响应 envelope
- `ExecutionPlan`
- `PlanStep`
- `ObservationReport`
- 描述符校验 schema

### 4.3 生成产物

位置：

- extension 侧生成的 registry 模块
- sidecar 侧生成的检索索引
- 生成的文档表格或校验表
- 生成的漂移测试

### 4.4 运行时存储

位置：

- 当前 extension 的状态目录

内容：

- 会话
- 消息历史
- 计划历史
- 审批记录
- 执行日志
- 观察日志

## 5. 会话与传输契约

传输层继续使用 Windows named pipe 上的 JSON。

### 5.1 会话生命周期

1. extension 为当前文档打开或恢复一个操作会话。
2. extension 采集 `ContextSnapshot`。
3. sidecar 针对当前应用和目标检索候选能力。
4. sidecar 返回 `ExecutionPlan`；如果不需要操作，也可以只返回 `DirectAnswer`。
5. extension 按步骤校验并执行计划。
6. extension 在每一步后发出 `ObservationReport`。
7. sidecar 决定继续、重规划、请求审批，或者停止。

### 5.2 核心消息类型

Extension 发给 sidecar：

- `HandshakeRequest`
- `ChatRequest`
- `CapabilitySearchRequest`
- `StepExecutionResult`
- `ObservationReport`
- `ApprovalDecision`
- `CancelRequest`

Sidecar 发给 extension：

- `HandshakeResponse`
- `ExecutionPlan`
- `DirectAnswer`
- `ApprovalRequest`
- `PlanRevision`
- `ErrorResponse`
- `StreamChunk`

### 5.3 `ExecutionPlan` 结构

```json
{
  "type": "ExecutionPlan",
  "sessionId": "sess-123",
  "goal": "Create a chart from the selected range and place it below the table.",
  "steps": [
    {
      "stepId": "step-1",
      "capabilityId": "Calc.CreateChartFromSelection",
      "descriptorHash": "sha256:...",
      "parameters": {
        "chart_type": "column"
      },
      "targetScope": "selection",
      "approvalMode": "explicit",
      "expectedObservation": {
        "probe": "calc.chart_count_delta",
        "comparison": "equals",
        "value": 1
      },
      "onFailure": "replan"
    }
  ]
}
```

### 5.4 `ObservationReport` 结构

```json
{
  "type": "ObservationReport",
  "sessionId": "sess-123",
  "stepId": "step-1",
  "outcome": "satisfied",
  "preconditions": [
    {
      "probe": "calc.has_selection",
      "status": "passed"
    }
  ],
  "postconditions": [
    {
      "probe": "calc.chart_count_delta",
      "status": "passed",
      "actual": 1,
      "expected": 1
    }
  ],
  "summary": "A chart was created below the selected range."
}
```

## 6. 能力目录规格

每个描述符都必须包含这些字段：

- `id`：稳定 capability id
- `version`：描述符版本号
- `app`：应用范围，比如 `writer`、`calc`、`impress`、`draw`、`math`、`base`、`app`
- `title`：给人看的短名称
- `description`：给 planner 用的描述
- `intent_tags`：可检索的意图标签
- `examples`：用于检索和提示的自然语言示例
- `parameters`：类型化输入 schema
- `binding`：`uno-dispatch`、`uno-routine`、`document-api`、`composite-plan`
- `safety`：安全等级、默认审批方式、允许范围和大范围阈值
- `preconditions`：执行前必须通过的探针
- `postconditions`：执行后必须通过的探针
- `undo`：撤销分组标签或补偿说明
- `audit`：审计分类和日志提示

### 6.1 绑定规则

- `uno-dispatch` 绑定到白名单中的 dispatch alias 或目录自带的 `.uno:` 命令。
- `uno-routine` 绑定到 extension 里的类型化执行函数。
- `document-api` 绑定到更高层 LibreOffice API 例程，适用于单纯 dispatch 不够的情况。
- `composite-plan` 由目录编译成固定的低层步骤序列。

### 6.2 编译器输出

编译器必须生成：

- descriptor hash manifest
- extension capability registry
- extension safety matrix
- execution binding map
- sidecar retrieval index
- 可直接供 prompt 使用的能力摘要
- 文档表格和漂移测试

如果 sidecar 发来的 `descriptorHash` 和本地 manifest 不一致，运行时必须拒绝执行该步骤。

## 7. Planner 规格

sidecar 的规划引擎拆成三块：检索、组合、评估。

### 7.1 检索

输入：

- 应用类型
- 当前上下文快照
- 用户目标
- 策略约束

检索数据来源：

- 描述符标题和描述
- intent tags
- examples
- app 范围
- safety class
- 参数名

检索规则：

- 不能再用手写关键词路由器来决定最终能力集合
- 可以按 app 或策略做硬过滤，但不能维护第二套手写工具列表
- 检索返回的是一个有边界的候选集，而不是把整本目录全塞给 planner

### 7.2 计划生成

planner 规则：

- 不允许编造 capability id
- 不允许编造原始 UNO 命令
- 每一步都必须带 `descriptorHash`
- 每个写步骤都必须带 `expectedObservation`
- 每一步都必须声明 `onFailure`
- 单轮默认计划长度必须有上限，并可配置

### 7.3 评估和重规划

每收到一次 `ObservationReport`，评估器只能做以下几种决策：

- 继续下一步
- 调整当前目标的参数
- 请求更大范围的用户审批
- 停止并返回失败摘要

## 8. 执行引擎规格

extension 的执行引擎按“每次只执行一步”的方式工作。

### 8.1 执行前校验

必须检查：

- descriptor hash 是否匹配本地 manifest
- capability 是否存在于生成的 registry 中
- 参数是否符合生成的 schema
- 请求范围是否合法
- 审批要求是否已经满足
- 前置探针是否通过

### 8.2 单步执行顺序

执行顺序：

1. 打开 undo group
2. 解析 binding
3. 执行 UNO dispatch 或类型化 routine
4. 收集原始执行结果
5. 运行后置探针
6. 发出 `ObservationReport`
7. 关闭 undo group，并写入审计结果

### 8.3 `App.ExecuteUnoCommand`

`App.ExecuteUnoCommand` 是通用 dispatch 执行的一级能力，不再只是占位符。

允许的参数形状：

- `dispatchAlias`，用于常见目录命令
- 可选的类型化 `arguments`
- 可选 `targetScope`
- 必填的预期观察信息

规则：

- 原始 `.uno:` 字符串可以存在于目录元数据里，但用户或模型输入不能绕过目录直接传命令
- 每条命令路径都必须经过策略、前置条件、后置条件三层检查
- 失败时返回的是结构化观察不匹配，而不是含糊的布尔结果

## 9. 观察引擎规格

观察引擎负责把“运行结果证据”变成“下一步控制反馈”。

### 9.1 快照与探针

探针家族包括：

- 选区探针
- 文档结构探针
- 格式探针
- 对象计数探针
- 光标或插入点探针
- 各应用特有探针，比如图表数量、幻灯片数量、公式文本等

### 9.2 观察结果类型

- `satisfied`
- `unchanged`
- `partial`
- `failed`
- `unknown`

`unknown` 只允许在探针本身不可用时出现，不能拿来替代“目录里没有写后置检查”。

### 9.3 重规划触发条件

sidecar 必须从观察结果里回答这些问题：

- 这一步有没有改到目标对象
- 是否改得过多
- 是否应该重试同一步
- 是否应该换一种拆解方式继续目标

## 10. 安全与审批模型

安全来自“目录数据 + 运行时检查”的组合。

| 安全等级 | 例子 | 默认审批 | 运行时关卡 |
|---|---|---|---|
| `read-only` | 读取选区、解释公式 | 自动执行 | 范围校验 |
| `targeted-format` | 样式、对齐、加粗 | 自动执行 | 前置条件 + 后置条件 |
| `targeted-write` | 改写选区、插入公式 | 预览或按策略审批 | 前置条件 + 后置条件 + 撤销 |
| `structural-write` | 建图表、建幻灯片、插表格 | 明确审批 | 前置条件 + 后置条件 + 审计 |
| `destructive-or-wide` | 删对象、覆盖大范围内容 | 带范围摘要的明确确认 | 前置条件 + 后置条件 + 用户确认 |

像“影响多少单元格、多少段落、多少页/幻灯片”这样的阈值，必须放在目录或编译器生成产物里，不能散落在不同模块的手写条件中。

## 11. 模块规格

### 11.1 `shared/src/loaia_shared`

交付内容：

- 能力描述符 schema
- 编译器和 manifest builder
- 共享传输和计划 schema
- 生成产物契约

### 11.2 `extension/src/loaia`

交付内容：

- 快照和探针模块
- 带执行前校验与观察环节的执行引擎
- 对生成 capability registry 的消费
- 审批运行时
- 审计和历史集成

### 11.3 `sidecar/src/loaia_sidecar`

交付内容：

- 轻量 transport server
- 检索引擎
- planner 和 evaluator
- 会话编排器
- 使用生成能力摘要的 provider 适配层

### 11.4 `scripts/` 与测试

交付内容：

- 目录生成命令
- 漂移校验命令
- 索引构建命令
- 描述符校验、策略编译、执行前校验、观察评估的单元测试
- 操作层端到端集成测试和 live test

## 12. 推进顺序

### Phase 0：盘点并冻结现有表面

- 列出当前所有 capability id
- 列出当前 registry、whitelist 和 planner 列表
- 停止继续扩张手写能力表面

### Phase 1：先做目录编译器

- 定义描述符 schema
- 把现有 Writer、Calc、Impress 的 action id 迁进目录
- 生成 manifest 和 registry 输出

### Phase 2：先迁执行，再迁规划

- 让 extension 通过生成产物完成校验
- 替换重复的安全检查
- 打通 `App.ExecuteUnoCommand`

### Phase 3：迁 planner 主路径

- 构建检索索引
- 把 provider prompt 改成“基于候选能力摘要”
- 删除主路径中的关键词路由逻辑

### Phase 4：强制观察闭环

- 给所有写能力补上后置探针
- 把观察结果回灌到 evaluator 和会话历史

### Phase 5：扩展应用 pack

- 补齐 Draw、Math、Base 和 app-global 覆盖
- 增加结构化多步能力

## 13. 验收测试

完成这次重构，至少要有这些检查：

- 目录校验测试
- 生成 registry 的漂移测试
- planner 契约测试，确保不能编造 capability id
- executor 针对 schema、策略、前置条件、后置条件的测试
- `App.ExecuteUnoCommand` 的 live test
- 带观察反馈的多步端到端计划测试
