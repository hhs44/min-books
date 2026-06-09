"""Provider 注册表(详见 v2 plan §Phase B Task 10)。

- OpenAI 兼容协议:OpenAI / DeepSeek / 智谱 / Moonshot / Qwen
- 独立协议:Anthropic
- 本地: Ollama(OpenAI 兼容,默认 base_url 走 host.docker.internal)
"""
from .base import BaseProvider
from .openai_compat import OpenAICompatProvider
from .anthropic_provider import AnthropicProvider
from .ollama_provider import OllamaProvider


def get_provider(name: str, **kwargs) -> BaseProvider:
    """按 name 返回 provider 实例。"""
    match name:
        case "openai":
            return OpenAICompatProvider(
                name="openai",
                default_base="https://api.openai.com/v1",
                **kwargs,
            )
        case "deepseek":
            return OpenAICompatProvider(
                name="deepseek",
                default_base="https://api.deepseek.com/v1",
                **kwargs,
            )
        case "zhipu":
            return OpenAICompatProvider(
                name="zhipu",
                default_base="https://open.bigmodel.cn/api/paas/v4",
                **kwargs,
            )
        case "moonshot":
            return OpenAICompatProvider(
                name="moonshot",
                default_base="https://api.moonshot.cn/v1",
                **kwargs,
            )
        case "qwen":
            return OpenAICompatProvider(
                name="qwen",
                default_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
                **kwargs,
            )
        case "anthropic":
            return AnthropicProvider(**kwargs)
        case "ollama":
            return OllamaProvider(**kwargs)
        case _:
            raise ValueError(f"Unknown provider: {name}")
