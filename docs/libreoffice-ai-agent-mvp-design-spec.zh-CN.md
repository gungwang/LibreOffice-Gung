# LibreOffice AI Agent MVP 设计规格

英文版: [libreoffice-ai-agent-mvp-design-spec.md](./libreoffice-ai-agent-mvp-design-spec.md)
相关架构文档: [libreoffice-ai-agent-architecture.zh-CN.md](./libreoffice-ai-agent-architecture.zh-CN.md)
相关仓库骨架文档: [libreoffice-ai-agent-repo-scaffold.zh-CN.md](./libreoffice-ai-agent-repo-scaffold.zh-CN.md)

## 1. 文档目的

这份文档是 LibreOffice AI Agent 第一版可运行产品的“可落地设计规格”。

前面的架构文档更偏方向和边界，这份文档更偏“怎么做第一版”。它的目标是把大的设计收敛成开发时可以直接照着实现的 MVP 方案。

这份规格主要回答：

- MVP 到底包含什么
- 扩展和侧车怎么分工
- 第一批用户可见流程是什么
- 扩展和侧车之间传什么消息
- Writer、Calc、Impress 第一批动作有哪些
- 审批规则、历史记录、设置、日志、验收标准分别是什么

## 2. MVP 发布目标

MVP 的发布目标是：

- 只支持 Windows
- 以 LibreOffice 扩展 + 本地侧车进程方式交付
- 覆盖 Writer、Calc、Impress
- 默认只发送当前选中内容给模型
- 同时支持远程 API 和本地 OpenAI 兼容模型服务
- 会话历史按“文档 + 当前 LibreOffice profile”保存

实现顺序仍然建议 Writer 优先，但这份 MVP 设计必须给 Calc 和 Impress 留出清晰扩展点，避免做完 Writer 后又重写整体结构。

## 3. 已确定的产品决策

- 安全的纯格式操作直接执行。
- 更大的内容修改必须先预览，再让用户确认。
- 宏生成和宏执行不在第一阶段范围内。
- API Key 由用户自己提供。
- 本地模型统一走 OpenAI 兼容接口。
- 侧车进程不能直接修改 LibreOffice 文档。
- 文档改动、审批、撤销和历史记录都由扩展端负责。

## 4. MVP 成功标准

只有当用户能稳定完成下面整条链路时，MVP 才算成功：

1. 在 LibreOffice 里打开 AI 侧边栏面板。
2. 选择 Provider 和模型。
3. 使用一个远程模型或一个本地 OpenAI 兼容模型。
4. 针对当前选区发起问题。
5. 收到直接答案或者结构化动作提案。
6. 安全格式操作会立即执行。
7. 更大的内容修改会先显示预览，再确认。
8. 修改后可以正常撤销。
9. 关闭并重新打开同一文档后，在同一个 LibreOffice profile 中能恢复对话历史。

## 5. 支持的用户场景

### Writer 场景

- 总结当前选中的段落。
- 把选中的段落改写成另一种语气。
- 把选中的多行文本变成项目符号列表。
- 对选中的段落应用 Heading 1、Heading 2、Heading 3。
- 对选区加粗、斜体、对齐。

### Calc 场景

- 解释选中单元格里的公式。
- 给选中区域建议并插入一个公式。
- 对选中区域应用安全数字格式。
- 根据当前选中区域创建图表。

### Impress 场景

- 改写当前选中的幻灯片文字。
- 把选中的要点整理成更清晰的大纲。
- 根据输入的大纲创建新幻灯片。
- 对当前幻灯片应用布局变更。

## 6. 用户体验规格

### 入口

MVP 至少要有一个稳定入口：

- AI 侧边栏 deck 和 panel

后续可选入口：

- 菜单项
- 工具栏按钮

### 侧边栏布局

面板必须包含下面几个区域：

1. 头部区域
- Provider 选择器
- 模型选择器
- 隐私范围提示
- broker 连接状态

2. 对话区域
- 用户消息
- 模型消息
- 动作卡片
- 审批卡片
- 错误提示条

3. 输入区域
- 输入框
- 发送按钮
- 流式输出期间的取消按钮

4. 可选底部区域
- 当前历史作用域提示
- 最近一次动作状态

### 面板状态

- 未连接
- 就绪
- 正在流式输出
- 等待审批
- 正在执行动作
- 完成
- 错误

### 交互流程

#### 只读回答流程

1. 用户先选中文档内容。
2. 用户提交问题。
3. 扩展把“只包含选区”的上下文发给侧车。
4. 侧车返回直接答案。
5. 扩展把答案显示出来，并写入历史记录。

#### 安全格式流程

1. 用户先选中内容。
2. 用户要求做格式操作。
3. 侧车返回一个“安全格式动作”提案。
4. 扩展检查这个动作是否在安全白名单里。
5. 如果在白名单里，扩展立即执行。
6. 扩展记录执行结果，并保留正常撤销能力。

#### 内容编辑流程

1. 用户选中内容。
2. 用户要求改写或插入内容。
3. 侧车返回带预览内容的结构化动作提案。
4. 扩展显示预览卡片。
5. 用户选择批准或拒绝。
6. 扩展执行已批准的动作，并记录结果。

#### 上下文升级流程

1. 用户的问题仅靠当前选区不够回答。
2. 侧车或扩展判断需要更大范围的上下文。
3. 扩展明确询问用户是否允许读取更大范围。
4. 用户同意或拒绝。
5. 只有得到同意后才继续。

## 7. 审批与安全策略

系统把动作分成四类。

| 动作类别 | 例子 | 自动执行 | 预览 | 明确确认 |
|---|---|---|---|---|
| 只读 | 总结选区、解释公式 | 是 | 否 | 否 |
| 安全纯格式 | 加粗、标题、项目符号、对齐、数字格式 | 是 | 否 | 否 |
| 内容编辑 | 改写段落、插入摘要、生成幻灯片文字 | 否 | 是 | 是 |
| 破坏性或大范围 | 大范围替换、覆盖式排序、删除内容 | 否 | 是 | 是 |

### 第一阶段安全格式白名单

Writer：

- `Writer.ToggleBold`
- `Writer.ToggleItalic`
- `Writer.ToggleUnderline`
- `Writer.ApplyHeading1`
- `Writer.ApplyHeading2`
- `Writer.ApplyHeading3`
- `Writer.ApplyBullets`
- `Writer.AlignLeft`
- `Writer.AlignCenter`
- `Writer.AlignRight`

Calc：

- `Calc.ToggleBold`
- `Calc.ToggleItalic`
- `Calc.AlignLeft`
- `Calc.AlignCenter`
- `Calc.AlignRight`
- `Calc.ApplyNumberFormatCurrency`
- `Calc.ApplyNumberFormatPercent`
- `Calc.ApplyNumberFormatDate`

Impress：

- `Impress.ToggleBold`
- `Impress.ToggleItalic`
- `Impress.ApplyBullets`
- `Impress.AlignLeft`
- `Impress.AlignCenter`
- `Impress.AlignRight`

不在这个白名单里的动作，在第一阶段都不能自动执行。

## 8. 运行时组件与边界

### LibreOffice 扩展

负责：

- 侧边栏 UI
- 文档上下文提取
- 动作校验与执行
- 用户审批提示
- Undo 分组
- 历史记录持久化
- 从 LibreOffice 侧管理 sidecar 生命周期

不负责：

- 各家 Provider 的具体适配逻辑
- 多种远程 API 直接调用细节

### 本地侧车

负责：

- Provider 适配器
- 模型选择
- 流式输出
- 意图路由
- 工具提案生成
- 提案前的策略检查

不负责：

- 直接改 LibreOffice 文档
- 用户审批 UI
- 在 LibreOffice profile 中保存历史记录

## 9. 通信与会话生命周期

### 通信方式

- Windows 命名管道

### 启动流程

1. 用户打开 AI 面板。
2. 扩展检查 sidecar 是否已运行。
3. 如果没有运行，扩展启动 sidecar。
4. 扩展通过命名管道建立连接。
5. 扩展发送握手请求。
6. sidecar 返回版本、能力和 Provider 可用性。

### 请求流程

1. 扩展构建请求信封。
2. sidecar 先返回流式片段，再返回一个最终结果信封。
3. 最终结果可能是：直接答案、工具提案列表、权限升级请求或错误。

### 取消流程

- 用户可以取消正在运行的请求。
- 扩展发送 `CancelRequest`。
- 如果 Provider 支持取消，sidecar 立即停止；如果不支持，sidecar 至少要丢弃后续晚到结果。

## 10. 请求与响应契约

第一版协议建议采用：

- JSON over named pipes

也就是：消息内容是 JSON，传输通道是命名管道。

### 核心请求信封

```json
{
  "type": "ChatRequest",
  "requestId": "req-123",
  "app": "writer",
  "document": {
    "canonicalUrl": "file:///C:/docs/example.odt",
    "profileId": "default"
  },
  "provider": "openai-compatible-local",
  "model": "qwen2.5-14b-instruct",
  "privacyScope": "selection-only",
  "context": {
    "selection": {
      "mimeType": "text/plain",
      "text": "Selected paragraph text"
    }
  },
  "userMessage": "Rewrite this in a professional tone.",
  "historySummary": []
}
```

### 最终结果类型

- `DirectAnswer`
- `ToolProposal`
- `ConsentRequest`
- `ErrorResponse`

### 工具提案结构

```json
{
  "type": "ToolProposal",
  "proposalId": "prop-456",
  "toolId": "Writer.ReplaceSelection",
  "safetyClass": "content-edit",
  "requiresApproval": true,
  "preview": {
    "summary": "Replace the selected paragraph with a rewritten version.",
    "before": "Original text",
    "after": "Rewritten text"
  },
  "arguments": {
    "replacementText": "Rewritten text"
  }
}
```

## 11. 上下文提取规则

### 默认规则

- 只发送当前选区给模型

### 没有选区时的行为

如果当前没有选中内容，扩展不能偷偷把整篇文档发出去。

它只能二选一：

- 提示用户先选择内容
- 明确请求用户授权读取更大范围

### 上下文升级选项

- 当前段落
- 当前单元格附近的区域
- 当前文本框或当前幻灯片文字区域
- 只有显式同意后，才允许整篇文档或整张工作表范围

### 上下文裁剪

- 尽量去掉无意义空白和格式噪声
- 不发送当前任务不需要的隐藏元数据
- 对超大选区做上限控制，超过时先征得同意

## 12. 第一批动作注册表

### Writer 动作

只读：

- `Writer.GetSelection`

安全纯格式：

- `Writer.ToggleBold`
- `Writer.ToggleItalic`
- `Writer.ToggleUnderline`
- `Writer.ApplyHeading1`
- `Writer.ApplyHeading2`
- `Writer.ApplyHeading3`
- `Writer.ApplyBullets`
- `Writer.AlignLeft`
- `Writer.AlignCenter`
- `Writer.AlignRight`

内容编辑：

- `Writer.ReplaceSelection`
- `Writer.InsertBelowSelection`

### Calc 动作

只读：

- `Calc.GetSelectedRange`
- `Calc.GetSelectedFormula`

安全纯格式：

- `Calc.ToggleBold`
- `Calc.ToggleItalic`
- `Calc.AlignLeft`
- `Calc.AlignCenter`
- `Calc.AlignRight`
- `Calc.ApplyNumberFormatCurrency`
- `Calc.ApplyNumberFormatPercent`
- `Calc.ApplyNumberFormatDate`

内容或结构编辑：

- `Calc.InsertFormulaInSelection`
- `Calc.CreateChartFromSelection`
- `Calc.SortSelectedRange`

### Impress 动作

只读：

- `Impress.GetSelectedText`

安全纯格式：

- `Impress.ToggleBold`
- `Impress.ToggleItalic`
- `Impress.ApplyBullets`
- `Impress.AlignLeft`
- `Impress.AlignCenter`
- `Impress.AlignRight`

内容或结构编辑：

- `Impress.ReplaceSelectedText`
- `Impress.CreateSlideFromOutline`
- `Impress.ApplyLayoutToCurrentSlide`

## 13. 历史记录存储规格

历史记录必须保存在 LibreOffice profile 中，建议使用 SQLite。

这里的 SQLite 可以理解为“本地单文件数据库”，适合这种按文档查询、按时间追加记录的场景。

建议位置：

- `<LibreOfficeProfile>/loaia/history.sqlite3`

建议表：

- `sessions`
- `messages`
- `events`

建议的会话主键：

- `profile_id`
- `canonical_document_url`
- `app_type`

### 应保存的内容

- 用户消息文本
- 模型回答文本
- 工具提案元数据
- 批准和拒绝事件
- 已执行动作元数据
- 使用的 Provider 和模型
- 时间戳

### 不应保存的内容

- 原始 API Key
- 默认情况下整篇文档快照
- 历史回放不需要的隐藏 Office 元数据

## 14. 设置与密钥存储

### 非敏感设置

建议保存在 profile 作用域的设置文件中，例如：

- `<LibreOfficeProfile>/loaia/settings.json`

包括：

- 默认 Provider
- 默认模型
- 本地端点 URL
- 隐私默认策略
- 是否自动应用格式动作
- 日志级别

### 敏感信息存储

远程 Provider 的 API Key 建议存到：

- Windows Credential Manager

扩展和 sidecar 应该只通过 Provider 逻辑名引用密钥，不能把密钥写进历史记录或日志。

## 15. 日志与审计

系统需要三类日志。

### 扩展日志

- UI 生命周期
- 动作校验
- 执行失败

### 侧车日志

- Provider 选择
- 请求路由
- 流式输出生命周期
- Provider 错误

### 审计日志

- 批准事件
- 拒绝事件
- 已执行动作
- 文档 URL 引用
- 使用的 Provider 和模型

建议审计日志位置：

- `<LibreOfficeProfile>/loaia/audit.jsonl`

## 16. 错误处理要求

MVP 必须明确处理下面这些故障。

### Sidecar 不可用

- UI 显示未连接状态
- 提供重新连接或重启选项

### Provider 鉴权失败

- 显示与该 Provider 相关的错误信息
- 不要丢掉用户刚输入的 prompt

### 本地端点不可达

- 显示可操作的本地端点错误
- 允许用户切换 Provider，而不需要重启 LibreOffice

### 非法工具提案

- 在本地直接拒绝该提案
- 写入违规日志
- 对用户显示通用、安全的失败提示

### Undo 失败

- 给出警告
- 仍然保留审计记录和动作结果详情

## 17. 验收标准

### Phase 0 验收

- 扩展能打开可见 AI 面板
- 扩展能启动并握手连接 sidecar
- mock provider 能返回一个直接答案
- 一个 Writer 安全格式动作能成功自动应用

### Phase 1 验收

- 一个远程 Provider 能端到端跑通
- 一个本地 OpenAI 兼容 Provider 能端到端跑通
- Writer 选区总结可用
- Writer 选区改写加预览审批可用
- 重新打开文档后能恢复按文档、按 profile 保存的历史
- Calc 至少支持一个只读场景和一个写入场景
- Impress 至少支持一个只读场景和一个写入场景
- 所有批准后的写操作都能通过正常用户工作流撤销

## 18. 明确不在范围内的事项

- 宏生成
- 宏执行
- 任意 shell 执行
- 任意文件系统工具
- 无限制 UNO 命令分发
- 不经审批的全文档自主改写
- 多用户协作同步
- 移动端或 LibreOfficeKit 部署

## 19. 第一阶段实现顺序

建议实现顺序如下：

1. 传输与握手
2. 侧边栏基础 UI
3. Writer 选区提取
4. 本地 mock provider
5. Writer 安全格式动作
6. Writer 改写预览
7. 设置与密钥存储
8. 历史记录存储
9. Calc 最小切片
10. Impress 最小切片

这个顺序的目的是先降低风险，再逐步满足“Writer + Calc + Impress 都覆盖”的产品要求。