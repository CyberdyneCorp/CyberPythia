from app.domain.services.code_chunker import HeuristicCodeChunker
from app.domain.value_objects.enums import ChunkType

chunker = HeuristicCodeChunker()


def symbols(chunks):
    return [(c.chunk_type, c.symbol_name) for c in chunks]


class TestPython:
    def test_top_level_def_and_class(self):
        src = (
            "import os\n"
            "\n"
            "def dispatch_kernels(n):\n"
            "    return n * 2\n"
            "\n"
            "class Backend:\n"
            "    def run(self):\n"
            "        return 1\n"
        )
        chunks = chunker.chunk("a.py", src, "Python")
        syms = symbols(chunks)
        assert (ChunkType.FUNCTION, "dispatch_kernels") in syms
        assert (ChunkType.CLASS, "Backend") in syms
        fn = next(c for c in chunks if c.symbol_name == "dispatch_kernels")
        assert "return n * 2" in fn.content

    def test_nested_methods_folded_into_class(self):
        src = "class A:\n    def m1(self):\n        pass\n    def m2(self):\n        pass\n"
        chunks = chunker.chunk("a.py", src, "Python")
        classes = [c for c in chunks if c.chunk_type is ChunkType.CLASS]
        assert len(classes) == 1
        assert "m1" in classes[0].content and "m2" in classes[0].content

    def test_comment_def_not_detected(self):
        src = "# def not_a_function():\nx = 1\n"
        chunks = chunker.chunk("a.py", src, "Python")
        assert all(c.symbol_name is None for c in chunks)


class TestBraceLanguages:
    def test_cpp_function_and_class(self):
        src = (
            "#include <cstdio>\n"
            "\n"
            "class GpuBackend {\n"
            "  public:\n"
            "    void dispatch() { run(); }\n"
            "};\n"
            "\n"
            "int main() {\n"
            "  return 0;\n"
            "}\n"
        )
        chunks = chunker.chunk("main.cpp", src, "C++")
        syms = symbols(chunks)
        assert (ChunkType.CLASS, "GpuBackend") in syms
        assert (ChunkType.FUNCTION, "main") in syms

    def test_go_func(self):
        src = "package main\n\nfunc Dispatch(n int) int {\n\treturn n\n}\n"
        chunks = chunker.chunk("m.go", src, "Go")
        assert (ChunkType.FUNCTION, "Dispatch") in symbols(chunks)

    def test_typescript_interface_and_function(self):
        src = (
            "export interface Backend {\n  run(): void;\n}\n"
            "\nexport function make(): Backend {\n  return null;\n}\n"
        )
        chunks = chunker.chunk("b.ts", src, "TypeScript")
        syms = symbols(chunks)
        assert (ChunkType.INTERFACE, "Backend") in syms
        assert (ChunkType.FUNCTION, "make") in syms

    def test_solidity_contract(self):
        src = "pragma solidity ^0.8;\n\ncontract Token {\n  function mint() public {}\n}\n"
        # 'contract' isn't in the keyword set; body still covered as module/window
        chunks = chunker.chunk("Token.sol", src, "Solidity")
        assert chunks  # full coverage
        assert "function mint" in "\n".join(c.content for c in chunks)


class TestFallback:
    def test_unsupported_language_windows(self):
        src = "\n".join(f"line {i}" for i in range(200))
        chunks = chunker.chunk("data.txt", src, None)
        assert chunks
        assert all(c.symbol_name is None for c in chunks)
        assert all(c.chunk_type in (ChunkType.WINDOW, ChunkType.MODULE) for c in chunks)
        # windowed with overlap -> multiple chunks for 200 lines
        assert len(chunks) > 1

    def test_empty_and_whitespace(self):
        assert chunker.chunk("a.py", "", "Python") == []
        assert chunker.chunk("a.py", "\n\n   \n", "Python") == []


class TestCoverageAndDeterminism:
    def test_full_line_coverage(self):
        src = (
            "TOP = 1\n"
            "def f():\n    return TOP\n"
            "BETWEEN = 2\n"
            "def g():\n    return BETWEEN\n"
            "BOTTOM = 3\n"
        )
        chunks = chunker.chunk("a.py", src, "Python")
        covered = set()
        for c in chunks:
            covered.update(range(c.start_line, c.end_line + 1))
        non_blank = {i for i, line in enumerate(src.split("\n"), start=1) if line.strip()}
        assert non_blank <= covered  # every code line is in some chunk

    def test_deterministic(self):
        src = "class A:\n    def m(self):\n        return 1\n" * 3
        a = chunker.chunk("a.py", src, "Python")
        b = chunker.chunk("a.py", src, "Python")
        assert [(c.chunk_type, c.symbol_name, c.start_line, c.end_line, c.content) for c in a] == [
            (c.chunk_type, c.symbol_name, c.start_line, c.end_line, c.content) for c in b
        ]

    def test_oversized_body_subsplit(self):
        body = "\n".join(f"    x{i} = {i}" for i in range(300))
        src = f"def big():\n{body}\n"
        chunks = chunker.chunk("a.py", src, "Python")
        assert len(chunks) > 1  # sub-split beyond max_chunk_lines
        assert all(c.end_line - c.start_line + 1 <= 120 for c in chunks)
