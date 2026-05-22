# How to Install and Use the AI Agent in LibreOffice

Simplified Chinese version: [Howto-Install-Use-in-Libreoffice.zh-CN.md](./Howto-Install-Use-in-Libreoffice.zh-CN.md)

## Prerequisites

- **LibreOffice 26** (Windows), installed at the default path
- **Python 3.11+** (system Python, used to run the sidecar process)
- An **API key** for a supported provider:
  - [OpenRouter](https://openrouter.ai/) (remote) — or
  - A local OpenAI-compatible endpoint (Ollama, vLLM, LM Studio, etc.)

## 1. Build the Extension Package (.oxt)

Open PowerShell in the project directory and run:

```powershell
cd c:\AI\intel-ai\libreoffice\libreoffice-ai-agent
.\scripts\build_oxt.ps1
```

This produces the extension package at `dist/libreoffice-ai-agent.oxt`.

## 2. Install the Extension into LibreOffice

**Option A — Using the dev install script (recommended for development):**

```powershell
.\scripts\dev_install_oxt.ps1
```

**Option B — Using unopkg directly:**

```powershell
& "C:\Program Files\LibreOffice\26\program\unopkg.exe" add -f dist\libreoffice-ai-agent.oxt
```

**Option C — Via LibreOffice UI:**

1. Open LibreOffice
2. Go to **Tools → Extension Manager**
3. Click **Add…** and select `dist/libreoffice-ai-agent.oxt`
4. Restart LibreOffice when prompted

## 3. Configure the API Key

Create a `.env` file at the workspace root (`c:\AI\intel-ai\libreoffice\.env`):

```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
LOAIA_DEFAULT_PROVIDER=openrouter
LOAIA_DEFAULT_MODEL=openai/gpt-4.1-mini
```

### Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | Yes (for OpenRouter) | Your OpenRouter API key |
| `LOAIA_DEFAULT_PROVIDER` | No | Default provider: `openrouter` or `openai-compatible` |
| `LOAIA_DEFAULT_MODEL` | No | Default model ID, e.g. `openai/gpt-4.1-mini` |
| `LOAIA_LOCAL_ENDPOINT_URL` | No | URL for local OpenAI-compatible endpoint |
| `LIBREOFFICE_PROGRAM_PATH` | No | Custom LibreOffice program directory path |

The API key can also be stored in **Windows Credential Manager** (the sidecar checks it as a fallback).

## 4. Start the Sidecar Process

The sidecar is the local broker that handles AI provider communication:

```powershell
.\scripts\run_sidecar.ps1
```

It listens on the named pipe `\\.\pipe\loaia-sidecar`.

> **Note:** The extension attempts to auto-start the sidecar when it first tries to connect. Manual start is only needed if auto-start fails or for development.

## 5. Using the AI Sidebar

### Open the Sidebar

1. Launch LibreOffice and open any document (Writer, Calc, Impress, Draw, or Math)
2. The AI sidebar panel should appear automatically
3. If not visible: **View → Sidebar** (or press `Ctrl+F5`), then select the AI panel

### Basic Workflow

1. **Select content** in your document:
   - Writer: select text
   - Calc: select a cell or range
   - Impress/Draw: select a shape with text
   - Math: the formula is captured automatically
2. **Type a prompt** in the sidebar input box
3. **Press Enter** or click the Send button
4. The AI responds in one of three ways:

### Response Types

| Type | What Happens | Example Prompts |
|------|-------------|-----------------|
| **Direct Answer** | AI answers without changing the document | "Summarize this", "Explain this formula", "What does this mean?" |
| **Safe Formatting** | Formatting applied immediately (no preview needed) | "Make this bold", "Center this", "Apply heading 1" |
| **Content Edit** | Shows a preview; click **Approve** to apply | "Rewrite this more formally", "Insert a SUM formula for A1:A10" |

### Configure Settings

In the sidebar's Settings section you can change:
- **Provider** — switch between `openrouter` and `openai-compatible`
- **Model** — change the model ID
- **API Key status** — shows whether the key is configured

## Supported Applications

| Application | Direct Answer | Safe Formatting | Content Edit (Preview + Approve) |
|-------------|:---:|:---:|:---:|
| **Writer** | ✅ | ✅ Bold, italic, underline, headings, bullets, alignment | ✅ Rewrite / insert text |
| **Calc** | ✅ | ✅ Bold, italic, alignment, number formats | ✅ Insert formula |
| **Impress** | ✅ | ✅ Bold, italic, bullets, alignment | ✅ Rewrite shape text |
| **Draw** | ✅ | ✅ Bold, italic, underline, alignment | ✅ Rewrite shape text |
| **Math** | ✅ | — | ✅ Rewrite formula |
| **Base** | ✅ | — | — |

## Troubleshooting

| Symptom | Solution |
|---------|----------|
| "Sidecar connection failed" | Run `.\scripts\run_sidecar.ps1` manually; check that no other sidecar is already running |
| "API key is not configured" | Set `OPENROUTER_API_KEY` in `.env` or Windows Credential Manager |
| Sidebar not visible | View → Sidebar (`Ctrl+F5`); ensure extension is installed in Extension Manager |
| "Sidebar actions require a supported LibreOffice document" | Open a supported document type (Writer/Calc/Impress/Draw/Math) |
| Math formula not captured | Ensure the Math editor has a formula entered (not a blank document) |

## Uninstall

```powershell
& "C:\Program Files\LibreOffice\26\program\unopkg.exe" remove libreoffice-ai-agent.oxt
```

Or via **Tools → Extension Manager → select the extension → Remove**.
