
I’m grounding this in the current extension design first, then I’ll answer whether the limitation is in the implementation, the integration boundary, or the overall approach.

Read [](file:///c%3A/AI/intel-ai/libreoffice/libreoffice-ai-agent)

Searched for files matching `libreoffice` · `libreoffice-ai-agent/**/README*.md`, 2 matches

Searched for regex `UNO|dispatch|tool calling|function call|LibreOfficeKit|socket|WebSocket|MCP|agent` (`**/libreoffice-ai-agent/**`), 200 results

Read memory [](file:///c%3A/Users/wghap/AppData/Roaming/Code/User/workspaceStorage/0bc97d4d8be2009308cd7c6dbdc3f354/GitHub.copilot-chat/memory-tool/memories/repo/libreoffice-ai-agent-scaffold.md)

I’ve confirmed the extension is built around a narrow protocol bridge plus a tool-to-UNO registry. Next I’m reading the owning docs and control path to see whether the ceiling comes from missing coverage, the planner, or the LibreOffice integration boundary itself.

Read [](file:///c%3A/AI/intel-ai/libreoffice/libreoffice-ai-agent/README.md)

Read [](file:///c%3A/AI/intel-ai/libreoffice/libreoffice-ai-agent/sidecar/src/loaia_sidecar/planner/prompts.py)

Read [](file:///c%3A/AI/intel-ai/libreoffice/libreoffice-ai-agent/extension/src/loaia/actions/executor.py#1-1), lines 1 to 260

Read [](file:///c%3A/AI/intel-ai/libreoffice/libreoffice-ai-agent/extension/src/loaia/protocol_handler.py)

The README claims broad app support, but the concrete control surface is still a registered tool list and a few protocol commands. I’m checking the actual dispatch and planner path now, because that’s where “can’t control LibreOffice fully” will either be a design choice or a mismatch between docs and runtime.

Searched for regex `preview-selection|approve-pending|send-message|save-settings|SUPPORTED_COMMANDS|TOOL_UNO_DISPATCH_MAP` (`**/libreoffice-ai-agent/extension/src/**`), 8 results

Read [](file:///c%3A/AI/intel-ai/libreoffice/libreoffice-ai-agent/extension/src/loaia_python.py#60-60), lines 60 to 192

Read [](file:///c%3A/AI/intel-ai/libreoffice/libreoffice-ai-agent/sidecar/src/loaia_sidecar/server.py#1-1), lines 1 to 260

Read [](file:///c%3A/AI/intel-ai/libreoffice/docs/libreoffice-ai-agent-mvp-design-spec.md#1-1), lines 1 to 260

The core product decision is explicit in the spec: the sidecar is not allowed to mutate LibreOffice directly, and phase 1 only auto-applies a whitelist. That means the current architecture is safe and shippable for an MVP, but it is structurally not a “full LibreOffice operator.” I’m checking how hard-coded that ceiling is in the planner and registry.

Searched for regex `def _plan_tool_proposal|registered tool|tool registry|tool_id|available_tools|Only propose registered tools|Never invent a tool id` (`**/libreoffice-ai-agent/sidecar/src/**`), 11 results

Searched for files matching `libreoffice` · `libreoffice-ai-agent/shared/src/**/*.py`, 9 matches

Read [](file:///c%3A/AI/intel-ai/libreoffice/libreoffice-ai-agent/sidecar/src/loaia_sidecar/server.py#260-260), lines 260 to 620

Read [](file:///c%3A/AI/intel-ai/libreoffice/docs/libreoffice-ai-agent-architecture.md#1-1), lines 1 to 280

The architecture document answers part of it directly: “full autonomous control” and “arbitrary command execution” are non-goals. I’m reading the planner implementation for Calc/Impress and the safe-formatting policy now, because that shows whether the current product is merely incomplete or fundamentally constrained by design.

Read [](file:///c%3A/AI/intel-ai/libreoffice/libreoffice-ai-agent/sidecar/src/loaia_sidecar/server.py#620-620), lines 620 to 1080

Searched for regex `CreateChartFromSelection|InsertFormulaInSelection|CreateSlideFromOutline|ApplyLayout|ExecuteUnoCommand` (`**/libreoffice-ai-agent/**`), 200 results

Read [](file:///c%3A/AI/intel-ai/libreoffice/libreoffice-ai-agent/sidecar/src/loaia_sidecar/planner/policy.py)

Read [](file:///c%3A/AI/intel-ai/libreoffice/libreoffice-ai-agent/shared/src/loaia_shared/schema/actions.py)

The planner is heavily keyword-driven, and the safe-formatting policy file still reflects the narrower phase-1 whitelist even though the executor has grown. I’m checking the execution registry next, because the bottleneck may be less “LibreOffice can’t be controlled” and more “the agent only knows how to request a small subset of things.”

Read [](file:///c%3A/AI/intel-ai/libreoffice/libreoffice-ai-agent/extension/src/loaia/actions/app.py)

Read [](file:///c%3A/AI/intel-ai/libreoffice/libreoffice-ai-agent/extension/src/loaia/actions/calc.py)

Read [](file:///c%3A/AI/intel-ai/libreoffice/libreoffice-ai-agent/extension/src/loaia/actions/impress.py)

Read [](file:///c%3A/AI/intel-ai/libreoffice/libreoffice-ai-agent/extension/tests/unit/test_action_registry.py)

There’s a mismatch emerging: the executor can dispatch many more commands than the planner and the documented safe-formatting policy acknowledge. That usually produces the exact symptom you described: “the system can do some things, but it doesn’t reliably know or choose the full tool surface.”

Searched for regex `App.ExecuteUnoCommand|SAFE_FORMATTING_TOOL_IDS|ACTION_REGISTRY|requires_approval=False|requires_approval=True` (`**/libreoffice-ai-agent/extension/src/**`), 56 results

Searched for regex `keyword|contains\(|startswith\(|casefold\(|_SAFE_FORMATTING_KEYWORDS|_QUESTION_STARTERS|_ANALYSIS_KEYWORDS` (`**/libreoffice-ai-agent/sidecar/src/**`), 64 results

Read [](file:///c%3A/AI/intel-ai/libreoffice/libreoffice-ai-agent/extension/src/loaia/actions/registry.py)

Read [](file:///c%3A/AI/intel-ai/libreoffice/libreoffice-ai-agent/extension/src/loaia/sidebar_actions.py#300-300), lines 300 to 520

One more check: I want to verify whether your supposed escape hatch for broader office control, `App.ExecuteUnoCommand`, is actually wired end to end or just registered on paper. If it’s only nominal, that’s another sign the product surface is narrower than the architecture suggests.

Searched for text `App.ExecuteUnoCommand|ExecuteUnoCommand` (`**/libreoffice-ai-agent/**`), 23 results

Searched for regex `requiresApproval=False|requiresApproval=True|requires_approval=False|requires_approval=True` (`**/libreoffice-ai-agent/extension/src/loaia/chat_controller.py`), no results

Searched for regex `Base.ExplainQuery|Math.ReplaceFormula|Draw.ReplaceSelectedText|Draw.GetSelectedText|Math.GetFormula|Base.GetContext` (`**/libreoffice-ai-agent/sidecar/src/**`), 2 results

Read [](file:///c%3A/AI/intel-ai/libreoffice/libreoffice-ai-agent/extension/src/loaia/chat_controller.py)

I have enough to form a concrete answer. I’m pulling exact anchors for the main claims so I can give you a grounded recommendation instead of a generic architecture opinion.

Searched for text `Full autonomous control of every LibreOffice feature|Expose typed office capabilities, not arbitrary internal access|The sidecar does not directly edit LibreOffice documents|The model never gets arbitrary command execution` (`**/libreoffice-ai-agent/docs/libreoffice-ai-agent-architecture.md`), no results

Searched for text `Only propose registered tools. Never invent a tool id.|supports Writer, Calc, and Impress through a typed action layer|The sidecar never edits LibreOffice documents directly.` (`**/libreoffice-ai-agent/**/*.{md,py}`), 1 result

Searched for text `SUPPORTED_COMMANDS =|OPEN_SIDEBAR_COMMAND|SEND_MESSAGE_COMMAND|SAVE_SETTINGS_COMMAND` (`**/libreoffice-ai-agent/extension/src/loaia/protocol_handler.py`), 10 results

Searched for regex `App.ExecuteUnoCommand|Unsupported tool:|SAFE_FORMATTING_TOOL_IDS = frozenset\(TOOL_UNO_DISPATCH_MAP.keys\(\)\)` (`**/libreoffice-ai-agent/extension/src/**`), 3 results

I found the concrete control boundaries in code. I’m just grabbing the design-doc lines that match those boundaries, because they matter for the recommendation: this repo currently treats “safe typed assistance” and “full office autonomy” as different products.

Searched for text `Full autonomous control of every LibreOffice feature in phase 1|Expose typed office capabilities, not arbitrary internal access.|The sidecar does not directly edit LibreOffice documents.|The model never gets arbitrary command execution.` (`**/docs/libreoffice-ai-agent-architecture.md`), 4 results

Searched for text `The sidecar never edits LibreOffice documents directly.|supports Writer, Calc, and Impress through a typed action layer` (`**/libreoffice-ai-agent/README.md`), no results

Searched for text `Safe formatting-only whitelist for phase 1|Anything outside this whitelist must not auto-apply in phase 1.` (`**/docs/libreoffice-ai-agent-mvp-design-spec.md`), 2 results

Searched for text `_SAFE_FORMATTING_KEYWORDS:|def _plan_safe_formatting|def _plan_calc_proposal|def _plan_impress_proposal` (`**/libreoffice-ai-agent/sidecar/src/loaia_sidecar/server.py`), 4 results

The evidence is consistent now. I’m not seeing a single broken idea so much as an architecture that was intentionally optimized for a safe MVP and then allowed to carry expectations of a general-purpose office operator.

Searched for text `support Writer, Calc, and Impress through a typed action layer` (`libreoffice` · `libreoffice-ai-agent/README.md`), 1 result

Searched for text `The sidecar never edits LibreOffice documents directly.` (`libreoffice` · `docs/libreoffice-ai-agent-mvp-design-spec.md`), 1 result

Searched for text `Only propose registered tools. Never invent a tool id.` (`libreoffice` · `libreoffice-ai-agent/sidecar/src/loaia_sidecar/planner/prompts.py`), 1 result

Searched for regex `if proposal.tool_id not in ACTION_REGISTRY|Unknown tool proposal` (`libreoffice` · `libreoffice-ai-agent/extension/src/loaia/chat_controller.py`), 2 results

I also verified the broader-command escape hatch is mostly theoretical right now. `App.ExecuteUnoCommand` exists in the action registry, but it isn’t part of the planner surface and it isn’t handled in the main proposal executor, so it doesn’t actually solve the “full control” problem yet.

Searched for text `App.ExecuteUnoCommand` (`**/libreoffice-ai-agent/extension/src/**`), 1 result

Searched for text `App.ExecuteUnoCommand` (`**/libreoffice-ai-agent/sidecar/src/**`), no results

Searched for text `Unsupported tool:` (`**/libreoffice-ai-agent/extension/src/loaia/sidebar_actions.py`), 1 result

Searched for text `proposal.tool_id not in ACTION_REGISTRY` (`**/libreoffice-ai-agent/extension/src/loaia/chat_controller.py`), 1 result

I’m doing one last narrow check on test coverage around protocol dispatch. If tests are still written against a broader command set than the live handler exposes, that would confirm this is partly an architecture-target mismatch and partly implementation drift.

Checked [](file:///c%3A/AI/intel-ai/libreoffice/libreoffice-ai-agent/extension/src/loaia/protocol_handler.py), [](file:///c%3A/AI/intel-ai/libreoffice/libreoffice-ai-agent/extension/tests/unit/test_uno_entrypoints.py), no problems found

Read [](file:///c%3A/AI/intel-ai/libreoffice/libreoffice-ai-agent/extension/tests/unit/test_uno_entrypoints.py#80-80), lines 80 to 280

The code and tests are not obviously aligned on the protocol surface, so I’m running the narrow unit slice that exercises those entrypoints. If that fails, it confirms there’s implementation drift on top of the architectural limitation.

Ran terminal command: Set-Location 'c:\AI\intel-ai\libreoffice\libreoffice-ai-agent'; pytest extension/tests/unit/test_uno_entrypoints.py -q
Completed with input: Set-Location 'c:\AI\intel-ai\libreoffice\libreoffice-ai-agent'; pytest extension/tests/unit/test_uno_entrypoints.py -q

That test slice failed exactly where I expected: the tests still expect preview/approve protocol commands, but the current bootstrap surface doesn’t export them. This is now a concrete example of the larger problem: the intended agent surface and the implemented surface have drifted apart.

Searched for regex `OPEN_SIDEBAR_COMMAND =|SEND_MESSAGE_COMMAND =|SAVE_SETTINGS_COMMAND =|APPROVE_PENDING_COMMAND|PREVIEW_SELECTION_COMMAND` (`**/libreoffice-ai-agent/extension/src/loaia/bootstrap.py`), 3 results

Searched for text `ImportError: cannot import name 'APPROVE_PENDING_COMMAND'` (`libreoffice` · `libreoffice-ai-agent`), no results

I have enough to answer cleanly now. The short version is: your underlying safety architecture is defensible, but the current system is not organized like a true “agentic operating layer,” and there is also concrete drift between docs/tests and the implemented command surface.

Searched for regex `APPROVE_PENDING_COMMAND|PREVIEW_SELECTION_COMMAND` (`**/libreoffice-ai-agent/extension/tests/unit/test_uno_entrypoints.py`), 11 results

Searched for text `supports Writer, Calc, and Impress through a typed action layer` (`**/libreoffice-ai-agent/README.md`), no results

Searched for regex `proposal.tool_id not in ACTION_REGISTRY|Unknown tool proposal` (`**/libreoffice-ai-agent/extension/src/loaia/chat_controller.py`), 2 results

Searched for text `App.ExecuteUnoCommand` (`**/libreoffice-ai-agent/extension/src/loaia/actions/app.py`), 1 result

I’m not doing more code reads. The remaining question is just how to frame the recommendation: keep the safe core and narrow the product promise, or pivot deliberately to a more capable operator architecture.

Searched for text `support Writer, Calc, and Impress through a typed action layer` (`**/libreoffice-ai-agent/README.md`), 1 result

There’s one more design-level inconsistency worth checking because it affects safety semantics, not just coverage: whether the extension is auto-applying everything in the dispatch map as “safe formatting,” even when the spec says only a small whitelist should auto-apply.

Searched for regex `is_safe_formatting_action\(|execute_safe_formatting\(` (`**/libreoffice-ai-agent/extension/src/loaia/sidebar_actions.py`), 2 results

Searched for regex `SAFE_FORMATTING_TOOL_IDS = \{|def is_safe_formatting_tool` (`**/libreoffice-ai-agent/sidecar/src/loaia_sidecar/planner/policy.py`), 2 results

Searched for regex `SAFE_FORMATTING_TOOL_IDS = frozenset\(TOOL_UNO_DISPATCH_MAP.keys\(\)\)` (`**/libreoffice-ai-agent/extension/src/loaia/actions/executor.py`), 1 result

Searched for text `Anything outside this whitelist must not auto-apply in phase 1.` (`**/docs/libreoffice-ai-agent-mvp-design-spec.md`), 1 result

I found a more serious structural issue than “not enough coverage”: the auto-apply safety boundary has diverged. The spec keeps a small whitelist, but the extension currently treats every dispatch-mapped tool as safe formatting during execution.

Searched for regex `is_safe_formatting_tool\(` (`**/libreoffice-ai-agent/sidecar/src/**`), 1 result

Searched for regex `safe_formatting|requires_approval` (`**/libreoffice-ai-agent/extension/src/loaia/actions/*.py`), 106 results

Read [](file:///c%3A/AI/intel-ai/libreoffice/libreoffice-ai-agent/extension/src/loaia/actions/base.py)

I’m recording the concrete drift I found so the next pass doesn’t have to rediscover it: protocol surface mismatch, duplicated safety registries, and executor safety classification broader than the spec.

Read memory

Inserted into memory file [](file:///c%3A/Users/wghap/AppData/Roaming/Code/User/workspaceStorage/0bc97d4d8be2009308cd7c6dbdc3f354/GitHub.copilot-chat/memory-tool/memories/repo/libreoffice-ai-agent-scaffold.md)

**Assessment**
If the target is a safe MVP assistant, the approach is reasonable. If the target is a true agent that can broadly operate LibreOffice, the current shape is wrong.

- The architecture explicitly rules out full office autonomy and arbitrary internal access. See libreoffice-ai-agent-architecture.md, libreoffice-ai-agent-architecture.md, libreoffice-ai-agent-architecture.md, libreoffice-ai-agent-architecture.md, and libreoffice-ai-agent-mvp-design-spec.md.
- The planner is not really an operating layer yet. It is constrained to registered tools in prompts.py, and most routing is still large keyword tables and hand-written heuristics in server.py, server.py, server.py, and server.py. That scales badly and will never feel like “full LibreOffice coverage.”
- The bigger problem is duplicated sources of truth. The spec keeps a narrow auto-apply whitelist in libreoffice-ai-agent-mvp-design-spec.md and libreoffice-ai-agent-mvp-design-spec.md, but the extension currently marks every dispatch-mapped tool as safe in executor.py and auto-applies on that basis in sidebar_actions.py. That is a control-model bug, not just missing feature work.
- There is already drift between intended and implemented surfaces. The bootstrap currently defines only three protocol commands in bootstrap.py, while tests still expect preview/approve commands in test_uno_entrypoints.py. I ran `pytest extension/tests/unit/test_uno_entrypoints.py -q`; collection currently fails because `APPROVE_PENDING_COMMAND` cannot be imported. Also, `App.ExecuteUnoCommand` exists only as a registry entry in app.py, while unsupported tools still hard-fail in sidebar_actions.py.

My view: the extension + sidecar split is not the wrong choice. The wrong choice is expecting “full LibreOffice control” from a system that is still fundamentally a typed assistant with keyword planning and multiple hand-maintained registries. I would keep the split, but I would change the control model and the product framing.

**Next Steps**

1. Decide the product honestly: “high-confidence assistant for common workflows” or “operator mode for broad office control.” Those are different systems.
2. If you stay assistant-first, make one canonical capability registry and generate planner prompt, safety class, validation, docs, and tests from it. Right now the spec, planner policy, action registry, executor map, and tests can drift independently.
3. If you want operator mode, do not pivot to raw UI automation. Build a discoverable UNO capability catalog plus a plan-execute-observe loop: retrieved candidate tools, explicit preconditions, whitelisted command execution, and postcondition checks.

If you want, I can turn this into a concrete refactor plan for the current repo, starting with the single-source-of-truth action/safety registry and the protocol-surface cleanup.

---

# **中文易读版（口语、清晰、好理解）**

我们做了 LibreOffice 的 AI Agent 扩展，但现在遇到很多问题。

AI Agent 不能完全控制 LibreOffice 的所有工具和功能。

所以我开始怀疑：是不是我们一开始就选错了方向或方案？

下面是我根据目前扩展的设计，整理出的想法。

---

## **1. 现有架构本身就有限制，不是实现的问题**

从设计文档来看，这个扩展是用一个“窄协议桥 + 工具到 UNO 的注册表”来实现的。

换句话说，它本来就不是为了“完全控制 LibreOffice”而设计的。

文档里写得很清楚：

**“完全自主控制”和“任意命令执行”不是目标。**

所以现在的架构更像是一个“安全的助手”，而不是“能操作整个 Office 的智能代理”。

---

## **2. Planner（规划器）能力太弱，不是真正的操作层**

Planner 现在主要靠：

* 注册过的工具列表
* 一堆关键词匹配
* 手写的规则和判断

这些东西分散在 server.py 的很多地方。

这种方式扩展性很差，也不可能覆盖 LibreOffice 的全部功能。

所以你会感觉“能做一点，但做不全”。

---

## **3. 多个“真相来源”彼此不一致，导致行为混乱**

现在系统里有：

* 设计文档里的安全白名单
* Planner 的规则
* Action registry（动作注册表）
* Executor（执行器）
* 测试代码

这些本来应该统一，但现在都各自为政，互相不一致。

例如：

* 文档里说只有少量命令是“自动应用”的
* 但执行器里却把所有注册的工具都当成“安全的”
* Planner 也没有同步更新
* 测试代码还在期待一些已经不存在的协议命令

这种“漂移”会直接导致你看到的各种奇怪问题。

---

## **4. ExecuteUnoCommand 名义上存在，但实际上没真正接好**

虽然 registry 里有 `App.ExecuteUnoCommand`，

但 Planner 不会用它，执行器也没有完整处理它。

所以它并不能解决“让 AI 控制更多 LibreOffice 功能”的问题。

---

## **5. 结论：不是你实现错了，而是架构本身不适合做‘全功能 AI 操作层’**

如果目标只是做一个“安全的、常用功能助手”，

现在的架构是合理的。

但如果目标是“让 AI 像人一样操作整个 LibreOffice”，

那现在的设计方向就不够了。

---

# **下一步建议**

## **方案 A：继续做“安全助手”**

如果你们想保持安全优先、功能有限的方向：

1. **建立一个统一的能力注册表（单一真相来源）**

   Planner、执行器、文档、测试都从这里生成。
2. **清理协议面（protocol surface）**

   把文档、代码、测试对齐。
3. **保持小范围、安全的自动应用功能**

   避免扩展过快导致风险。

---

## **方案 B：转向“真正的 AI 操作层”**

如果你们想让 AI 能真正操作 LibreOffice：

1. **不要靠关键词匹配和手写规则**

   改成可发现、可查询的 UNO 能力目录。
2. **建立 plan → execute → observe 的循环**

   让 AI 能根据反馈调整动作。
3. **明确安全边界**

   允许更多命令，但要有白名单、前置条件、后置检查。
4. **让 ExecuteUnoCommand 真正可用**

   这是扩展 LibreOffice 控制能力的关键。

---

# **一句话总结**

你们不是“实现错了”，

而是现在的架构本来就不是为了“完全控制 LibreOffice”而设计的。

要么调整目标，要么重构架构。

---

如果你愿意，我可以帮你：

* 把整个 repo 的架构重组成“单一真相来源”
* 设计一个真正可扩展的 AI 操作层
* 或者写一个完整的 refactor 计划（按模块拆解）

你想往哪个方向走？


方案 B：转向“真正的 AI 操作层”。以“完全控制 LibreOffice”为项目的核心目标，并完成以下目标。

Option B: pivot to a real AI operation layer. Make “full control of LibreOffice” the core project goal, and deliver the following outcomes.

重写一个完整的重构计划，按模块拆解，并覆盖 Architecture doc 和 design-specification doc。

Rewrite a complete refactor plan, broken down by module, and cover both the architecture document and the design specification document.

把整个 repo 的架构重组成“单一真相来源”。

Reorganize the entire repository architecture around a single source of truth.

设计一个真正可扩展的 AI 操作层。

Design a genuinely extensible AI operation layer.

不要再依赖关键词匹配和手写规则，改成可发现、可查询的 UNO 能力目录。

Stop relying on keyword matching and hand-written rules, and replace them with a discoverable, queryable UNO capability catalog.

建立 plan → execute → observe 的循环，让 AI 能根据反馈调整动作。

Build a plan → execute → observe loop so the AI can adjust its actions based on feedback.

明确安全边界，允许更多命令，但必须有白名单、前置条件和后置检查。

Define the safety boundary clearly. Allow more commands, but require a whitelist, preconditions, and post-execution checks.

让 ExecuteUnoCommand 真正可用，这是扩展 LibreOffice 控制能力的关键。

Make ExecuteUnoCommand genuinely usable. That is the key to expanding LibreOffice control coverage.

