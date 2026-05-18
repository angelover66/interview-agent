"""LLM API 封装 — 统一调用入口，支持 Anthropic / OpenAI 兼容接口（DeepSeek 等）"""
from __future__ import annotations
import json
import os
from typing import Optional
from pathlib import Path

import yaml
import httpx


# ─── .env 文件加载 ────────────────────────────────────────

def _load_dotenv():
    """从项目根目录 .env 文件加载环境变量（不覆盖已有值）。"""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value

_load_dotenv()


_config: dict = {}

# OpenAI 兼容 API 的默认地址
_PROVIDER_BASE_URLS = {
    "deepseek": "https://api.deepseek.com",
    "openai": "https://api.openai.com/v1",
}


def _load_config() -> dict:
    global _config
    if not _config:
        config_path = Path(__file__).parent.parent / "config.yaml"
        if config_path.exists():
            _config = yaml.safe_load(config_path.read_text())
    return _config


def _get_config_value(key: str, default=None):
    conf = _load_config()
    return conf.get("llm", {}).get(key, default)


def _get_provider() -> str:
    return _get_config_value("provider", "deepseek")


def _get_model() -> str:
    return _get_config_value("model", "deepseek-chat")


def _get_api_key() -> str:
    # 优先级: 环境变量 > 配置文件
    provider = _get_provider()
    env_keys = {
        "anthropic": "ANTHROPIC_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "openai": "OPENAI_API_KEY",
    }
    env_var = env_keys.get(provider, "LLM_API_KEY")
    key = os.environ.get(env_var) or _get_config_value("api_key", "")
    return key


def _get_max_tokens() -> int:
    return _get_config_value("max_tokens", 4096)


def _get_temperature() -> float:
    return _get_config_value("temperature", 0.7)


# ─── Claude (Anthropic SDK) ────────────────────────────

def _chat_anthropic(
    system: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> str:
    from anthropic import Anthropic

    api_key = _get_api_key()
    model = _get_model()
    client = Anthropic(api_key=api_key)

    kwargs = {
        "model": model,
        "system": system,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if json_mode:
        kwargs["system"] = (kwargs["system"]
                            + "\n\n你必须只返回合法的 JSON 对象，不要包含其他任何内容。").strip()

    resp = client.messages.create(**kwargs)
    return resp.content[0].text


# ─── OpenAI 兼容接口 (DeepSeek / OpenAI / 其它) ────────

def _chat_openai_compat(
    system: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> str:
    provider = _get_provider()
    base_url = _PROVIDER_BASE_URLS.get(provider, "https://api.deepseek.com")
    api_key = _get_api_key()
    model = _get_model()

    # 构建 OpenAI 格式的 messages
    openai_messages = []
    if system:
        openai_messages.append({"role": "system", "content": system})
    openai_messages.extend(messages)

    payload = {
        "model": model,
        "messages": openai_messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    url = f"{base_url.rstrip('/')}/v1/chat/completions"

    with httpx.Client(timeout=180.0) as client:
        resp = client.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"LLM API 错误 ({resp.status_code}): {resp.text[:500]}"
            )
        data = resp.json()
        return data["choices"][0]["message"]["content"]


# ─── 统一入口 ──────────────────────────────────────────

def chat(
    system: str = "",
    messages: list[dict] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    json_mode: bool = False,
) -> str:
    """
    统一 LLM 调用入口，自动根据 provider 选择后端。

    Args:
        system: System prompt
        messages: 消息列表 [{"role": "user"/"assistant", "content": "..."}]
        temperature: 温度
        max_tokens: 最大输出 token
        json_mode: 是否强制 JSON 输出

    Returns:
        模型回复文本
    """
    provider = _get_provider()
    messages = messages or []
    temperature = temperature if temperature is not None else _get_temperature()
    max_tokens = max_tokens or _get_max_tokens()

    if provider == "anthropic":
        return _chat_anthropic(system, messages, temperature, max_tokens, json_mode)
    else:
        return _chat_openai_compat(system, messages, temperature, max_tokens, json_mode)


def chat_json(
    system: str = "",
    messages: list[dict] = None,
    temperature: Optional[float] = None,
) -> dict:
    """调用 LLM 并解析返回的 JSON。"""
    result = chat(system=system, messages=messages, temperature=temperature, json_mode=True)
    # 清理可能的 markdown 包围
    result = result.strip()
    if result.startswith("```"):
        result = result.split("\n", 1)[-1]
        result = result.rsplit("```", 1)[0]
    return json.loads(result.strip())
