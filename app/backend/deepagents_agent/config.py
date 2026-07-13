"""
Agent 配置：使用项目统一的 Kimi / Moonshot 模型。
"""
from typing import Any

from langchain_openai import ChatOpenAI

from config import get_settings


def _is_kimi_k2(model_name: str) -> bool:
    """判断是否为 Kimi K2.x 系列模型。"""
    return model_name.startswith("kimi-k2")


def get_kimi_model(temperature: float = 0.2) -> ChatOpenAI:
    """
    返回配置好的 Kimi / Moonshot 聊天模型。

    Moonshot 提供 OpenAI 兼容接口，因此使用 langchain_openai.ChatOpenAI
    并指定 base_url 即可。

    针对 kimi-k2.6 等 K2 系列模型做特殊处理：
    - K2 系列固定 temperature=0.6（API 限制）
    - kimi-k2.6 关闭 thinking，避免 code-first 长 prompt 下响应过慢
    - 其他 K2 模型（如 kimi-k2.7-code）保持 thinking 开启
    """
    settings = get_settings()
    if not settings.LLM_API_KEY:
        raise RuntimeError(
            "未配置 LLM API Key，请设置环境变量 MOONSHOT_API_KEY "
            "或在 .env 中配置 LLM_API_KEY"
        )

    # LLM_API_URL 形如 https://api.moonshot.cn/v1/chat/completions
    # ChatOpenAI 需要 base_url 到 /v1 级别
    base_url = settings.LLM_API_URL.removesuffix("/chat/completions").removesuffix("/")

    # Agent 默认使用更大的上下文模型（如 32k 或 kimi-k2.6）
    model_name = settings.AGENT_LLM_MODEL or settings.LLM_MODEL

    kwargs: dict[str, Any] = {
        "model": model_name,
        "api_key": settings.LLM_API_KEY,
        "base_url": base_url,
    }

    if _is_kimi_k2(model_name):
        # K2 系列 API 要求 temperature=0.6
        kwargs["temperature"] = 0.6
        kwargs["max_tokens"] = 16384
        # kimi-k2.6 支持关闭 thinking，长 prompt 的 code-first 场景响应更快
        if model_name == "kimi-k2.6":
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        else:
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
    else:
        kwargs["temperature"] = temperature
        # 题库整理需要输出长 JSON，给足输出空间
        kwargs["max_tokens"] = 32768

    return ChatOpenAI(**kwargs)
