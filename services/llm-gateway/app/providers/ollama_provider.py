"""Ollama 本地模型适配器(OpenAI 兼容协议,默认 base_url 走 host.docker.internal)。"""
import os

from .openai_compat import OpenAICompatProvider


class OllamaProvider(OpenAICompatProvider):
    def __init__(self, **kwargs):
        super().__init__(
            name="ollama",
            default_base=os.environ.get(
                "OLLAMA_BASE_URL", "http://host.docker.internal:11434/v1"
            ),
            **kwargs,
        )
        # Ollama 默认不需要 API key,但 OpenAI SDK 要求非空
        if not self.api_key:
            self.api_key = "ollama"
