"""Request-scoped organization access boundary (spec: auth).

A per-request/per-tool-call allow-list of organizations (lower-cased), consulted
at the repository-store choke point so every repository read is filtered to the
caller's accessible organizations. ``None`` means unrestricted (admin, bare
entitlement, service token, or the background worker, which sets nothing).

contextvars are task-local, so a value set in one request's task never leaks to
another; the background worker never sets it and is therefore unrestricted.
"""

import contextvars

_allowed_orgs: contextvars.ContextVar[frozenset[str] | None] = contextvars.ContextVar(
    "mnemosyne_allowed_orgs", default=None
)


def set_allowed_organizations(orgs: frozenset[str] | None) -> None:
    """Set the accessible-org boundary for the current task (None = unrestricted)."""
    _allowed_orgs.set(orgs)


def allowed_organizations() -> frozenset[str] | None:
    return _allowed_orgs.get()


def is_organization_allowed(owner: str) -> bool:
    """True when the current caller may access repositories owned by ``owner``."""
    allowed = _allowed_orgs.get()
    return allowed is None or owner.lower() in allowed
