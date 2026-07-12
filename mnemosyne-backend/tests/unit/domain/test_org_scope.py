"""Fail-closed org-scope boundary (spec: auth, #76, CWE-284).

The default (UNSET) must deny every org so an entrypoint that forgets to set a
scope cannot leak cross-org data. Only an explicit unrestricted grant, or a
matching restricted set, may allow access.
"""

from app.domain.services.org_scope import (
    is_organization_allowed,
    is_unrestricted,
    reset_org_scope,
    set_allowed_organizations,
    set_unrestricted,
)


def test_unset_scope_denies_everything():
    # NB: the autouse conftest fixture sets None; force the real production default.
    reset_org_scope()
    assert is_organization_allowed("cyberdyne") is False
    assert is_organization_allowed("anything") is False
    assert is_unrestricted() is False


def test_unrestricted_allows_every_org():
    set_unrestricted()
    assert is_organization_allowed("cyberdyne") is True
    assert is_organization_allowed("aminitech") is True
    assert is_unrestricted() is True


def test_restricted_set_allows_only_members_case_insensitive():
    set_allowed_organizations(frozenset({"cyberdyne"}))
    assert is_organization_allowed("CyberDyne") is True  # owner is lower-cased
    assert is_organization_allowed("aminitech") is False
    assert is_unrestricted() is False


def test_empty_restricted_set_denies_all_but_is_not_unset():
    # An explicit empty allow-list is a real restriction (deny-all), distinct from
    # UNSET, and must NOT read as unrestricted.
    set_allowed_organizations(frozenset())
    assert is_organization_allowed("cyberdyne") is False
    assert is_unrestricted() is False


def test_reset_returns_to_fail_closed_default():
    set_unrestricted()
    assert is_organization_allowed("cyberdyne") is True
    reset_org_scope()  # e.g. between requests — no bleed of the previous grant
    assert is_organization_allowed("cyberdyne") is False
    assert is_unrestricted() is False
