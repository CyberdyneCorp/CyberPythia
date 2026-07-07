import pytest

from app.domain.services.file_importance import (
    classify_importance,
    detect_language,
    file_extension,
)


class TestImportance:
    @pytest.mark.parametrize(
        ("path", "kind"),
        [
            ("package.json", "dependency_manifest"),
            ("backend/pyproject.toml", "dependency_manifest"),
            ("requirements-dev.txt", "dependency_manifest"),
            ("go.mod", "dependency_manifest"),
            ("Dockerfile", "container"),
            ("Dockerfile.coolify", "container"),
            ("docker-compose.dev.yml", "container"),
            (".github/workflows/ci.yml", "ci_workflow"),
            ("infra/main.tf", "infrastructure"),
            ("api/openapi.json", "api_spec"),
            ("k8s/deployment.yaml", "kubernetes"),
            ("justfile", "task_runner"),
            ("alembic.ini", "database"),
        ],
    )
    def test_important(self, path, kind):
        assert classify_importance(path) == kind

    @pytest.mark.parametrize("path", ["src/app.py", "README.md", "data.yaml"])
    def test_not_important(self, path):
        assert classify_importance(path) is None


class TestLanguage:
    @pytest.mark.parametrize(
        ("path", "language"),
        [
            ("src/app.py", "Python"),
            ("web/App.svelte", "Svelte"),
            ("contracts/Token.sol", "Solidity"),
            ("rtl/core.sv", "SystemVerilog"),
            ("Makefile", None),
            ("lib/utils.unknownext", None),
        ],
    )
    def test_detect(self, path, language):
        assert detect_language(path) == language

    def test_extension(self):
        assert file_extension("a/b/c.TAR.GZ") == "gz"
        assert file_extension("LICENSE") is None
