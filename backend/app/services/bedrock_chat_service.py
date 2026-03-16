"""
Amazon Bedrock chat (Converse API) for the conversational agent.

Uses DeepSeek V3.2 (or configurable model) via boto3 bedrock-runtime.
Reuses AWS credentials from config (same as Nova Act).
"""

import asyncio
import logging
from typing import Any, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


def _get_credentials() -> tuple[str, str]:
    """Return (access_key_id, secret_access_key)."""
    s = get_settings()
    ak = (s.aws_access_key_id or "").strip()
    sk = (s.aws_secret_access_key or "").strip()
    if not ak:
        import os
        ak = (os.environ.get("ACCESS_KEY") or "").strip()
    if not sk:
        import os
        sk = (os.environ.get("SECRET_ACCRESS_KEY") or "").strip()
    return ak, sk


def _converse_sync(
    system: Optional[str],
    messages: list[dict],
    *,
    model_id: str,
    region: str,
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> str:
    """Synchronous Converse API call. Returns assistant text content."""
    if not has_bedrock_configured():
        logger.debug("Bedrock not configured; skipping Converse call")
        return ""

    import boto3

    ak, sk = _get_credentials()
    kwargs = {"region_name": region}
    if ak and sk:
        kwargs["aws_access_key_id"] = ak
        kwargs["aws_secret_access_key"] = sk

    client = boto3.client("bedrock-runtime", **kwargs)

    converse_messages = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, str):
            content = [{"text": content}]
        elif isinstance(content, list) and content and isinstance(content[0], dict):
            pass
        else:
            content = [{"text": str(content)}]
        converse_messages.append({"role": role, "content": content})

    system_block = None
    if system:
        system_block = [{"text": system}]

    response = client.converse(
        modelId=model_id,
        messages=converse_messages,
        system=system_block,
        inferenceConfig={
            "maxTokens": max_tokens,
            "temperature": temperature,
        },
    )

    output = response.get("output", {})
    message = output.get("message", {})
    content_list = message.get("content", [])
    parts = []
    for block in content_list:
        if "text" in block:
            parts.append(block["text"])
        if "reasoningContent" in block:
            rc = block["reasoningContent"]
            if isinstance(rc, dict) and "reasoningText" in rc:
                # Optional: include reasoning; for chat we often skip to keep reply short
                pass
    return "".join(parts).strip()


async def invoke_converse(
    messages: list[dict],
    *,
    system: Optional[str] = None,
    model_id: Optional[str] = None,
    region: Optional[str] = None,
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> str:
    """
    Invoke Bedrock Converse API (async). Uses DeepSeek V3.2 by default.
    Returns "" when Bedrock is not configured (missing env vars); feature is disabled.
    """
    if not has_bedrock_configured():
        return ""

    s = get_settings()
    model_id = model_id or s.bedrock_chat_model_id or "deepseek.v3.2"
    region = region or s.bedrock_region or "us-east-1"

    return await asyncio.to_thread(
        _converse_sync,
        system,
        messages,
        model_id=model_id,
        region=region,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def invoke_converse_sync(
    messages: list[dict],
    *,
    system: Optional[str] = None,
    model_id: Optional[str] = None,
    region: Optional[str] = None,
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> str:
    """Synchronous Converse for use in sync LangGraph nodes. Returns "" when not configured."""
    if not has_bedrock_configured():
        return ""

    s = get_settings()
    model_id = model_id or s.bedrock_chat_model_id or "deepseek.v3.2"
    region = region or s.bedrock_region or "us-east-1"
    return _converse_sync(
        system,
        messages,
        model_id=model_id,
        region=region,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def has_bedrock_configured() -> bool:
    """True if Bedrock chat can be used (model id + credentials)."""
    ak, sk = _get_credentials()
    s = get_settings()
    model_id = (s.bedrock_chat_model_id or "deepseek.v3.2").strip()
    return bool(model_id and ak and sk)
