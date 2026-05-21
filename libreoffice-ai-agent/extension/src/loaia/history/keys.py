from loaia_shared.types import AppType


def build_session_key(profile_id: str, canonical_document_url: str, app_type: AppType) -> str:
    return f"{profile_id}::{app_type.value}::{canonical_document_url}"
