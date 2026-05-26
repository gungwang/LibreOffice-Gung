<p align="center">
  <img src="https://img.shields.io/badge/LibreOffice-26-green?logo=libreoffice" alt="LibreOffice 26"/>
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/License-MPL--2.0-orange" alt="License MPL-2.0"/>
  <img src="https://img.shields.io/badge/status-operation%20layer%20refactor-yellowgreen" alt="Status operation layer refactor"/>
</p>

# 🚀 LibreOffice AI Agent（智能助手）

**一个开源的 LibreOffice AI 副驾驶** — 为 Writer（文档）、Calc（表格）、Impress（演示）和 Draw（绘图）提供智能文档操作能力。

> 类似「微软 365 Copilot」，但完全开源、隐私优先、可以在本地运行。

[English Version](./README.md)

---

## 操作层重构状态

这个仓库正在围绕“能力目录（capability catalog，统一记录能力定义的目录）是唯一真相来源”进行重构。以后规划、执行、安全策略和文档表格，都尽量从同一份能力描述生成。

这次优先重做的是控制模型，不是界面外观。重构的核心变化包括：

- 用共享的生成产物替代 extension 和 sidecar 里重复维护的注册表
- 用统一的执行运行时处理 UNO dispatch、UNO routine 和 document API
- 把操作前后观察（observation，用来确认执行结果的探针检查）变成强制环节
- 让 sidecar 根据观察结果评估并在边界内重规划，而不是继续依赖关键词表

关键设计文档：

- [操作层重构计划](./docs/libreoffice-ai-agent-operation-layer-refactor-plan.zh-CN.md)
- [操作层架构](./docs/libreoffice-ai-agent-operation-layer-architecture.zh-CN.md)
- [操作层设计规格](./docs/libreoffice-ai-agent-operation-layer-design-spec.zh-CN.md)

---

## ✨ 功能介绍

LibreOffice AI Agent 在 LibreOffice 中添加一个智能侧边栏，能够理解自然语言并执行真实的文档操作 — 无需复制粘贴，无需手动格式化。

| 你说的话... | AI 助手执行的操作... |
|---|---|
| "加粗并改成红色" | 通过 UNO 调度（dispatch）应用粗体 + 红色字体 |
| "改为一级标题" | 应用「标题 1」段落样式 |
| "翻译成英文" | 将选中文本替换为翻译结果 |
| "插入一个 5×3 的表格" | 创建 5 行 3 列的表格 |
| "改成更正式的语气" | 用正式语气重写选中文本 |
| "右对齐，双倍行距" | 设置右对齐 + 2.0 倍行距 |

所有格式操作都通过 LibreOffice 原生的 **UNO API** 执行，不依赖脆弱的文本替换。操作层重构不会改变这个基本能力，但会把规划和执行改成更明确、更容易验证的控制路径。

---

## 🏗️ 架构方向

```
┌────────────────────────────────────────────────────────┐
│ 共享能力目录                                            │
│ • 应用能力包 • 安全元数据 • 生成的文档表和索引           │
└───────────────┬───────────────────────────────┬────────┘
                │ 生成 extension 运行时产物      │ 生成 planner 输入
┌───────────────▼──────────────────┐   ┌────────▼──────────────────────────┐
│ LibreOffice Extension 执行层     │   │ Sidecar 编排层                    │
│ • snapshot（快照）               │   │ • session state（会话状态）       │
│ • preflight（预检查）            │   │ • retrieval / composition         │
│ • bindings + execution engine    │   │ • evaluation / bounded replan     │
│ • observe / approval / undo      │   │ • provider abstraction            │
└───────────────┬──────────────────┘   └────────┬──────────────────────────┘
                │ 命名管道 / Socket             │ HTTPS
┌───────────────▼──────────────────┐   ┌────────▼─────────┐
│ LibreOffice 应用                  │   │ AI 供应商         │
│ Writer / Calc / Impress / Draw   │   │ OpenRouter       │
│ Math / Base / App 全局能力       │   │ OpenAI 兼容      │
└──────────────────────────────────┘   │ Anthropic        │
                                        │ Gemini           │
                                        └──────────────────┘
```

**这次重构的重点：**
- 🔒 **能力目录优先** — 用一份目录生成运行时 manifest、安全信息和文档表格
- 🧭 **统一执行路径** — schema 校验、策略校验、范围校验、binding、观察、undo 都走同一层
- 👀 **观察成为强制步骤** — 写操作不再只看异常文字，也要看可复用探针返回的结果
- 🧩 **planner 改成检索驱动** — sidecar 看到的是有边界的能力摘要，不再靠关键词表硬路由
- ⚡ **保留原生 UNO 行为** — 实际文档操作仍然通过 LibreOffice 原生 API 执行

---

## 🛠️ 能力包与覆盖范围

现有的工具栏和文档操作，正在迁移到一组“能力包（pack）”中。每个能力包都使用同一种描述符 schema 和同一套执行契约，这样 Writer、Calc、Impress、Draw、Math、Base 以及 App 全局能力都可以沿着同一条路径扩展，而不是继续维护多份手写注册表。

<details>
<summary><b>Writer 能力包（80+ 能力）</b></summary>

- **字符格式**：粗体、斜体、下划线、删除线、上标、下标、阴影、轮廓、小型大写
- **大小写转换**：全部大写、全部小写、标题大小写、句首大写、切换大小写
- **对齐方式**：左对齐、居中、右对齐、两端对齐
- **列表**：项目符号列表、编号列表
- **间距**：行距（1.0/1.5/2.0）、段前段后间距、缩进
- **字体**：字号（增大/减小/指定值）、字体名称（任意字体）、颜色（7 种预设 + 自定义）
- **文本高亮**：黄色、绿色、红色、蓝色、无高亮
- **样式**：标题 1-3、默认样式、清除格式
- **插入**：分页符、分栏符、批注、书签、页码、日期/时间、超链接、图片、脚注、尾注、页眉、页脚
- **编辑**：撤销、重做、全选、查找替换、字数统计、拼写检查、格式刷

</details>

<details>
<summary><b>Calc 能力包（40+ 能力）</b></summary>

- **格式**：粗体、斜体、下划线、删除线、字体颜色、背景颜色
- **对齐**：左对齐、居中、右对齐、顶端、居中、底端、自动换行
- **数字格式**：货币、百分比、科学记数法、增加/减少小数位
- **单元格**：合并、插入/删除行列
- **数据**：升序排列、降序排列、自动筛选、冻结窗格、自动求和
- **插入**：图表、函数

</details>

<details>
<summary><b>Impress 与 Draw 能力包（30+ 能力）</b></summary>

- **格式**：粗体、斜体、下划线、删除线、字号、字体颜色
- **对齐**：左对齐、居中、右对齐、两端对齐
- **幻灯片**：新建、复制、删除、开始放映
- **插入**：图片、文本框、形状
- **绘图**：清除格式、编号

</details>

这次重构还会补齐 **Math**、**Base** 和 **App 全局能力包**，例如通过生成 manifest 统一驱动的 UNO 命令执行。

---

## 🚀 快速上手

### 前置要求

- **LibreOffice 26**（Windows）— [下载地址](https://www.libreoffice.org/download/)
- **Python 3.11+** — 用于运行侧车进程
- **AI API 密钥** — 推荐 [OpenRouter](https://openrouter.ai/)（有免费额度）

### 安装步骤

```powershell
# 克隆仓库
git clone https://github.com/gungwang/LibreOffice-Gung.git
cd LibreOffice-Gung/libreoffice-ai-agent

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入你的 OPENROUTER_API_KEY

# 构建扩展
pwsh -File scripts/build_oxt.ps1

# 安装到 LibreOffice
& "C:\Program Files\LibreOffice\26\program\unopkg.exe" add dist/libreoffice-ai-agent.oxt

# 启动侧车进程
pwsh -File scripts/run_sidecar.ps1
```

### 使用方法

1. 打开 LibreOffice Writer（或 Calc / Impress）
2. AI 侧边栏自动出现
3. 选中文本，输入你的需求
4. AI 提出修改建议 → 你确认或编辑 → 即时应用

---

## 🧪 测试

```powershell
# Sidecar 质量检测（30 项测试 — 关键词路由、格式工具、工具建议）
python scripts/qa_test.py

# UI 集成测试（60 项测试 — 对真实 LibreOffice 执行 UNO 调度命令）
python scripts/qa_ui_test.py
```

全部 90 项测试在 Windows + LibreOffice 26 环境下通过。

---

## 📁 项目结构

```
libreoffice-ai-agent/
├── extension/                    # LibreOffice 扩展（.oxt 包）
│   └── src/loaia/
│       ├── execution/            # 通用执行运行时、预检查、binding、观察
│       ├── snapshot/             # 各应用的上下文快照与探针
│       ├── history/              # 会话与审计历史
│       └── broker/               # extension 侧通信与协调
├── sidecar/                      # 本地 AI 代理进程
│   └── src/loaia_sidecar/
│       ├── orchestrator/         # 会话引擎、评估器、有限重规划
│       ├── planner/              # 检索、组合、提示构建
│       └── providers/            # 模型供应商适配层
├── shared/                       # 共享 schema 与能力模型
│   └── src/loaia_shared/
│       ├── schema/               # 共享请求/响应模型
│       └── capabilities/         # 目录、编译器、manifest、生成表格
├── scripts/                      # 构建、测试、验证脚本
└── docs/                         # 重构计划、架构、设计规格
```

这里展示的是操作层重构的目标结构。当前仓库里仍然会同时存在一些迁移阶段的旧模块和新目标模块。

---

## 🗺️ 路线图

- [x] Extension + sidecar MVP，已能驱动真实 UNO 执行
- [x] Writer、Calc、Impress、Draw 的基础能力覆盖
- [x] 针对真实 UNO 调度路径的 UI 集成测试
- [ ] 让能力目录成为唯一真相来源
- [ ] 生成执行 manifest 和安全矩阵
- [ ] 为每个写能力补齐快照与观察探针
- [ ] 把 sidecar 编排逻辑从大而全的 server 中拆出来
- [ ] 做成基于检索的 planner 和有限重规划
- [ ] 补齐 Math、Base 和 App 全局能力包
- [ ] 支持 macOS 和 Linux
- [ ] 支持本地大模型（Ollama、llama.cpp）

---

## 🤝 参与贡献

欢迎贡献！本项目在适用的地方遵循 LibreOffice 编码规范。

1. Fork → 新建分支 (`feature/my-feature`) → 提交 → 发起 PR
2. 提交前运行 `python scripts/qa_test.py` 和 `python scripts/qa_ui_test.py`
3. 遵循 [Karpathy 准则](.github/instructions/karpathy-guidelines.instructions.md)：简洁优先、精准修改、明确假设

---

## 📄 许可证

本项目基于 [Mozilla Public License 2.0](./core/COPYING.MPL) 许可。

---

<p align="center">
  <b>为开源办公套件社区用 ❤️ 构建</b><br>
  <sub>让 AI 驱动的文档编辑人人可用 — 无需订阅付费。</sub>
</p>
