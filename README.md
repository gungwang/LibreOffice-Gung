<p align="center">
  <img src="https://img.shields.io/badge/LibreOffice-26-green?logo=libreoffice" alt="LibreOffice 26"/>
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/License-MPL--2.0-orange" alt="License MPL-2.0"/>
  <img src="https://img.shields.io/badge/version-0.1.9-brightgreen" alt="Version 0.1.9"/>
</p>

# 🚀 LibreOffice AI Agent

**An open-source AI Copilot for LibreOffice** — bringing intelligent document assistance to Writer, Calc, Impress, and Draw.

> Think "Microsoft 365 Copilot", but open-source, privacy-first, and running entirely on your machine.

[简体中文版](./README.zh-CN.md)

---

## ✨ What It Does

LibreOffice AI Agent adds a smart sidebar to LibreOffice that understands natural language and executes real document operations — no copy-paste, no manual formatting.

| You say... | The Agent does... |
|---|---|
| "Make this bold and red" | Applies bold + red font color via UNO dispatch |
| "Change to heading 1" | Applies Heading 1 paragraph style |
| "Translate to Chinese" | Replaces selected text with translation |
| "Insert a 5×3 table" | Creates a table with 5 rows and 3 columns |
| "Make it more formal" | Rewrites selected text in formal tone |
| "Align right and double space" | Sets right alignment + 2.0 line spacing |

All formatting happens **instantly** through LibreOffice's native UNO API — not through fragile text manipulation.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│           LibreOffice (Writer/Calc/Impress)  │
│  ┌───────────────────────────────────────┐  │
│  │  AI Sidebar Extension (.oxt)          │  │
│  │  • Context extraction                 │  │
│  │  • Tool execution (160+ UNO commands) │  │
│  │  • Preview/Apply workflow             │  │
│  └────────────────┬──────────────────────┘  │
└───────────────────┼─────────────────────────┘
                    │ Named Pipe / Socket
┌───────────────────┼─────────────────────────┐
│  Local Sidecar    ▼                         │
│  • Intent classification                    │
│  • Tool proposal & planning                 │
│  • Streaming responses                      │
│  • Provider abstraction                     │
└───────────────────┬─────────────────────────┘
                    │ HTTPS
          ┌─────────┴─────────┐
          │  AI Providers     │
          │  • OpenRouter     │
          │  • OpenAI-compat  │
          │  • Anthropic      │
          │  • Gemini         │
          └───────────────────┘
```

**Key design decisions:**
- 🔒 **Privacy-first** — selection-only context; your full document never leaves your machine
- 🏠 **Local sidecar** — AI logic runs outside LibreOffice core for stability and security
- 🔌 **Provider-agnostic** — swap between OpenRouter, local LLMs, or any OpenAI-compatible API
- ⚡ **Native UNO dispatch** — formatting commands execute at native speed, not through text hacks

---

## 🛠️ 160+ Toolbar Tools

Every toolbar button in Writer, Calc, Impress, and Draw is mapped to the AI agent:

<details>
<summary><b>Writer (80+ tools)</b></summary>

- **Formatting**: Bold, Italic, Underline, Strikethrough, Superscript, Subscript, Shadow, Outline, Small Caps
- **Text Case**: Uppercase, Lowercase, Title Case, Sentence Case, Toggle Case
- **Alignment**: Left, Center, Right, Justify
- **Lists**: Bullets, Numbering
- **Spacing**: Line spacing (1.0/1.5/2.0), Paragraph spacing, Indentation
- **Font**: Size (increase/decrease/parametric), Name (any font), Color (7 presets + custom)
- **Highlighting**: Yellow, Green, Red, Blue, None
- **Styles**: Heading 1-3, Default, Clear Formatting
- **Insert**: Page Break, Column Break, Comment, Bookmark, Page Number, Date/Time, Hyperlink, Image, Footnote, Endnote, Header, Footer
- **Edit**: Undo, Redo, Select All, Find & Replace, Word Count, Spell Check, Format Paintbrush

</details>

<details>
<summary><b>Calc (40+ tools)</b></summary>

- **Formatting**: Bold, Italic, Underline, Strikethrough, Font Color, Background Color
- **Alignment**: Left, Center, Right, Top, Middle, Bottom, Wrap Text
- **Numbers**: Currency, Percent, Scientific, Increase/Decrease Decimals
- **Cells**: Merge, Insert/Delete Rows/Columns
- **Data**: Sort Ascending/Descending, AutoFilter, Freeze Panes, AutoSum
- **Insert**: Chart, Function

</details>

<details>
<summary><b>Impress & Draw (30+ tools)</b></summary>

- **Formatting**: Bold, Italic, Underline, Strikethrough, Font Size, Font Color
- **Alignment**: Left, Center, Right, Justify
- **Slides**: New Slide, Duplicate, Delete, Start Presentation
- **Insert**: Image, Text Box, Shape
- **Drawing**: Clear Formatting, Numbering

</details>

---

## 🚀 Quick Start

### Prerequisites

- **LibreOffice 26** (Windows) — [download](https://www.libreoffice.org/download/)
- **Python 3.11+** — for the sidecar process
- **An AI API key** — [OpenRouter](https://openrouter.ai/) recommended (free tier available)

### Install

```powershell
# Clone the repo
git clone https://github.com/gungwang/LibreOffice-Gung.git
cd LibreOffice-Gung/libreoffice-ai-agent

# Set up environment
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY

# Build the extension
pwsh -File scripts/build_oxt.ps1

# Install in LibreOffice
& "C:\Program Files\LibreOffice\26\program\unopkg.exe" add dist/libreoffice-ai-agent.oxt

# Start the sidecar
pwsh -File scripts/run_sidecar.ps1
```

### Usage

1. Open LibreOffice Writer (or Calc/Impress)
2. The AI sidebar appears automatically
3. Select text and type your request
4. The agent proposes changes → you approve or edit → applied instantly

---

## 🧪 Testing

```powershell
# Sidecar QA (30 tests — keyword routing, formatting, tool proposals)
python scripts/qa_test.py

# UI Integration (60 tests — real UNO dispatch against live LibreOffice)
python scripts/qa_ui_test.py
```

All 90 tests pass against LibreOffice 26 on Windows.

---

## 📁 Project Structure

```
libreoffice-ai-agent/
├── extension/          # LibreOffice extension (.oxt)
│   ├── oxt/            # OXT packaging assets (XML configs)
│   └── src/loaia/      # Python extension code
│       └── actions/    # Tool executor (UNO dispatch map)
├── sidecar/            # Local AI broker process
│   └── src/loaia_sidecar/
│       └── server.py   # Intent classification + tool planning
├── shared/             # Shared schemas (Pydantic models)
├── scripts/            # Build, test, and verification scripts
└── docs/               # Architecture and design documentation
```

---

## 🗺️ Roadmap

- [x] Writer full toolbar support (v0.1.9)
- [x] Calc/Impress/Draw basic support
- [x] UI integration test suite (60 UNO dispatch tests)
- [ ] macOS and Linux support
- [ ] Local LLM support (Ollama, llama.cpp)
- [ ] Multi-turn conversation context
- [ ] Document-wide operations (summarize, outline)
- [ ] Presentation generation from outline
- [ ] Spreadsheet formula assistance

---

## 🤝 Contributing

Contributions welcome! This project follows the LibreOffice coding conventions where applicable.

1. Fork → Branch (`feature/my-feature`) → Commit → PR
2. Run `python scripts/qa_test.py` and `python scripts/qa_ui_test.py` before submitting
3. Follow the [Karpathy Guidelines](.github/instructions/karpathy-guidelines.instructions.md): simplicity first, surgical changes, explicit assumptions

---

## 📄 License

This project is licensed under the [Mozilla Public License 2.0](./core/COPYING.MPL).

---

<p align="center">
  <b>Built with ❤️ for the open-source office suite community</b><br>
  <sub>Making AI-powered document editing accessible to everyone — no subscription required.</sub>
</p>