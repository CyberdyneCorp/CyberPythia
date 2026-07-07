"""AnswerPort adapter: LLM answer synthesis over retrieved context (design OQ1)."""

from openai import AsyncOpenAI

from app.config import get_settings

SYSTEM_PROMPT = (
    "You answer questions about a software repository using ONLY the provided "
    "context blocks. Each block is prefixed with its source path in brackets. "
    "Cite sources inline as [path]. If the context does not contain the answer, "
    "say so explicitly instead of guessing."
)


class OpenAIAnswerer:
    def __init__(self, client: AsyncOpenAI | None = None, model: str = "gpt-4o-mini") -> None:
        self._api_key = get_settings().openai_api_key
        self._injected = client
        self._model = model

    @property
    def _client_instance(self) -> AsyncOpenAI:
        if self._injected is None:
            self._injected = AsyncOpenAI(api_key=self._api_key)
        return self._injected

    async def answer(self, question: str, context_blocks: list[str]) -> str:
        if not self._api_key and self._injected is None:
            # Degraded mode (no API key): extractive answer from the top sources.
            joined = "\n\n".join(context_blocks[:3])
            return f"Based on the indexed context:\n\n{joined}"
        context = "\n\n".join(context_blocks)
        response = await self._client_instance.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
            ],
            temperature=0.1,
        )
        return response.choices[0].message.content or ""
