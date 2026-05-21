from dataclasses import dataclass
from datetime import datetime, UTC


@dataclass(slots=True)
class AuditEvent:
    event_type: str
    message: str
    created_at: str

    @classmethod
    def create(cls, event_type: str, message: str) -> "AuditEvent":
        return cls(event_type=event_type, message=message, created_at=datetime.now(UTC).isoformat())
