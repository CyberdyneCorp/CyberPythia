"""Caller identity resolved from a CyberdyneAuth token (spec: auth)."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CallerIdentity:
    """Identity and authorization claims of an authenticated caller.

    Populated exclusively from a validated CyberdyneAuth token or its
    introspection response — never from local state (design D2).

    CyberdyneAuth models access differently per token type:
    - user tokens carry ``entitlements`` (``product_key`` or ``product_key:plan``)
    - service tokens carry an ``aud`` audience instead (entitlements are
      user-only in CyberdyneAuth; client scopes are registry-validated)
    """

    subject: str
    username: str | None = None
    client_id: str | None = None
    scopes: frozenset[str] = field(default_factory=frozenset)
    entitlements: frozenset[str] = field(default_factory=frozenset)
    audiences: frozenset[str] = field(default_factory=frozenset)
    is_admin: bool = False
    # Read/query-only credential (e.g. a Mnemosyne API key). Such callers may read
    # but SHALL NOT invoke mutating operations, even with the required entitlement
    # (CWE-269).
    is_read_only: bool = False

    def has_entitlement(self, product_key: str) -> bool:
        """Exact product key, tolerating plan-qualified tokens (`key:plan`)."""
        return any(
            e == product_key or e.startswith(f"{product_key}:") for e in self.entitlements
        )

    def can_access(self, required_entitlement: str, service_audience: str | None = None) -> bool:
        if self.is_admin or self.has_entitlement(required_entitlement):
            return True
        if required_entitlement in self.scopes:
            return True
        return service_audience is not None and service_audience in self.audiences

    def can_administer(self, admin_scope: str) -> bool:
        return self.is_admin or admin_scope in self.scopes

    def allowed_organizations(self, product_key: str) -> frozenset[str] | None:
        """Organizations this caller may access, lower-cased. ``None`` = unrestricted.

        Scoping is expressed via plan-qualified entitlements ``product_key:<org>``.
        A caller is unrestricted (``None``) when they are admin, hold the bare
        ``product_key`` entitlement, or were admitted by scope/audience without a
        plan-qualified entitlement (service tokens). A caller whose only grant is
        one or more ``product_key:<org>`` plans is restricted to those orgs.
        """
        if self.is_admin:
            return None
        plans: set[str] = set()
        for e in self.entitlements:
            if e == product_key:
                return None  # bare entitlement -> full access
            if e.startswith(f"{product_key}:"):
                plans.add(e.split(":", 1)[1].lower())
        return frozenset(plans) if plans else None
