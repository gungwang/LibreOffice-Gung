from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import re

from loaia_shared.capabilities.catalog import CAPABILITY_CATALOG, CapabilityDescriptor
from loaia_shared.schema.actions import SafetyClass


TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True, slots=True)
class CompiledCapability:
    descriptor: CapabilityDescriptor
    descriptor_hash: str
    search_text: str
    search_tokens: frozenset[str]


def _serialize_descriptor(descriptor: CapabilityDescriptor) -> dict[str, object]:
    binding = descriptor.binding
    return {
        "toolId": descriptor.tool_id,
        "app": descriptor.app,
        "title": descriptor.title,
        "summary": descriptor.summary,
        "safetyClass": descriptor.safety_class.value,
        "requiresApproval": descriptor.requires_approval,
        "binding": {
            "kind": binding.kind,
            "dispatchUrl": binding.dispatch_url,
            "dispatchAlias": binding.dispatch_alias,
            "argumentPreset": binding.argument_preset,
            "argumentValue": binding.argument_value,
        },
        "intentTags": list(descriptor.intent_tags),
        "examples": list(descriptor.examples),
        "preconditionProbes": list(descriptor.precondition_probes),
        "postconditionProbes": list(descriptor.postcondition_probes),
    }


def _tokenize(text: str) -> frozenset[str]:
    return frozenset(TOKEN_RE.findall(text.casefold()))


def _build_search_text(descriptor: CapabilityDescriptor) -> str:
    parts = [
        descriptor.tool_id,
        descriptor.title,
        descriptor.summary,
        *descriptor.intent_tags,
        *descriptor.examples,
    ]
    return "\n".join(part for part in parts if part)


@lru_cache(maxsize=1)
def get_compiled_capabilities() -> dict[str, CompiledCapability]:
    compiled: dict[str, CompiledCapability] = {}
    for descriptor in CAPABILITY_CATALOG:
        payload = _serialize_descriptor(descriptor)
        descriptor_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        search_text = _build_search_text(descriptor)
        compiled[descriptor.tool_id] = CompiledCapability(
            descriptor=descriptor,
            descriptor_hash=descriptor_hash,
            search_text=search_text,
            search_tokens=_tokenize(search_text),
        )
    return compiled


def get_capability_descriptor(tool_id: str) -> CapabilityDescriptor | None:
    compiled = get_compiled_capabilities().get(tool_id)
    if compiled is None:
        return None
    return compiled.descriptor


def get_descriptor_hash(tool_id: str) -> str | None:
    compiled = get_compiled_capabilities().get(tool_id)
    if compiled is None:
        return None
    return compiled.descriptor_hash


def get_dispatch_tool_map() -> dict[str, str]:
    return {
        tool_id: compiled.descriptor.binding.dispatch_url
        for tool_id, compiled in get_compiled_capabilities().items()
        if compiled.descriptor.binding.kind == "uno-dispatch"
        and compiled.descriptor.binding.dispatch_url is not None
    }


def get_dispatch_alias_map() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for tool_id, compiled in get_compiled_capabilities().items():
        binding = compiled.descriptor.binding
        if binding.kind != "uno-dispatch":
            continue
        if binding.dispatch_alias is not None:
            aliases[binding.dispatch_alias] = tool_id
    return aliases


def get_safe_formatting_tool_ids() -> frozenset[str]:
    return frozenset(
        tool_id
        for tool_id, compiled in get_compiled_capabilities().items()
        if compiled.descriptor.safety_class == SafetyClass.SAFE_FORMATTING
    )