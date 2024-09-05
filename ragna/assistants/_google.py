from typing import AsyncIterator, Union

from ragna.core import Message, Source

from ._http_api import HttpApiAssistant, HttpStreamingProtocol


class GoogleAssistant(HttpApiAssistant):
    _API_KEY_ENV_VAR = "GOOGLE_API_KEY"
    _STREAMING_PROTOCOL = HttpStreamingProtocol.JSON
    _MODEL: str

    @classmethod
    def display_name(cls) -> str:
        return f"Google/{cls._MODEL}"

    def _instructize_prompt(self, prompt: str, sources: list[Source]) -> str:
        # https://ai.google.dev/docs/prompt_best_practices#add-contextual-information
        return "\n".join(
            [
                "Answer the prompt using only the pieces of context below.",
                "If you don't know the answer, just say so. Don't try to make up additional context.",
                f"Prompt: {prompt}",
                *[f"\n{source.content}" for source in sources],
            ]
        )

    def _render_prompt(self, prompt: Union[str, list[Message]]) -> list[dict]:
        # need to verify against https://ai.google.dev/api/generate-content#chat_1
        role_mapping = {"user": "user", "assistant": "model"}
        if isinstance(prompt, str):
            messages = [Message(content=prompt, role=MessageRole.USER)]
        else:
            messages = prompt
        messages = [
            {"parts": [{"text": i["content"]}], "role": role_mapping[i["role"]]}
            for i in messages
            if i["role"] != "system"
        ]
        return messages

    async def generate(
        self, prompt: Union[str, list[Message]], *, max_new_tokens: int = 256
    ) -> AsyncIterator[str]:
        """
        Primary method for calling assistant inference, either as a one-off request from anywhere in ragna, or as part of self.answer()
        This method should be called for tasks like pre-processing, agentic tasks, or any other user-defined calls.

        Args:
            prompt: Either a single prompt string or a list of ragna messages
            max_new_tokens: Max number of completion tokens (default 256)

        Returns:
            async streamed inference response string chunks
        """
        async with self._call_api(
            "POST",
            f"https://generativelanguage.googleapis.com/v1beta/models/{self._MODEL}:streamGenerateContent",
            params={"key": self._api_key},
            headers={"Content-Type": "application/json"},
            json={
                "contents": _render_prompt(prompt),
                # https://ai.google.dev/docs/safety_setting_gemini
                "safetySettings": [
                    {
                        "category": f"HARM_CATEGORY_{category}",
                        "threshold": "BLOCK_NONE",
                    }
                    for category in [
                        "HARASSMENT",
                        "HATE_SPEECH",
                        "SEXUALLY_EXPLICIT",
                        "DANGEROUS_CONTENT",
                    ]
                ],
                # https://ai.google.dev/tutorials/rest_quickstart#configuration
                "generationConfig": {
                    "temperature": 0.0,
                    "maxOutputTokens": max_new_tokens,
                },
            },
            parse_kwargs=dict(item="item.candidates.item.content.parts.item.text"),
        ) as stream:
            async for chunk in stream:
                yield chunk

    async def answer(
        self, messages: list[Message], *, max_new_tokens: int = 256
    ) -> AsyncIterator[str]:
        prompt, sources = (message := messages[-1]).content, message.sources
        expanded_prompt = self._instructize_prompt(prompt, sources)
        yield generate(prompt=expanded_prompt, max_new_tokens=max_new_tokens)


class GeminiPro(GoogleAssistant):
    """[Google Gemini Pro](https://ai.google.dev/models/gemini)

    !!! info "Required environment variables"

        - `GOOGLE_API_KEY`

    !!! info "Required packages"

        - `ijson`
    """

    _MODEL = "gemini-pro"


class GeminiUltra(GoogleAssistant):
    """[Google Gemini Ultra](https://ai.google.dev/models/gemini)

    !!! info "Required environment variables"

        - `GOOGLE_API_KEY`

    !!! info "Required packages"

        - `ijson`
    """

    _MODEL = "gemini-ultra"
