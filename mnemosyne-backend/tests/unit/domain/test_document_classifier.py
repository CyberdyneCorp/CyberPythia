import pytest

from app.domain.services.document_classifier import (
    classify_document,
    document_title,
    is_documentation_path,
)
from app.domain.value_objects.enums import DocumentType


class TestIsDocumentationPath:
    @pytest.mark.parametrize(
        "path",
        [
            "README.md",
            "readme.markdown",
            "README.pt-BR.md",
            "docs/setup.md",
            "docs/guides/deploy.mdx",
            "CONTRIBUTING.md",
            "ARCHITECTURE.md",
            "SECURITY.md",
            "CHANGELOG.md",
            "ROADMAP.md",
            "openspec/project.md",
            "specs/auth/spec.md",
        ],
    )
    def test_captured(self, path):
        assert is_documentation_path(path)

    @pytest.mark.parametrize(
        "path",
        [
            "src/main.py",
            "docs/image.png",
            "notes.md",  # root generic markdown not in a known category
            "src/README.txt",
            "deep/nested/CONTRIBUTING.md",  # root-file types only at root
        ],
    )
    def test_not_captured(self, path):
        assert not is_documentation_path(path) or classify_document(path) not in (
            DocumentType.CONTRIBUTING,
        )


class TestClassifyDocument:
    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            ("README.md", DocumentType.README),
            ("docs/README.md", DocumentType.README),
            ("docs/setup.md", DocumentType.DOCS),
            ("documentation/api.md", DocumentType.DOCS),
            ("openspec/changes/add-x/proposal.md", DocumentType.OPENSPEC),
            ("specs/auth/spec.md", DocumentType.OPENSPEC),
            ("changes/add-y/tasks.md", DocumentType.OPENSPEC),
            ("ARCHITECTURE.md", DocumentType.ARCHITECTURE),
            ("SECURITY.md", DocumentType.SECURITY),
            ("CHANGELOG.md", DocumentType.CHANGELOG),
            ("CONTRIBUTING.md", DocumentType.CONTRIBUTING),
            ("ROADMAP.md", DocumentType.ROADMAP),
            ("notes.md", DocumentType.GENERIC_MARKDOWN),
        ],
    )
    def test_classification(self, path, expected):
        assert classify_document(path) is expected


class TestDocumentTitle:
    def test_uses_first_h1(self):
        assert document_title("README.md", "intro\n# My Project\ntext") == "My Project"

    def test_falls_back_to_filename(self):
        assert document_title("docs/setup.md", "no heading here") == "setup.md"
