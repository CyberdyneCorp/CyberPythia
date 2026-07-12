"""#82 (CWE-89-like): free-text memory search must treat LIKE metacharacters
literally, not as wildcards, and cap the query length."""

from app.infrastructure.persistence.repositories.misc import (
    _MAX_MEMORY_QUERY_LEN,
    _like_contains,
)


def test_percent_and_underscore_are_escaped():
    # `%` and `_` are user data, not wildcards: they must be backslash-escaped so
    # the pattern matches them literally (paired with ilike(escape="\\")).
    assert _like_contains("a%b_c") == "%a\\%b\\_c%"


def test_backslash_is_escaped_first():
    assert _like_contains("a\\b") == "%a\\\\b%"


def test_query_length_capped():
    pattern = _like_contains("x" * (_MAX_MEMORY_QUERY_LEN + 50))
    # Outer wildcards + the capped literal only.
    assert pattern == "%" + "x" * _MAX_MEMORY_QUERY_LEN + "%"
