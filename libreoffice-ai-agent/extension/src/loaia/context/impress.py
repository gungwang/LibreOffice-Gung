from loaia_shared.schema.messages import ContextEnvelope, SelectionContext


def extract_impress_selection(text: str) -> ContextEnvelope:
    return ContextEnvelope(selection=SelectionContext(mimeType="text/plain", text=text))
