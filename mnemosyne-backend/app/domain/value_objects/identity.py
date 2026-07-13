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
    # Authorized organization set from CyberdyneAuth's `orgs` claim, as GitHub org
    # logins (lower-cased). ``None`` = the claim was absent (legacy token, or a
    # service/API-key identity that doesn't carry it) — fall back to the legacy
    # entitlement derivation. An empty frozenset = the claim was present but grants
    # no organizations (fail-closed). See CyberdyneAuth#104 / CyberPythia#77.
    authorized_org_logins: frozenset[str] | None = None

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
        """Organizations this caller may access, as GitHub org logins (lower-cased).
        ``None`` = unrestricted (all orgs).

        Admins are always unrestricted (``None``) — treating admin as unrestricted
        is our policy; the token reports real memberships regardless.

        The authoritative source is CyberdyneAuth's ``orgs`` claim (CyberdyneAuth#104),
        exposed as ``authorized_org_logins``. When the claim is present it wins: the
        caller is restricted to exactly those GitHub logins, and an empty set means
        "no organizations" (fail-closed) — a present-but-empty claim is NOT
        unrestricted.

        When the claim is absent (``authorized_org_logins is None`` — a legacy
        pre-``orgs`` token, a service token, or a Mnemosyne API key whose scope is
        encoded via ``product_key:<org>`` entitlements, #64) it falls back to the
        legacy plan-qualified-entitlement derivation for backward compatibility.
        """
        if self.is_admin:
            return None
        if self.authorized_org_logins is not None:
            return self.authorized_org_logins  # `orgs` claim is authoritative
        # Fallback (legacy tokens / service tokens / API keys): plan-qualified
        # entitlements ``product_key:<org>``; the bare entitlement is unrestricted.
        plans: set[str] = set()
        for e in self.entitlements:
            if e == product_key:
                return None  # bare entitlement -> full access
            if e.startswith(f"{product_key}:"):
                plans.add(e.split(":", 1)[1].lower())
        return frozenset(plans) if plans else None
