<p align="center">
  <img src="https://img.shields.io/badge/LibreOffice-26-green?logo=libreoffice" alt="LibreOffice 26"/>
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/License-MPL--2.0-orange" alt="License MPL-2.0"/>
  <img src="https://img.shields.io/badge/version-0.1.9-brightgreen" alt="Version 0.1.9"/>
</p>

# 🚀 LibreOffice AI Agent（智能助手）

**一个开源的 LibreOffice AI 副驾驶** — 为 Writer（文档）、Calc（表格）、Impress（演示）和 Draw（绘图）提供智能文档操作能力。

> 类似「微软 365 Copilot」，但完全开源、隐私优先、可以在本地运行。

[English Version](./README.md)

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

所有格式操作都通过 LibreOffice 原生的 **UNO API** 即时执行 — 不是通过脆弱的文本替换。

---

## 🏗️ 架构设计

```
┌─────────────────────────────────────────────┐
│        LibreOffice (Writer/Calc/Impress)     │
│  ┌───────────────────────────────────────┐  │
│  │  AI 侧边栏扩展 (.oxt)                │  │
│  │  • 上下文提取（选中文本）              │  │
│  │  • 工具执行（160+ UNO 命令）           │  │
│  │  • 预览/确认工作流                     │  │
│  └────────────────┬──────────────────────┘  │
└───────────────────┼─────────────────────────┘
                    │ 命名管道 / Socket
┌───────────────────┼─────────────────────────┐
│  本地 Sidecar     ▼                         │
│  （侧车进程 — AI 逻辑独立运行）              │
│  • 意图分类                                  │
│  • 工具建议与规划                             │
│  • 流式响应                                  │
│  • AI 供应商抽象层                            │
└───────────────────┬─────────────────────────┘
                    │ HTTPS
          ┌─────────┴─────────┐
          │  AI 供应商         │
          │  • OpenRouter     │
          │  • OpenAI 兼容    │
          │  • Anthropic      │
          │  • Gemini         │
          └───────────────────┘
```

**核心设计理念：**
- 🔒 **隐私优先** — 仅发送选中文本；完整文档永远不会离开你的电脑
- 🏠 **本地侧车** — AI 逻辑在 LibreOffice 之外独立运行，保证稳定性和安全性
- 🔌 **供应商无关** — 可切换 OpenRouter、本地大模型（LLM）或任何 OpenAI 兼容 API
- ⚡ **原生 UNO 调度** — 格式命令以原生速度执行，不通过文本黑科技

---

## 🛠️ 160+ 工具栏工具

Writer、Calc、Impress、Draw 中的每个工具栏按钮都已映射到 AI 代理：

<details>
<summary><b>Writer 文档（80+ 工具）</b></summary>

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
<summary><b>Calc 表格（40+ 工具）</b></summary>

- **格式**：粗体、斜体、下划线、删除线、字体颜色、背景颜色
- **对齐**：左对齐、居中、右对齐、顶端、居中、底端、自动换行
- **数字格式**：货币、百分比、科学记数法、增加/减少小数位
- **单元格**：合并、插入/删除行列
- **数据**：升序排列、降序排列、自动筛选、冻结窗格、自动求和
- **插入**：图表、函数

</details>

<details>
<summary><b>Impress 演示 & Draw 绘图（30+ 工具）</b></summary>

- **格式**：粗体、斜体、下划线、删除线、字号、字体颜色
- **对齐**：左对齐、居中、右对齐、两端对齐
- **幻灯片**：新建、复制、删除、开始放映
- **插入**：图片、文本框、形状
- **绘图**：清除格式、编号

</details>

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
├── extension/          # LibreOffice 扩展（.oxt 包）
│   ├── oxt/            # OXT 打包配置（XML 文件）
│   └── src/loaia/      # Python 扩展代码
│       └── actions/    # 工具执行器（UNO 调度映射表）
├── sidecar/            # 本地 AI 代理进程
│   └── src/loaia_sidecar/
│       └── server.py   # 意图分类 + 工具规划
├── shared/             # 共享数据模型（Pydantic 模型）
├── scripts/            # 构建、测试、验证脚本
└── docs/               # 架构和设计文档
```

---

## 🗺️ 路线图

- [x] Writer 全部工具栏支持（v0.1.9）
- [x] Calc / Impress / Draw 基础支持
- [x] UI 集成测试套件（60 项 UNO 调度测试）
- [ ] macOS 和 Linux 支持
- [ ] 本地大模型支持（Ollama、llama.cpp）
- [ ] 多轮对话上下文
- [ ] 文档级操作（摘要、大纲生成）
- [ ] 从大纲生成演示文稿
- [ ] 电子表格公式辅助

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
