from __future__ import annotations

import re

from loaia_shared.capabilities.compiler import CompiledCapability, get_compiled_capabilities
from loaia_shared.types import AppType


TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "a",
    "an",
    "the",
    "this",
    "that",
    "these",
    "those",
    "to",
    "of",
    "for",
    "in",
    "on",
    "at",
    "and",
    "or",
    "is",
    "are",
    "be",
    "me",
    "my",
    "it",
    "here",
    "please",
}


class CapabilityRetriever:
    def __init__(self) -> None:
        self._compiled_capabilities = get_compiled_capabilities()

    def search(
        self,
        *,
        app: AppType | str,
        query: str,
        limit: int = 8,
    ) -> list[CompiledCapability]:
        app_value = app.value if isinstance(app, AppType) else str(app)
        normalized_query = query.casefold()
        query_tokens = {
            token
            for token in TOKEN_RE.findall(normalized_query)
            if token not in STOPWORDS
        }

        ranked: list[tuple[int, CompiledCapability]] = []
        for compiled in self._compiled_capabilities.values():
            descriptor = compiled.descriptor
            if descriptor.app not in {app_value, "app"}:
                continue

            score = len(query_tokens & compiled.search_tokens) * 3
            title = descriptor.title.casefold()
            if title and title in normalized_query:
                score += 4
            for tag in descriptor.intent_tags:
                if tag.casefold() in normalized_query:
                    score += 2
            for example in descriptor.examples:
                example_text = example.casefold()
                if example_text in normalized_query or normalized_query in example_text:
                    score += 6

            if score > 0:
                ranked.append((score, compiled))

        ranked.sort(
            key=lambda item: (
                -item[0],
                0 if item[1].descriptor.app == app_value else 1,
                0 if item[1].descriptor.binding.kind == "none" else 1,
                item[1].descriptor.tool_id,
            )
        )
        return [compiled for _, compiled in ranked[:limit]]