<p align="center">
  <img src="https://img.shields.io/badge/LibreOffice-26-green?logo=libreoffice" alt="LibreOffice 26"/>
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/License-MPL--2.0-orange" alt="License MPL-2.0"/>
  <img src="https://img.shields.io/badge/status-operation%20layer%20refactor-yellowgreen" alt="Status operation layer refactor"/>
</p>

# 🚀 LibreOffice AI Agent

**An open-source AI Copilot for LibreOffice** — bringing intelligent document assistance to Writer, Calc, Impress, and Draw.

> Think "Microsoft 365 Copilot", but open-source, privacy-first, and running entirely on your machine.

[简体中文版](./README.zh-CN.md)

---

## Operation Layer Refactor

This repository is being refactored around a capability catalog as the single source of truth for planning, execution, safety policy, and generated documentation.

The immediate goal is a control-model rewrite, not a UI rewrite. The refactor replaces handwritten registries and keyword routing with:

- generated capability artifacts shared by the extension and the sidecar
- one policy-aware execution runtime for UNO dispatch, UNO routines, and document APIs
- required observation before and after mutating operations
- sidecar orchestration that can evaluate results and replan from evidence

Key design docs:

- [Operation layer refactor plan](./docs/libreoffice-ai-agent-operation-layer-refactor-plan.md)
- [Operation layer architecture](./docs/libreoffice-ai-agent-operation-layer-architecture.md)
- [Operation layer design specification](./docs/libreoffice-ai-agent-operation-layer-design-spec.md)

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

All formatting happens through LibreOffice's native UNO API instead of fragile text manipulation. The operation-layer refactor keeps that behavior, but moves planning and execution onto a more explicit and testable control path.

---

## 🏗️ Architecture Direction

```
┌────────────────────────────────────────────────────────┐
│ Shared Capability Catalog                              │
│ • app packs • safety metadata • generated docs/index   │
└───────────────┬───────────────────────────────┬────────┘
                │ generated runtime outputs     │ generated planner inputs
┌───────────────▼──────────────────┐   ┌────────▼──────────────────────────┐
│ LibreOffice Extension Runtime    │   │ Sidecar Orchestrator              │
│ • snapshot                       │   │ • session state                   │
│ • preflight                      │   │ • retrieval and composition       │
│ • bindings and execution engine  │   │ • evaluation and bounded replan   │
│ • observe, approval, undo        │   │ • provider abstraction            │
└───────────────┬──────────────────┘   └────────┬──────────────────────────┘
                │ named pipe / socket            │ HTTPS
┌───────────────▼──────────────────┐   ┌────────▼─────────┐
│ LibreOffice Apps                 │   │ AI Providers     │
│ Writer / Calc / Impress / Draw   │   │ OpenRouter       │
│ Math / Base / App-global actions │   │ OpenAI-compat    │
└──────────────────────────────────┘   │ Anthropic        │
                                        │ Gemini           │
                                        └──────────────────┘
```

**What changes with the refactor:**
- 🔒 **Capability catalog first** — one catalog generates runtime manifests, safety metadata, and docs tables
- 🧭 **Unified execution path** — schema checks, policy checks, scope checks, bindings, observation, and undo run through one operation layer
- 👀 **Observation is required** — mutating steps are validated with reusable probes instead of relying on exception text alone
- 🧩 **Planner becomes retrieval-driven** — the sidecar retrieves bounded capability summaries instead of routing from keyword tables
- ⚡ **Native UNO behavior stays** — document operations still execute through LibreOffice-native APIs

---

## 🛠️ Capability Packs and Coverage

The existing toolbar and document operations are being migrated into capability packs. Each pack uses the same descriptor schema and the same execution contract, so Writer, Calc, Impress, Draw, Math, Base, and app-global actions can expand without creating new handwritten registries.

<details>
<summary><b>Writer pack (80+ capabilities)</b></summary>

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
<summary><b>Calc pack (40+ capabilities)</b></summary>

- **Formatting**: Bold, Italic, Underline, Strikethrough, Font Color, Background Color
- **Alignment**: Left, Center, Right, Top, Middle, Bottom, Wrap Text
- **Numbers**: Currency, Percent, Scientific, Increase/Decrease Decimals
- **Cells**: Merge, Insert/Delete Rows/Columns
- **Data**: Sort Ascending/Descending, AutoFilter, Freeze Panes, AutoSum
- **Insert**: Chart, Function

</details>

<details>
<summary><b>Impress and Draw packs (30+ capabilities)</b></summary>

- **Formatting**: Bold, Italic, Underline, Strikethrough, Font Size, Font Color
- **Alignment**: Left, Center, Right, Justify
- **Slides**: New Slide, Duplicate, Delete, Start Presentation
- **Insert**: Image, Text Box, Shape
- **Drawing**: Clear Formatting, Numbering

</details>

Additional pack targets in the refactor are **Math**, **Base**, and **app-global capabilities** such as manifest-driven UNO command execution.

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
├── extension/                    # LibreOffice extension (.oxt)
│   └── src/loaia/
│       ├── execution/            # Generic runtime, preflight, bindings, observe
│       ├── snapshot/             # App-specific context snapshots and probes
│       ├── history/              # Session and audit history
│       └── broker/               # Extension-side transport and coordination
├── sidecar/                      # Local AI broker process
│   └── src/loaia_sidecar/
│       ├── orchestrator/         # Session engine, evaluator, bounded replanning
│       ├── planner/              # Retrieval, composition, prompt building
│       └── providers/            # Provider adapters
├── shared/                       # Shared schemas and capability model
│   └── src/loaia_shared/
│       ├── schema/               # Shared request/response models
│       └── capabilities/         # Catalog, compiler, manifests, generated tables
├── scripts/                      # Build, test, and verification scripts
└── docs/                         # Refactor plan, architecture, design specification
```

This is the target layout during the operation-layer refactor. The current repository still contains migration-era modules alongside these destinations.

---

## 🗺️ Roadmap

- [x] Extension + sidecar MVP with live UNO execution
- [x] Writer, Calc, Impress, and Draw baseline capability coverage
- [x] UI integration coverage for live UNO dispatch paths
- [ ] Capability catalog as the single source of truth
- [ ] Generated execution manifests and safety matrix
- [ ] Snapshot and observation probes for every mutating capability
- [ ] Sidecar orchestrator split from the monolithic server
- [ ] Retrieval-based planner with bounded replanning
- [ ] Math, Base, and app-global capability packs
- [ ] macOS and Linux support
- [ ] Local LLM support (Ollama, llama.cpp)

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