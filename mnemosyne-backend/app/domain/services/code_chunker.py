"""Pure-Python heuristic code chunker (design D2).

Splits source into symbol-bounded chunks for supported languages, with a
windowed fallback for everything else. Deterministic. No native deps — a
tree-sitter-backed adapter can replace this behind CodeChunkerPort later.

Strategy: detect keyword-declared symbols (class/func/interface/struct/…)
reliably, bound each by brace balance (brace languages) or dedent (Python),
window the lines not covered by any symbol as `module` chunks, then
sub-split any oversized chunk into overlapping windows. Retrieval embeds the
chunk text regardless of perfect boundaries, so conservative detection with
full windowed coverage beats aggressive misdetection.
"""

import re

from app.domain.ports.code_chunker_port import CodeChunk
from app.domain.value_objects.enums import ChunkType

BRACE_LANGUAGES = frozenset(
    {
        "C", "C++", "Java", "Go", "TypeScript", "JavaScript", "Svelte",
        "Solidity", "Rust", "Kotlin", "PHP", "SystemVerilog", "Verilog",
    }
)  # fmt: skip
INDENT_LANGUAGES = frozenset({"Python"})

_KEYWORD_TO_TYPE = {
    "class": ChunkType.CLASS,
    "interface": ChunkType.INTERFACE,
    "struct": ChunkType.STRUCT,
    "trait": ChunkType.INTERFACE,
    "enum": ChunkType.CLASS,
    "impl": ChunkType.CLASS,
    "func": ChunkType.FUNCTION,
    "function": ChunkType.FUNCTION,
    "fn": ChunkType.FUNCTION,
    "def": ChunkType.FUNCTION,
}

_BRACE_DECL = re.compile(
    r"^\s*(?:(?:export|public|private|protected|internal|static|async|final"
    r"|abstract|pub|const|virtual|override|inline)\s+)*"
    r"(?P<kw>class|interface|struct|trait|enum|impl|func|function|fn)\b"
    r"\s*(?P<name>[A-Za-z_]\w*)?"
)
# C-family function without a keyword: `int main() {`, `static void f(x) {`.
# Excludes control statements and anything ending in `;` (calls / prototypes).
_C_FUNC = re.compile(
    r"^\s*(?!(?:if|for|while|switch|return|else|do|catch|sizeof)\b)"
    r"(?:[A-Za-z_][\w:<>\*&,\[\]\s]*?\s+[\*&]?)+"
    r"(?P<name>[A-Za-z_]\w*)\s*\([^;{]*\)\s*(?:const|noexcept|override|final)?\s*\{?\s*$"
)
_PY_DECL = re.compile(r"^(?P<indent>\s*)(?:async\s+)?(?P<kw>def|class)\s+(?P<name>[A-Za-z_]\w*)")


class HeuristicCodeChunker:
    def __init__(
        self, window_lines: int = 80, overlap: int = 10, max_chunk_lines: int = 120
    ) -> None:
        self._window = window_lines
        self._overlap = overlap
        self._max = max_chunk_lines

    def chunk(self, path: str, content: str, language: str | None) -> list[CodeChunk]:
        lines = content.split("\n")
        if not any(line.strip() for line in lines):
            return []
        if language in INDENT_LANGUAGES:
            spans = self._python_spans(lines)
        elif language in BRACE_LANGUAGES:
            spans = self._brace_spans(lines)
        else:
            spans = []
        chunks = self._assemble(lines, spans)
        return [c for chunk in chunks for c in self._enforce_max(chunk)]

    # -- symbol detection ----------------------------------------------------

    def _brace_spans(self, lines: list[str]) -> list[tuple[int, int, ChunkType, str | None]]:
        spans: list[tuple[int, int, ChunkType, str | None]] = []
        i = 0
        n = len(lines)
        while i < n:
            match = _BRACE_DECL.match(lines[i])
            if match is not None:
                end = self._brace_body_end(lines, i)
                ctype = _KEYWORD_TO_TYPE.get(match.group("kw"), ChunkType.FUNCTION)
                spans.append((i, end, ctype, match.group("name")))
                i = end + 1
                continue
            fmatch = _C_FUNC.match(lines[i])
            if fmatch is not None and self._has_body(lines, i):
                end = self._brace_body_end(lines, i)
                spans.append((i, end, ChunkType.FUNCTION, fmatch.group("name")))
                i = end + 1
                continue
            i += 1
        return spans

    @staticmethod
    def _has_body(lines: list[str], start: int) -> bool:
        """A C-style signature is a function only if a `{` opens within a few lines."""
        return any("{" in lines[j] for j in range(start, min(start + 3, len(lines))))

    def _brace_body_end(self, lines: list[str], start: int) -> int:
        """End line index of a brace-delimited body starting at/after `start`."""
        depth = 0
        seen_open = False
        for j in range(start, len(lines)):
            depth += lines[j].count("{") - lines[j].count("}")
            if "{" in lines[j]:
                seen_open = True
            if seen_open and depth <= 0:
                return j
            # signature with no body brace within a few lines (e.g. forward decl)
            if not seen_open and j - start > 4:
                return j
        return len(lines) - 1

    def _python_spans(self, lines: list[str]) -> list[tuple[int, int, ChunkType, str | None]]:
        spans: list[tuple[int, int, ChunkType, str | None]] = []
        for i, line in enumerate(lines):
            match = _PY_DECL.match(line)
            if match is None or line.strip().startswith("#"):
                continue
            indent = len(match.group("indent"))
            end = self._python_body_end(lines, i, indent)
            ctype = ChunkType.CLASS if match.group("kw") == "class" else ChunkType.FUNCTION
            spans.append((i, end, ctype, match.group("name")))
        return _dedupe_nested(spans)

    def _python_body_end(self, lines: list[str], start: int, indent: int) -> int:
        end = start
        for j in range(start + 1, len(lines)):
            stripped = lines[j].strip()
            if not stripped:
                continue
            if len(lines[j]) - len(lines[j].lstrip()) <= indent:
                return end
            end = j
        return len(lines) - 1

    # -- assembly ------------------------------------------------------------

    def _assemble(
        self, lines: list[str], spans: list[tuple[int, int, ChunkType, str | None]]
    ) -> list[CodeChunk]:
        """Emit symbol chunks + `module` window chunks for uncovered lines."""
        chunks: list[CodeChunk] = []
        cursor = 0
        for start, end, ctype, name in spans:
            if start > cursor:
                chunks += self._module_windows(lines, cursor, start - 1)
            chunks.append(_chunk(lines, start, end, ctype, name))
            cursor = end + 1
        if cursor < len(lines):
            chunks += self._module_windows(lines, cursor, len(lines) - 1)
        if not chunks:  # unsupported language / no symbols
            chunks += self._module_windows(lines, 0, len(lines) - 1)
        return chunks

    def _module_windows(self, lines: list[str], start: int, end: int) -> list[CodeChunk]:
        if not any(lines[k].strip() for k in range(start, end + 1)):
            return []
        return [
            CodeChunk(ChunkType.MODULE if self._is_module(lines, s, e) else ChunkType.WINDOW,
                      None, s + 1, e + 1, "\n".join(lines[s : e + 1]))
            for s, e in self._windows(start, end)
        ]

    def _is_module(self, lines: list[str], start: int, end: int) -> bool:
        return end - start + 1 <= self._window  # single-window gap reads as a module region

    def _windows(self, start: int, end: int) -> list[tuple[int, int]]:
        if end - start + 1 <= self._window:
            return [(start, end)]
        out: list[tuple[int, int]] = []
        s = start
        step = max(1, self._window - self._overlap)
        while s <= end:
            out.append((s, min(s + self._window - 1, end)))
            if s + self._window - 1 >= end:
                break
            s += step
        return out

    def _enforce_max(self, chunk: CodeChunk) -> list[CodeChunk]:
        span = chunk.end_line - chunk.start_line + 1
        if span <= self._max:
            return [chunk]
        lines = chunk.content.split("\n")
        return [
            CodeChunk(chunk.chunk_type, chunk.symbol_name,
                      chunk.start_line + s, chunk.start_line + e,
                      "\n".join(lines[s : e + 1]))
            for s, e in self._windows(0, len(lines) - 1)
        ]


def _chunk(
    lines: list[str], start: int, end: int, ctype: ChunkType, name: str | None
) -> CodeChunk:
    return CodeChunk(ctype, name, start + 1, end + 1, "\n".join(lines[start : end + 1]))


def _dedupe_nested(
    spans: list[tuple[int, int, ChunkType, str | None]],
) -> list[tuple[int, int, ChunkType, str | None]]:
    """Keep only top-level spans (a method inside a class is covered by the class)."""
    spans = sorted(spans, key=lambda s: (s[0], -s[1]))
    kept: list[tuple[int, int, ChunkType, str | None]] = []
    covered_until = -1
    for span in spans:
        if span[0] > covered_until:
            kept.append(span)
            covered_until = span[1]
    return kept
