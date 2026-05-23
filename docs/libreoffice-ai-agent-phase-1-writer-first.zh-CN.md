# LibreOffice AI Agent 第一阶段 Writer 优先范围

## 目标

先把 Writer 路径做稳定，再考虑 Calc 或 Impress。

第一阶段完成的标准是：Windows 用户可以安装扩展，打开侧边栏，配置 provider 和 model，预览 Writer 改写，手动批准应用结果，在 provider 或 sidecar 出错时看到明确错误信息，并且在重启 LibreOffice 后仍然保留设置和最近对话上下文。

## 本阶段范围

- 只做 Writer 相关操作，包括直接回答，以及 ReplaceSelection 的预览和应用。
- 侧边栏提供 provider、model、API key 状态和常见错误状态。
- 扩展本地持久化设置和最近对话历史，重启 LibreOffice 后仍然可用。
- provider 驱动的 Writer 改写提案使用更可预测的结构化改写契约。
- 定义一组小型发布冒烟矩阵，用于打包或分享构建前快速验证。

## 暂不处理

- Calc 或 Impress 的编辑流程。
- 多文档编排、后台索引、全文自主编辑。
- 流式 UI 打磨、token 统计、遥测面板、复杂审计报表。
- 当前 Windows 验证路径之外的跨平台支持。

## 发版约束

- Writer 预览和应用必须继续保留人工批准步骤。
- provider 逻辑继续放在 sidecar 中。
- 扩展只持久化设置和最近历史所需的最小本地状态。
- 如果 sidecar 或 provider 不可用，侧边栏必须显示明确失败状态，不能静默降级。

## 发布冒烟矩阵

| 场景 | 要验证的内容 | 预期结果 |
| --- | --- | --- |
| 安装 | 构建 OXT，安装到干净 profile，并打开 Writer 侧边栏 | 侧边栏能打开，设置控件能显示 |
| 直接回答 | 提交一个不应该修改文档的问题 | 显示直接回答，不产生待批准提案 |
| 预览并应用 | 选中 Writer 文本，请求改写，再手动批准 | 先看到预览，批准后选中文本被更新 |
| Provider 失败 | 在缺少或无效凭据的情况下运行 | 侧边栏显示明确的 provider 错误状态 |
| Sidecar 失败 | sidecar 未启动或管道不可用时运行 | 侧边栏显示明确的传输错误状态 |
| 重启持久化 | 保存设置，发送一次请求，重启 LibreOffice | provider/model 设置和最近活动会恢复 |

## 延后扩展条件

在 Writer 路径的所有冒烟矩阵项都稳定通过之前，不启动 Calc 或 Impress 功能开发。只有当改写契约已经足够稳定，provider 驱动的提案在重复运行时也表现可预测，才进入下一轮扩展。