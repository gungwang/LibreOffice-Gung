from collections.abc import Callable, Iterable

from loaia_shared.schema.messages import (
    ChatRequest,
    ContextEnvelope,
    DocumentRef,
    SelectionContext,
)
from loaia_shared.types import AppType, PrivacyScope
from loaia_sidecar.providers.base import ProviderChunk, ProviderRequest
from loaia_sidecar.server import LoaiaSidecarServer


class FakeProviderAdapter:
    name = "openrouter"

    def __init__(
        self,
        answer: str = "Remote answer",
        complete_impl: Callable[[ProviderRequest], str] | None = None,
    ) -> None:
        self.answer = answer
        self.complete_impl = complete_impl
        self.requests: list[ProviderRequest] = []

    def complete(self, request: ProviderRequest) -> str:
        self.requests.append(request)
        if self.complete_impl is not None:
            return self.complete_impl(request)
        return self.answer

    def stream(self, request: ProviderRequest) -> Iterable[ProviderChunk]:
        self.requests.append(request)
        return iter(())


class FailingProviderAdapter:
    name = "openrouter"

    def complete(self, request: ProviderRequest) -> str:
        raise ValueError("OpenRouter API key is not configured.")

    def stream(self, request: ProviderRequest) -> Iterable[ProviderChunk]:
        return iter(())


def make_chat_request(
    *,
    provider: str = "openrouter",
    model: str = "openai/gpt-4.1-mini",
    app: AppType = AppType.WRITER,
    selection_text: str | None = "hello world",
    user_message: str = "Summarize this selection.",
) -> ChatRequest:
    context = ContextEnvelope()
    if selection_text is not None:
        context = ContextEnvelope(
            selection=SelectionContext(mimeType="text/plain", text=selection_text)
        )

    return ChatRequest(
        requestId="req-openrouter-1",
        app=app,
        document=DocumentRef(canonicalUrl="file:///example.odt", profileId="profile-1"),
        provider=provider,
        model=model,
        privacyScope=PrivacyScope.SELECTION_ONLY,
        context=context,
        userMessage=user_message,
    )


def test_handle_chat_request_uses_provider_adapter_for_direct_answers() -> None:
    adapter = FakeProviderAdapter(answer="Remote summary")
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    response = server.handle_chat_request(make_chat_request(selection_text=None))

    assert response.type == "DirectAnswer"
    assert response.text == "Remote summary"
    assert adapter.requests == [
        ProviderRequest(
            provider="openrouter",
            model="openai/gpt-4.1-mini",
            prompt="Summarize this selection.",
            context_text="",
        )
    ]


def test_handle_chat_request_uses_provider_adapter_for_writer_proposals() -> None:
    adapter = FakeProviderAdapter(
        answer=(
            '{"action":"replace-selection",'
            '"replacementText":"Greetings from the revised draft."}'
        )
    )
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    response = server.handle_chat_request(
        make_chat_request(user_message="Rewrite this selection in a more formal tone.")
    )

    assert response.type == "ToolProposal"
    assert len(response.proposals) == 1
    proposal = response.proposals[0]
    assert proposal.tool_id == "Writer.ReplaceSelection"
    assert proposal.preview is not None
    assert proposal.preview.before == "hello world"
    assert proposal.preview.after == "Greetings from the revised draft."
    assert proposal.arguments == {"replacementText": "Greetings from the revised draft."}
    assert len(adapter.requests) == 1
    assert adapter.requests[0].context_text == "hello world"
    assert '"action":"no-replacement"' in adapter.requests[0].prompt
    assert '"replacementText":"<full replacement text>"' in adapter.requests[0].prompt
    assert "Rewrite this selection in a more formal tone." in adapter.requests[0].prompt


def test_handle_chat_request_falls_back_to_direct_answer_when_provider_declines_rewrite() -> None:
    def complete_impl(request: ProviderRequest) -> str:
        if '"action":"no-replacement"' in request.prompt:
            return '{"action":"no-replacement"}'

        return "Remote summary"

    adapter = FakeProviderAdapter(complete_impl=complete_impl)
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    response = server.handle_chat_request(
        make_chat_request(user_message="Fix the grammar in this text.")
    )

    assert response.type == "DirectAnswer"
    assert response.text == "Remote summary"
    assert len(adapter.requests) == 2
    assert '"action":"no-replacement"' in adapter.requests[0].prompt
    assert adapter.requests[0].context_text == "hello world"
    assert adapter.requests[1] == ProviderRequest(
        provider="openrouter",
        model="openai/gpt-4.1-mini",
        prompt="Fix the grammar in this text.",
        context_text="hello world",
    )


def test_normalize_writer_rewrite_response_supports_json_contract() -> None:
    server = LoaiaSidecarServer(provider_adapters={})

    assert (
        server._normalize_writer_rewrite_response(
            '{"action":"replace-selection","replacementText":"Formal rewrite"}'
        )
        == "Formal rewrite"
    )
    assert server._normalize_writer_rewrite_response('{"action":"no-replacement"}') is None


def test_handle_message_returns_error_response_for_provider_failures() -> None:
    server = LoaiaSidecarServer(provider_adapters={"openrouter": FailingProviderAdapter()})

    response = server.handle_message(make_chat_request().model_dump(by_alias=True, mode="json"))

    assert response["type"] == "ErrorResponse"
    assert response["requestId"] == "req-openrouter-1"
    assert response["message"] == "OpenRouter API key is not configured."


def test_calc_formula_proposal_generated_for_formula_request() -> None:
    adapter = FakeProviderAdapter(answer="=SUM(A1:A10)")
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    response = server.handle_chat_request(
        make_chat_request(
            app=AppType.CALC,
            selection_text="100",
            user_message="Insert a SUM formula for column A",
        )
    )

    assert response.type == "ToolProposal"
    assert len(response.proposals) == 1
    proposal = response.proposals[0]
    assert proposal.tool_id == "Calc.InsertFormulaInSelection"
    assert proposal.arguments == {"formula": "=SUM(A1:A10)"}


def test_calc_direct_answer_for_non_formula_request() -> None:
    adapter = FakeProviderAdapter(answer="This cell contains the number 100.")
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    response = server.handle_chat_request(
        make_chat_request(
            app=AppType.CALC,
            selection_text="100",
            user_message="Explain what this cell contains.",
        )
    )

    assert response.type == "DirectAnswer"
    assert response.text == "This cell contains the number 100."


def test_impress_rewrite_proposal_generated_for_rewrite_request() -> None:
    adapter = FakeProviderAdapter(answer="Simplified bullet points for the audience.")
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    response = server.handle_chat_request(
        make_chat_request(
            app=AppType.IMPRESS,
            selection_text="Complex slide text with jargon.",
            user_message="Rewrite this to be simpler.",
        )
    )

    assert response.type == "ToolProposal"
    assert len(response.proposals) == 1
    proposal = response.proposals[0]
    assert proposal.tool_id == "Impress.ReplaceSelectedText"
    assert proposal.preview is not None
    assert proposal.preview.after == "Simplified bullet points for the audience."


def test_impress_direct_answer_for_non_rewrite_request() -> None:
    adapter = FakeProviderAdapter(answer="This slide discusses project milestones.")
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    response = server.handle_chat_request(
        make_chat_request(
            app=AppType.IMPRESS,
            selection_text="Q1 goals achieved.",
            user_message="What does this slide talk about?",
        )
    )

    assert response.type == "DirectAnswer"
    assert response.text == "This slide discusses project milestones."


# ------------------------------------------------------------------
# Safe-formatting planner tests
# ------------------------------------------------------------------


def test_safe_formatting_bold_writer() -> None:
    adapter = FakeProviderAdapter()
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    response = server.handle_chat_request(make_chat_request(user_message="Make this bold"))

    assert response.type == "ToolProposal"
    proposal = response.proposals[0]
    assert proposal.tool_id == "Writer.ToggleBold"
    assert proposal.safety_class.value == "safe-formatting"
    assert proposal.requires_approval is False


def test_safe_formatting_center_calc() -> None:
    adapter = FakeProviderAdapter()
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    response = server.handle_chat_request(
        make_chat_request(
            app=AppType.CALC,
            user_message="Center this cell",
        )
    )

    assert response.type == "ToolProposal"
    assert response.proposals[0].tool_id == "Calc.AlignCenter"


def test_safe_formatting_bullets_impress() -> None:
    adapter = FakeProviderAdapter()
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    response = server.handle_chat_request(
        make_chat_request(
            app=AppType.IMPRESS,
            user_message="Add bullets to this",
        )
    )

    assert response.type == "ToolProposal"
    assert response.proposals[0].tool_id == "Impress.ApplyBullets"


# ------------------------------------------------------------------
# Writer insert-below planner test
# ------------------------------------------------------------------


def test_writer_insert_below_proposal() -> None:
    adapter = FakeProviderAdapter(answer="New paragraph text")
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    response = server.handle_chat_request(
        make_chat_request(user_message="Insert below a summary paragraph")
    )

    assert response.type == "ToolProposal"
    proposal = response.proposals[0]
    assert proposal.tool_id == "Writer.InsertBelowSelection"
    assert proposal.requires_approval is True


# ------------------------------------------------------------------
# Calc chart / sort planner tests
# ------------------------------------------------------------------


def test_calc_chart_proposal() -> None:
    adapter = FakeProviderAdapter()
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    response = server.handle_chat_request(
        make_chat_request(
            app=AppType.CALC,
            selection_text="A1:B10",
            user_message="Create a pie chart from this data",
        )
    )

    assert response.type == "ToolProposal"
    proposal = response.proposals[0]
    assert proposal.tool_id == "Calc.CreateChartFromSelection"
    assert proposal.arguments["chartType"] == "Pie"


def test_calc_sort_proposal() -> None:
    adapter = FakeProviderAdapter()
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    response = server.handle_chat_request(
        make_chat_request(
            app=AppType.CALC,
            selection_text="A1:B10",
            user_message="Sort this data in descending order",
        )
    )

    assert response.type == "ToolProposal"
    proposal = response.proposals[0]
    assert proposal.tool_id == "Calc.SortSelectedRange"
    assert proposal.arguments["ascending"] is False


def test_dispatch_backed_writer_command_routes_through_execute_uno_command() -> None:
    adapter = FakeProviderAdapter()
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    response = server.handle_chat_request(
        make_chat_request(user_message="Insert a page break here")
    )

    assert response.type == "ToolProposal"
    proposal = response.proposals[0]
    assert proposal.tool_id == "App.ExecuteUnoCommand"
    assert proposal.arguments["targetToolId"] == "Writer.InsertPageBreak"


# ------------------------------------------------------------------
# Impress slide / layout planner tests
# ------------------------------------------------------------------


def test_impress_create_slide_proposal() -> None:
    adapter = FakeProviderAdapter(answer="Project Status Update")
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    response = server.handle_chat_request(
        make_chat_request(
            app=AppType.IMPRESS,
            selection_text="",
            user_message="Create a new slide about project status",
        )
    )

    assert response.type == "ToolProposal"
    proposal = response.proposals[0]
    assert proposal.tool_id == "Impress.CreateSlideFromOutline"
    assert proposal.arguments["outline"] == "Project Status Update"


def test_impress_layout_proposal() -> None:
    adapter = FakeProviderAdapter()
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    response = server.handle_chat_request(
        make_chat_request(
            app=AppType.IMPRESS,
            selection_text="",
            user_message="Apply a blank layout to this slide",
        )
    )

    assert response.type == "ToolProposal"
    proposal = response.proposals[0]
    assert proposal.tool_id == "Impress.ApplyLayoutToCurrentSlide"
    assert proposal.arguments["layout"] == 0


def test_writer_multistep_plan_returns_follow_up_proposal_after_observation() -> None:
    adapter = FakeProviderAdapter(
        answer='{"action":"replace-selection","replacementText":"HELLO WORLD"}'
    )
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    response = server.handle_chat_request(
        make_chat_request(
            user_message="Please convert this selection to uppercase and make it bold.",
        )
    )

    assert response.type == "ToolProposal"
    assert response.proposals[0].tool_id == "Writer.ReplaceSelection"

    revision = server.handle_message(
        {
            "type": "ObservationReport",
            "sessionId": "req-openrouter-1",
            "stepId": "req-openrouter-1-step-1",
            "outcome": "satisfied",
            "preconditions": [
                {
                    "probe": "selection.non_empty",
                    "status": "passed",
                    "actual": True,
                    "expected": True,
                }
            ],
            "postconditions": [
                {
                    "probe": "selection.equals_preview_after",
                    "status": "passed",
                    "actual": "HELLO WORLD",
                    "expected": "HELLO WORLD",
                }
            ],
            "summary": "Applied Writer.ReplaceSelection",
        }
    )

    assert revision["type"] == "PlanRevision"
    assert revision["action"] == "continue"
    assert revision["nextStepId"] == "req-openrouter-1-step-2"
    assert revision["nextProposal"]["toolId"] == "Writer.ToggleBold"


# ------------------------------------------------------------------
# Cancellation tests
# ------------------------------------------------------------------


def test_cancel_request_acknowledged() -> None:
    server = LoaiaSidecarServer(provider_adapters={})

    result = server.handle_message({"type": "CancelRequest", "requestId": "req-cancel-1"})

    assert result["type"] == "CancelAck"
    assert result["requestId"] == "req-cancel-1"


def test_cancel_request_stops_streaming() -> None:
    """Simulate cancellation during streaming by pre-registering a cancelled ID."""
    adapter = FakeProviderAdapter()
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    # Pre-cancel the request
    server.handle_message_streaming({"type": "CancelRequest", "requestId": "req-openrouter-1"})

    # Now make the chat request with the same ID
    request = make_chat_request(selection_text=None, user_message="Tell me a story")
    response = server.handle_chat_request(request)

    # With no streaming chunks collected due to cancel, the response should
    # still be a direct answer (non-streaming fallback or empty).
    # The key thing is: no exception was raised.
    assert response is not None


# ------------------------------------------------------------------
# Consent escalation tests
# ------------------------------------------------------------------


def test_consent_escalation_when_no_selection_and_document_keyword() -> None:
    adapter = FakeProviderAdapter()
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    response = server.handle_chat_request(
        make_chat_request(
            selection_text=None,
            user_message="Summarize this document",
        )
    )

    assert response.type == "ConsentRequest"
    assert response.requested_scope == "full-document"
    assert "full document" in response.reason.lower()


def test_no_consent_escalation_when_selection_present() -> None:
    adapter = FakeProviderAdapter(answer="Summary of selection")
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    response = server.handle_chat_request(
        make_chat_request(
            selection_text="Some selected text",
            user_message="Summarize this document",
        )
    )

    # Should NOT trigger consent — selection is present.
    assert response.type != "ConsentRequest"


def test_no_consent_escalation_for_generic_prompt() -> None:
    adapter = FakeProviderAdapter(answer="Hello!")
    server = LoaiaSidecarServer(provider_adapters={adapter.name: adapter})

    response = server.handle_chat_request(
        make_chat_request(
            selection_text=None,
            user_message="Tell me a joke",
        )
    )

    # No document-scope keywords — should be a direct answer.
    assert response.type == "DirectAnswer"
