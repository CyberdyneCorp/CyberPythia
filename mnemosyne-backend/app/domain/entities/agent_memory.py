"""Agent-writable memory: a durable note scoped to a repo or org (spec: agent-memory)."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

# Open vocabulary; the UI offers these, the store accepts any short string.
MEMORY_KINDS = ("note", "decision", "gotcha", "convention", "todo")


@dataclass(slots=True)
class AgentMemory:
    id: UUID
    content: str
    kind: str
    author: str
    created_at: datetime
    repository_id: UUID | None = None  # repo-scoped
    organization: str | None = None  # org-scoped (when repository_id is None)
