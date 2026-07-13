import pytest

from app.domain.value_objects.enums import IndexingMode
from app.domain.value_objects.full_name import InvalidFullNameError, RepositoryFullName
from app.domain.value_objects.identity import CallerIdentity


class TestRepositoryFullName:
    def test_parses_owner_and_name(self):
        fn = RepositoryFullName("CyberdyneCorp/CyberPythia")
        assert fn.owner == "CyberdyneCorp"
        assert fn.name == "CyberPythia"
        assert str(fn) == "CyberdyneCorp/CyberPythia"

    @pytest.mark.parametrize("bad", ["", "noslash", "a//b", "/x", "x/", "-bad/repo", "a/b/c"])
    def test_rejects_invalid(self, bad):
        with pytest.raises(InvalidFullNameError):
            RepositoryFullName(bad)

    def test_allows_dots_and_dashes_in_name(self):
        assert RepositoryFullName("org/my.repo-name_2").name == "my.repo-name_2"


class TestIndexingMode:
    def test_docs_only_excludes_everything_else(self):
        mode = IndexingMode.DOCS_ONLY
        assert not mode.includes_issues_and_prs
        assert not mode.includes_file_tree

    def test_project_intelligence_includes_issues_not_files(self):
        mode = IndexingMode.PROJECT_INTELLIGENCE
        assert mode.includes_issues_and_prs
        assert not mode.includes_file_tree

    def test_code_metadata_includes_all(self):
        mode = IndexingMode.CODE_METADATA
        assert mode.includes_issues_and_prs
        assert mode.includes_file_tree


class TestCallerIdentity:
    def test_entitled_caller_can_access(self):
        caller = CallerIdentity(subject="u1", entitlements=frozenset({"mnemosyne"}))
        assert caller.can_access("mnemosyne")

    def test_unentitled_caller_denied(self):
        caller = CallerIdentity(subject="u1", entitlements=frozenset({"other"}))
        assert not caller.can_access("mnemosyne")

    def test_admin_bypasses_entitlement(self):
        caller = CallerIdentity(subject="u1", is_admin=True)
        assert caller.can_access("mnemosyne")
        assert caller.can_administer("mnemosyne:admin")

    def test_admin_scope_grants_administration(self):
        caller = CallerIdentity(subject="u1", scopes=frozenset({"mnemosyne:admin"}))
        assert caller.can_administer("mnemosyne:admin")

    def test_plain_caller_cannot_administer(self):
        caller = CallerIdentity(subject="u1", entitlements=frozenset({"mnemosyne"}))
        assert not caller.can_administer("mnemosyne:admin")

    def test_bare_entitlement_is_unrestricted(self):
        caller = CallerIdentity(subject="u1", entitlements=frozenset({"mnemosyne"}))
        assert caller.allowed_organizations("mnemosyne") is None

    def test_admin_is_unrestricted(self):
        caller = CallerIdentity(subject="u1", is_admin=True)
        assert caller.allowed_organizations("mnemosyne") is None

    def test_plan_qualified_entitlement_restricts_to_orgs(self):
        caller = CallerIdentity(
            subject="u1", entitlements=frozenset({"mnemosyne:CyberdyneCorp", "mnemosyne:aminitech"})
        )
        assert caller.allowed_organizations("mnemosyne") == frozenset({"cyberdynecorp", "aminitech"})

    def test_bare_plus_plan_is_unrestricted(self):
        caller = CallerIdentity(
            subject="u1", entitlements=frozenset({"mnemosyne", "mnemosyne:CyberdyneCorp"})
        )
        assert caller.allowed_organizations("mnemosyne") is None

    def test_service_audience_only_is_unrestricted(self):
        caller = CallerIdentity(subject="svc", audiences=frozenset({"mnemosyne"}))
        assert caller.allowed_organizations("mnemosyne") is None

    def test_orgs_claim_restricts_to_github_logins(self):
        # The `orgs` claim (CyberdyneAuth#104) is authoritative when present.
        caller = CallerIdentity(
            subject="u1",
            entitlements=frozenset({"mnemosyne"}),
            authorized_org_logins=frozenset({"cyberdynecorp", "aminitech"}),
        )
        assert caller.allowed_organizations("mnemosyne") == frozenset(
            {"cyberdynecorp", "aminitech"}
        )

    def test_orgs_claim_empty_denies_all(self):
        # Present-but-empty claim = "no organizations" (fail-closed), NOT unrestricted.
        caller = CallerIdentity(
            subject="u1",
            entitlements=frozenset({"mnemosyne"}),
            authorized_org_logins=frozenset(),
        )
        assert caller.allowed_organizations("mnemosyne") == frozenset()

    def test_orgs_claim_overrides_plan_qualifier(self):
        # #77 fix: a real billing plan qualifier must NOT be read as an org when the
        # authoritative `orgs` claim is present.
        caller = CallerIdentity(
            subject="u1",
            entitlements=frozenset({"mnemosyne:premium"}),
            authorized_org_logins=frozenset({"acme"}),
        )
        assert caller.allowed_organizations("mnemosyne") == frozenset({"acme"})

    def test_orgs_claim_admin_still_unrestricted(self):
        # Admin policy wins over a (possibly empty) membership claim.
        caller = CallerIdentity(
            subject="u1", is_admin=True, authorized_org_logins=frozenset()
        )
        assert caller.allowed_organizations("mnemosyne") is None

    def test_absent_orgs_claim_falls_back_to_entitlements(self):
        # None = claim absent (legacy/service/API-key) -> legacy plan derivation.
        caller = CallerIdentity(
            subject="u1",
            entitlements=frozenset({"mnemosyne:cyberdynecorp"}),
            authorized_org_logins=None,
        )
        assert caller.allowed_organizations("mnemosyne") == frozenset({"cyberdynecorp"})


class TestCallerIdentityCyberdyneAuthModel:
    """Access rules matching CyberdyneAuth's real token shapes (design D2)."""

    def test_plan_qualified_entitlement_matches(self):
        caller = CallerIdentity(subject="u1", entitlements=frozenset({"cyb_50Udgx:pro"}))
        assert caller.can_access("cyb_50Udgx")

    def test_unrelated_prefix_does_not_match(self):
        caller = CallerIdentity(subject="u1", entitlements=frozenset({"cyb_50Udgxother"}))
        assert not caller.can_access("cyb_50Udgx")

    def test_service_token_with_audience(self):
        caller = CallerIdentity(subject="client:agent-1", audiences=frozenset({"mnemosyne"}))
        assert caller.can_access("cyb_50Udgx", "mnemosyne")

    def test_service_token_without_audience_denied(self):
        caller = CallerIdentity(subject="client:agent-1")
        assert not caller.can_access("cyb_50Udgx", "mnemosyne")

    def test_scope_carrying_entitlement_grants_access(self):
        caller = CallerIdentity(subject="u1", scopes=frozenset({"cyb_50Udgx"}))
        assert caller.can_access("cyb_50Udgx", "mnemosyne")


class TestFullContextMode:
    def test_code_context_includes_everything_but_full(self):
        m = IndexingMode.CODE_CONTEXT
        assert m.includes_issues_and_prs and m.includes_file_tree and m.includes_source_code

    def test_full_context_includes_all(self):
        m = IndexingMode.FULL_CONTEXT
        assert m.includes_issues_and_prs and m.includes_file_tree and m.includes_source_code

    def test_code_metadata_excludes_source(self):
        assert not IndexingMode.CODE_METADATA.includes_source_code

    def test_lower_modes_exclude_source(self):
        assert not IndexingMode.DOCS_ONLY.includes_source_code
        assert not IndexingMode.PROJECT_INTELLIGENCE.includes_source_code
