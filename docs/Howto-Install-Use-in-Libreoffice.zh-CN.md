# 如何在 LibreOffice 中安装和使用 AI Agent

English version: [Howto-Install-Use-in-Libreoffice.md](./Howto-Install-Use-in-Libreoffice.md)

## 前置条件

- **LibreOffice 26**（Windows 版），安装在默认路径即可
- **Python 3.11+**（系统 Python，用于运行 sidecar 进程）
- 一个支持的 AI 服务商的 **API 密钥**：
  - [OpenRouter](https://openrouter.ai/)（远程服务）— 或
  - 本地 OpenAI 兼容端点（如 Ollama、vLLM、LM Studio 等）

## 1. 构建扩展包（.oxt）

打开 PowerShell，进入项目目录后运行：

```powershell
cd c:\AI\intel-ai\libreoffice\libreoffice-ai-agent
.\scripts\build_oxt.ps1
```

构建完成后，扩展包位于 `dist/libreoffice-ai-agent.oxt`。

## 2. 将扩展安装到 LibreOffice

**方式 A — 使用开发安装脚本（开发时推荐）：**

```powershell
.\scripts\dev_install_oxt.ps1
```

**方式 B — 直接使用 unopkg 命令：**

```powershell
& "C:\Program Files\LibreOffice\26\program\unopkg.exe" add -f dist\libreoffice-ai-agent.oxt
```

**方式 C — 通过 LibreOffice 界面安装：**

1. 打开 LibreOffice
2. 菜单 **工具 → 扩展管理器**
3. 点击 **添加…**，选择 `dist/libreoffice-ai-agent.oxt`
4. 按提示重启 LibreOffice

## 3. 配置 API 密钥

在工作区根目录（`c:\AI\intel-ai\libreoffice\.env`）创建 `.env` 文件：

```env
OPENROUTER_API_KEY=sk-or-v1-你的密钥
LOAIA_DEFAULT_PROVIDER=openrouter
LOAIA_DEFAULT_MODEL=openai/gpt-4.1-mini
```

### 环境变量参考

| 变量名 | 是否必需 | 说明 |
|--------|----------|------|
| `OPENROUTER_API_KEY` | 是（使用 OpenRouter 时） | 你的 OpenRouter API 密钥 |
| `LOAIA_DEFAULT_PROVIDER` | 否 | 默认服务商：`openrouter` 或 `openai-compatible` |
| `LOAIA_DEFAULT_MODEL` | 否 | 默认模型 ID，如 `openai/gpt-4.1-mini` |
| `LOAIA_LOCAL_ENDPOINT_URL` | 否 | 本地 OpenAI 兼容端点的 URL |
| `LIBREOFFICE_PROGRAM_PATH` | 否 | 自定义 LibreOffice 程序目录路径 |

API 密钥也可以存储在 **Windows 凭据管理器**（Credential Manager）中，sidecar 会将其作为后备来源自动查找。

## 4. 启动 Sidecar 进程

Sidecar（侧车进程）是本地的中间层，负责与 AI 服务商通信：

```powershell
.\scripts\run_sidecar.ps1
```

它监听 Windows 命名管道（named pipe）`\\.\pipe\loaia-sidecar`。

> **注意：** 扩展在首次尝试连接时会自动启动 sidecar。仅在自动启动失败或开发调试时才需要手动启动。

## 5. 使用 AI 侧边栏

### 打开侧边栏

1. 启动 LibreOffice，打开任意文档（Writer、Calc、Impress、Draw 或 Math）
2. AI 侧边栏面板会自动显示
3. 如果未显示：菜单 **视图 → 侧边栏**（或按 `Ctrl+F5`），然后选择 AI 面板

### 基本工作流程

1. **选中内容**：
   - Writer：选择文本
   - Calc：选择单元格或范围
   - Impress/Draw：选择含文本的形状（shape）
   - Math：公式会自动捕获，无需手动选择
2. **在输入框中输入提示语**（prompt）
3. **按回车**或点击发送按钮
4. AI 会以三种方式之一进行响应：

### 响应类型

| 类型 | 行为 | 示例提示语 |
|------|------|-----------|
| **直接回答** | AI 回答问题，不修改文档 | "总结这段内容"、"解释这个公式"、"这是什么意思？" |
| **安全格式化** | 立即应用格式（无需预览） | "加粗"、"居中对齐"、"应用标题1" |
| **内容编辑** | 显示预览；点击 **批准** 后应用到文档 | "用更正式的语气改写"、"插入 A1 到 A10 的求和公式" |

### 设置配置

在侧边栏的"设置"（Settings）区域可以修改：
- **Provider（服务商）** — 在 `openrouter` 和 `openai-compatible` 之间切换
- **Model（模型）** — 修改模型 ID
- **API Key 状态** — 显示密钥是否已配置

## 支持的应用类型

| 应用 | 直接回答 | 安全格式化 | 内容编辑（预览+批准） |
|------|:---:|:---:|:---:|
| **Writer**（文档） | ✅ | ✅ 加粗、斜体、下划线、标题、列表、对齐 | ✅ 改写/插入文本 |
| **Calc**（表格） | ✅ | ✅ 加粗、斜体、对齐、数字格式 | ✅ 插入公式 |
| **Impress**（演示） | ✅ | ✅ 加粗、斜体、列表、对齐 | ✅ 改写形状文本 |
| **Draw**（绘图） | ✅ | ✅ 加粗、斜体、下划线、对齐 | ✅ 改写形状文本 |
| **Math**（公式） | ✅ | — | ✅ 改写公式 |
| **Base**（数据库） | ✅ | — | — |

## 常见问题排查

| 症状 | 解决方法 |
|------|----------|
| "Sidecar connection failed"（连接失败） | 手动运行 `.\scripts\run_sidecar.ps1`；检查是否已有其他 sidecar 在运行 |
| "API key is not configured"（密钥未配置） | 在 `.env` 文件或 Windows 凭据管理器中设置 `OPENROUTER_API_KEY` |
| 侧边栏不可见 | 视图 → 侧边栏（`Ctrl+F5`）；确认扩展已在扩展管理器中安装 |
| "Sidebar actions require a supported LibreOffice document" | 打开受支持的文档类型（Writer/Calc/Impress/Draw/Math） |
| Math 公式未捕获 | 确保 Math 编辑器中已输入公式（非空白文档） |

## 卸载

```powershell
& "C:\Program Files\LibreOffice\26\program\unopkg.exe" remove libreoffice-ai-agent.oxt
```

或通过 **工具 → 扩展管理器 → 选中扩展 → 删除**。
