"""Important-file detection for file-tree capture (spec: repository-sync)."""

import fnmatch

_IMPORTANT: list[tuple[str, str]] = [
    ("package.json", "dependency_manifest"),
    ("pyproject.toml", "dependency_manifest"),
    ("requirements*.txt", "dependency_manifest"),
    ("Cargo.toml", "dependency_manifest"),
    ("go.mod", "dependency_manifest"),
    ("pom.xml", "dependency_manifest"),
    ("build.gradle", "dependency_manifest"),
    ("build.gradle.kts", "dependency_manifest"),
    ("composer.json", "dependency_manifest"),
    ("Gemfile", "dependency_manifest"),
    ("uv.lock", "lockfile"),
    ("package-lock.json", "lockfile"),
    ("Dockerfile*", "container"),
    ("docker-compose*.yml", "container"),
    ("docker-compose*.yaml", "container"),
    ("compose*.yaml", "container"),
    (".github/workflows/*.yml", "ci_workflow"),
    (".github/workflows/*.yaml", "ci_workflow"),
    ("*.tf", "infrastructure"),
    ("*.tfvars", "infrastructure"),
    ("openapi.json", "api_spec"),
    ("openapi.yaml", "api_spec"),
    ("openapi.yml", "api_spec"),
    ("alembic.ini", "database"),
    ("justfile", "task_runner"),
    ("Makefile", "task_runner"),
]

_K8S_HINTS = ("k8s/", "kubernetes/", "manifests/")

_LANGUAGES: dict[str, str] = {
    "py": "Python",
    "ts": "TypeScript",
    "tsx": "TypeScript",
    "js": "JavaScript",
    "jsx": "JavaScript",
    "svelte": "Svelte",
    "go": "Go",
    "rs": "Rust",
    "cpp": "C++",
    "cc": "C++",
    "hpp": "C++",
    "c": "C",
    "h": "C",
    "java": "Java",
    "kt": "Kotlin",
    "rb": "Ruby",
    "php": "PHP",
    "sol": "Solidity",
    "sv": "SystemVerilog",
    "v": "Verilog",
    "sql": "SQL",
    "sh": "Shell",
    "yml": "YAML",
    "yaml": "YAML",
    "json": "JSON",
    "toml": "TOML",
    "md": "Markdown",
}


def classify_importance(path: str) -> str | None:
    """Return the importance kind for a path, or None."""
    basename = path.rsplit("/", 1)[-1]
    for pattern, kind in _IMPORTANT:
        target = path if "/" in pattern else basename
        if fnmatch.fnmatch(target, pattern):
            return kind
    if path.lower().startswith(_K8S_HINTS) and path.endswith((".yml", ".yaml")):
        return "kubernetes"
    return None


def detect_language(path: str) -> str | None:
    name = path.rsplit("/", 1)[-1]
    if "." not in name:
        return None
    return _LANGUAGES.get(name.rsplit(".", 1)[-1].lower())


def file_extension(path: str) -> str | None:
    name = path.rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[-1].lower() if "." in name else None
