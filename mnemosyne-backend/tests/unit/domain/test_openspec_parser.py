from app.domain.services.openspec_parser import (
    find_change_folders,
    interesting_files,
    parse_change,
)

PATHS = [
    "openspec/project.md",
    "openspec/changes/add-auth/proposal.md",
    "openspec/changes/add-auth/tasks.md",
    "openspec/changes/add-auth/specs/auth/spec.md",
    "openspec/changes/add-auth/specs/rest-api/spec.md",
    "openspec/changes/archive/2026-01-15-add-billing/proposal.md",
    "changes/legacy-change/proposal.md",
    "src/main.py",
]


class TestFindChangeFolders:
    def test_finds_active_archived_and_legacy_roots(self):
        folders = find_change_folders(PATHS)
        assert folders == {
            "openspec/changes/add-auth": "add-auth",
            "openspec/changes/archive/2026-01-15-add-billing": "2026-01-15-add-billing",
            "changes/legacy-change": "legacy-change",
        }

    def test_no_openspec_content(self):
        assert find_change_folders(["src/a.py", "README.md"]) == {}


class TestParseChange:
    def test_active_change_with_artifacts(self):
        contents = {
            "openspec/changes/add-auth/proposal.md": "# Proposal",
            "openspec/changes/add-auth/tasks.md": "- [ ] 1.1",
        }
        parsed = parse_change("openspec/changes/add-auth", "add-auth", PATHS, contents)
        assert parsed.change_id == "add-auth"
        assert parsed.status == "active"
        assert parsed.proposal == "# Proposal"
        assert parsed.tasks == "- [ ] 1.1"
        assert parsed.design is None
        assert parsed.affected_specs == ["auth", "rest-api"]
        assert parsed.content_hash  # stable hash for change detection

    def test_archived_change_normalizes_id(self):
        parsed = parse_change(
            "openspec/changes/archive/2026-01-15-add-billing",
            "2026-01-15-add-billing",
            PATHS,
            {},
        )
        assert parsed.status == "archived"
        assert parsed.change_id == "add-billing"

    def test_content_hash_changes_with_content(self):
        a = parse_change("changes/x", "x", [], {"changes/x/proposal.md": "v1"})
        b = parse_change("changes/x", "x", [], {"changes/x/proposal.md": "v2"})
        assert a.content_hash != b.content_hash


def test_interesting_files():
    assert interesting_files("changes/x") == [
        "changes/x/proposal.md",
        "changes/x/design.md",
        "changes/x/tasks.md",
    ]
