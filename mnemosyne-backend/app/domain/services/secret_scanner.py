"""Rule-based secret scanning before persistence or embedding (design D7).

Pattern rules catch well-known credential formats; an entropy rule
catches generic high-entropy assignments.
"""

import math
import re
from dataclasses import dataclass

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b")),
    ("github_fine_grained_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{60,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    (
        "generic_assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|password|token)\b\s*[:=]\s*['\"][^'\"\s]{16,}['\"]"
        ),
    ),
]

_ENTROPY_CANDIDATE = re.compile(r"['\"]([A-Za-z0-9+/=_-]{32,})['\"]")
_ENTROPY_THRESHOLD = 4.5


@dataclass(frozen=True, slots=True)
class SecretFinding:
    rule: str
    line_number: int


def _shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    frequencies = {c: value.count(c) for c in set(value)}
    length = len(value)
    return -sum((n / length) * math.log2(n / length) for n in frequencies.values())


def scan_for_secrets(content: str) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        for rule, pattern in _PATTERNS:
            if pattern.search(line):
                findings.append(SecretFinding(rule=rule, line_number=line_number))
                break
        else:
            for match in _ENTROPY_CANDIDATE.finditer(line):
                if _shannon_entropy(match.group(1)) >= _ENTROPY_THRESHOLD:
                    findings.append(SecretFinding(rule="high_entropy", line_number=line_number))
                    break
    return findings


def has_secrets(content: str) -> bool:
    return bool(scan_for_secrets(content))
