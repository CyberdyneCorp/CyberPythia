"""Embedding inputs are truncated so a large chunk can't exceed the token limit.

Regression: a source chunk over 8192 tokens made the OpenAI embeddings call
400 ("maximum input length is 8192 tokens"), failing the whole sync.
"""

from types import SimpleNamespace

import httpx
import pytest
from openai import BadRequestError

from app.config import get_settings
from app.infrastructure.vector.pgvector_store import _HARD_INPUT_CHARS, PgVectorEmbeddingStore


def _too_long_error() -> BadRequestError:
    request = httpx.Request("POST", "https://api.openai.com/v1/embeddings")
    response = httpx.Response(400, request=request)
    return BadRequestError(
        "Error code: 400 - maximum input length is 8192 tokens.",
        response=response,
        body=None,
    )


class RecordingOpenAI:
    """Fake client that records inputs and optionally 400s on the first call."""

    def __init__(self, fail_first: bool = False) -> None:
        self.embeddings = SimpleNamespace(create=self._create)
        self.inputs: list[list[str]] = []
        self._fail_first = fail_first
        self.calls = 0

    async def _create(self, model, input, dimensions):
        self.calls += 1
        self.inputs.append(list(input))
        if self._fail_first and self.calls == 1:
            raise _too_long_error()
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.0]) for _ in input])


def _store(client: RecordingOpenAI) -> PgVectorEmbeddingStore:
    get_settings.cache_clear()  # ensure openai_api_key gate is bypassed by the client
    return PgVectorEmbeddingStore(session_factory=None, openai_client=client)  # type: ignore[arg-type]


async def test_input_truncated_to_soft_cap() -> None:
    client = RecordingOpenAI()
    store = _store(client)
    cap = get_settings().embedding_max_input_chars
    await store._embed_texts(["x" * (cap * 3)])
    assert len(client.inputs[0][0]) == cap  # truncated to the configured cap


async def test_retries_with_hard_cap_on_length_error() -> None:
    client = RecordingOpenAI(fail_first=True)
    store = _store(client)
    await store._embed_texts(["x" * 100_000])
    assert client.calls == 2  # soft cap failed, retried
    assert len(client.inputs[1][0]) == _HARD_INPUT_CHARS  # bulletproof retry
    assert _HARD_INPUT_CHARS <= 8192  # can never exceed the token limit


async def test_non_length_400_is_not_swallowed() -> None:
    client = RecordingOpenAI()

    async def _boom(model, input, dimensions):
        request = httpx.Request("POST", "https://api.openai.com/v1/embeddings")
        raise BadRequestError(
            "Error code: 400 - invalid model", response=httpx.Response(400, request=request), body=None
        )

    client.embeddings.create = _boom
    store = _store(client)
    with pytest.raises(BadRequestError):
        await store._embed_texts(["short"])
