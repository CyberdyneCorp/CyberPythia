"""Path ignore rules: `.mnemosyneignore` + global denylist (spec: repository-sync).

Gitignore-style subset: `#` comments, `dir/` prefixes, `*` globs, `**`
recursive globs. Matching paths are excluded from capture and embedding.
"""

import fnmatch

DEFAULT_DENYLIST = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.crt",
    "*.p12",
    "*.sqlite",
    "*.db",
    "secrets/",
    "credentials/",
    "private/",
    "node_modules/",
    "dist/",
    "build/",
    "target/",
    ".venv/",
    "__pycache__/",
]

IGNORE_FILE_NAME = ".mnemosyneignore"


class PathPolicy:
    def __init__(self, rules: list[str] | None = None, *, include_defaults: bool = True) -> None:
        self._rules: list[str] = list(DEFAULT_DENYLIST) if include_defaults else []
        if rules:
            self._rules.extend(rules)

    @classmethod
    def from_ignore_file(cls, content: str | None) -> "PathPolicy":
        rules = []
        for line in (content or "").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                rules.append(stripped)
        return cls(rules)

    def is_ignored(self, path: str) -> bool:
        path = path.lstrip("/")
        segments = path.split("/")
        basename = segments[-1]
        for rule in self._rules:
            if rule.endswith("/"):
                directory = rule.rstrip("/")
                if "/" in directory:
                    # multi-segment directory rule: prefix match from the root
                    if path.startswith(directory + "/"):
                        return True
                elif any(fnmatch.fnmatch(seg, directory) for seg in segments[:-1]):
                    # single-segment directory rule: matches at any depth
                    return True
            elif "/" in rule:
                # path rule (may contain ** globs)
                pattern = rule.replace("**", "*")
                if fnmatch.fnmatch(path, pattern):
                    return True
            elif fnmatch.fnmatch(basename, rule):
                return True
        return False

    def filter(self, paths: list[str]) -> list[str]:
        return [p for p in paths if not self.is_ignored(p)]
