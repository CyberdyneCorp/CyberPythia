"""Request-scoped organization access boundary (spec: auth).

A per-request/per-tool-call boundary consulted at the repository-store choke
point so every repository read is filtered to the caller's accessible orgs.

Three states, **fail-closed by default** (CWE-284):

- ``UNSET``          — no boundary has been established for this task. Denies
  every organization. This is the contextvar default, so an entrypoint that
  forgets to set a scope cannot leak cross-org data (fail-closed, not fail-open).
- ``None``           — unrestricted: admin/service HTTP callers, the background
  worker, and webhook processing. Set explicitly via :func:`set_unrestricted`.
- ``frozenset[str]`` — restricted to exactly these (lower-cased) organizations.

contextvars are task-local, so a value set in one request's task never leaks to
another. Legitimate all-org entrypoints (worker jobs, webhook processing) MUST
call :func:`set_unrestricted` at entry; per-caller HTTP/MCP paths set the
caller's own boundary.
"""

import contextvars
from typing import Final


class _Unset:
    """Sentinel type for the fail-closed default (no scope established)."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return "UNSET"


#: The deny-all default: no org boundary has been set for this task.
UNSET: Final[_Unset] = _Unset()

# frozenset = restricted to those orgs; None = unrestricted; UNSET = deny-all.
_allowed_orgs: contextvars.ContextVar[frozenset[str] | None | _Unset] = (
    contextvars.ContextVar("mnemosyne_allowed_orgs", default=UNSET)
)


def set_allowed_organizations(orgs: frozenset[str] | None) -> None:
    """Restrict the current task to ``orgs`` (``None`` = unrestricted, all orgs)."""
    _allowed_orgs.set(orgs)


def set_unrestricted() -> None:
    """Grant the current task access to every organization.

    For entrypoints that legitimately span all orgs and carry no per-caller
    boundary: background worker jobs and webhook processing. Admin/service HTTP
    callers reach this state implicitly because their identity resolves to a
    ``None`` (unrestricted) boundary.
    """
    _allowed_orgs.set(None)


def reset_org_scope() -> None:
    """Restore the fail-closed ``UNSET`` default (deny-all) for the current task."""
    _allowed_orgs.set(UNSET)


def allowed_organizations() -> frozenset[str] | None | _Unset:
    """The raw boundary: a ``frozenset`` (restricted), ``None`` (unrestricted),
    or ``UNSET`` (deny-all). Prefer :func:`is_unrestricted` /
    :func:`is_organization_allowed` unless you need the exact set."""
    return _allowed_orgs.get()


def is_unrestricted() -> bool:
    """True only when the caller may access every organization (``None`` scope).

    Distinct from ``UNSET``: an unset boundary is deny-all, not all-access.
    """
    return _allowed_orgs.get() is None


def is_organization_allowed(owner: str) -> bool:
    """True when the current caller may access repositories owned by ``owner``.

    Fail-closed: an ``UNSET`` boundary (the default) denies every owner, as does
    an owner outside a restricted set. Only ``None`` (unrestricted) allows all.
    """
    allowed = _allowed_orgs.get()
    if allowed is None:
        return True
    if isinstance(allowed, _Unset):
        return False
    return owner.lower() in allowed
