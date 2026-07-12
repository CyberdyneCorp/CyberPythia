"""#84 (CWE-327): the degraded-mode fallback feature-hash must not use md5.

Only used when OpenAI is unavailable, so no production embedding is affected; the
bucketing must stay deterministic under the replacement (blake2b).
"""

import hashlib

from app.infrastructure.vector.pgvector_store import _hash_embedding


def test_bucketing_uses_blake2b_not_md5():
    dims = 64
    token = "authentication"
    # blake2b bucket for the single token (matches the implementation).
    digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
    expected_index = int.from_bytes(digest[:4], "big") % dims

    vector = _hash_embedding(token, dims)

    nonzero = [i for i, v in enumerate(vector) if v != 0.0]
    assert nonzero == [expected_index]
    # md5 would bucket the same token elsewhere — guard against a silent revert.
    md5_index = int.from_bytes(hashlib.md5(token.encode()).digest()[:4], "big") % dims
    assert md5_index != expected_index


def test_hash_embedding_is_deterministic_and_normalized():
    dims = 64
    text = "context pack readiness score"
    first = _hash_embedding(text, dims)
    second = _hash_embedding(text, dims)
    assert first == second
    assert abs(sum(v * v for v in first) - 1.0) < 1e-9
