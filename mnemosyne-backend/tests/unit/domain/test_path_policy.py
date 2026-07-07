import pytest

from app.domain.services.path_policy import PathPolicy


class TestDefaultDenylist:
    @pytest.mark.parametrize(
        "path",
        [
            ".env",
            ".env.production",
            "certs/server.pem",
            "app.key",
            "data/app.sqlite",
            "secrets/api.txt",
            "credentials/gcp.json",
            "node_modules/pkg/index.js",
            "frontend/node_modules/x/y.js",
            "dist/bundle.js",
            "__pycache__/mod.pyc",
        ],
    )
    def test_denied(self, path):
        assert PathPolicy().is_ignored(path)

    @pytest.mark.parametrize("path", ["README.md", "src/app.py", "docs/env-setup.md"])
    def test_allowed(self, path):
        assert not PathPolicy().is_ignored(path)


class TestIgnoreFile:
    def test_parses_comments_and_blanks(self):
        content = "\n# never expose\ninternal/legal/\n\nsrc/payments/**\n*.snap\n"
        policy = PathPolicy.from_ignore_file(content)
        assert policy.is_ignored("internal/legal/contract.md")
        assert policy.is_ignored("src/payments/stripe/client.py")
        assert policy.is_ignored("ui/__snapshots__/x.snap")
        assert not policy.is_ignored("internal/eng/notes.md")

    def test_empty_ignore_file_keeps_defaults(self):
        policy = PathPolicy.from_ignore_file(None)
        assert policy.is_ignored(".env")

    def test_filter(self):
        policy = PathPolicy.from_ignore_file("private/\n")
        assert policy.filter(["README.md", "private/x.md"]) == ["README.md"]
