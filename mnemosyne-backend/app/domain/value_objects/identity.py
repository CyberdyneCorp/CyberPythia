"""Caller identity resolved from a CyberdyneAuth token (spec: auth)."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CallerIdentity:
    """Identity and authorization claims of an authenticated caller.

    Populated exclusively from a validated CyberdyneAuth token or its
    introspection response — never from local state (design D2).
    """

    subject: str
    username: str | None = None
    client_id: str | None = None
    scopes: frozenset[str] = field(default_factory=frozenset)
    entitlements: frozenset[str] = field(default_factory=frozenset)
    is_admin: bool = False

    def has_entitlement(self, product: str) -> bool:
        return product in self.entitlements

    def can_access(self, required_entitlement: str) -> bool:
        return self.is_admin or self.has_entitlement(required_entitlement)

    def can_administer(self, admin_scope: str) -> bool:
        return self.is_admin or admin_scope in self.scopes
