from app.domain.services.repository_signals import RepositorySignalsService
from app.domain.value_objects.enums import IndexingMode

svc = RepositorySignalsService()


def test_detects_ci_tests_manifest_license_contributing() -> None:
    paths = [
        "README.md",
        ".github/workflows/ci.yml",
        "tests/test_app.py",
        "pyproject.toml",
        "LICENSE",
        "CONTRIBUTING.md",
    ]
    s = svc.detect(paths, IndexingMode.CODE_METADATA)
    assert s.has_ci is True
    assert s.has_tests is True
    assert s.has_dependency_manifest is True
    assert s.has_license is True
    assert s.has_contributing is True


def test_absent_signals_are_false_not_unknown_when_tree_present() -> None:
    s = svc.detect(["README.md", "src/main.py"], IndexingMode.CODE_METADATA)
    assert s.has_ci is False
    assert s.has_tests is False
    assert s.has_license is False


def test_all_unknown_when_mode_has_no_tree() -> None:
    for mode in (IndexingMode.DOCS_ONLY, IndexingMode.PROJECT_INTELLIGENCE):
        s = svc.detect(["anything"], mode)
        assert s.has_ci is None
        assert s.has_tests is None
        assert s.has_dependency_manifest is None
        assert s.has_license is None
        assert s.has_contributing is None


def test_test_patterns() -> None:
    assert svc.detect(["app/foo_test.go"], IndexingMode.CODE_METADATA).has_tests is True
    assert svc.detect(["src/foo.spec.ts"], IndexingMode.CODE_METADATA).has_tests is True
    assert svc.detect(["__tests__/x.js"], IndexingMode.CODE_METADATA).has_tests is True
    assert svc.detect(["src/testament.py"], IndexingMode.CODE_METADATA).has_tests is False


def test_gitlab_and_requirements() -> None:
    s = svc.detect([".gitlab-ci.yml", "requirements-dev.txt"], IndexingMode.CODE_METADATA)
    assert s.has_ci is True
    assert s.has_dependency_manifest is True
