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
