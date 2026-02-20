"""Shared utilities for making Twilio+Deepgram voice calls and polling for results."""

from __future__ import annotations

import asyncio
import logging

import httpx

log = logging.getLogger(__name__)


async def initiate_call(base_url: str, phone: str, prompt: str, greeting: str) -> dict:
    """Start an outbound voice call via the local voice API."""
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                f"{base_url}/api/voice/call",
                json={
                    "to_number": phone,
                    "prompt": prompt,
                    "start_message": greeting,
                },
            )
            if resp.status_code == 200:
                return resp.json()
            log.error("Voice call API returned %s: %s", resp.status_code, resp.text[:300])
            return {"error": resp.text, "status": "failed"}
        except Exception as exc:
            log.exception("Failed to initiate call")
            return {"error": str(exc), "status": "failed"}


async def poll_for_transcript(base_url: str, call_id: str, timeout: int = 600) -> dict:
    """Poll the voice API until call completes or timeout is reached."""
    async with httpx.AsyncClient(timeout=10) as client:
        elapsed = 0
        interval = 3
        while elapsed < timeout:
            await asyncio.sleep(interval)
            elapsed += interval
            try:
                resp = await client.get(f"{base_url}/api/voice/call/{call_id}")
                data = resp.json()
                status = data.get("status", "")
                if status == "completed":
                    log.info("Call %s completed after %ds", call_id, elapsed)
                    return data
                if status == "unknown":
                    return {"status": "unknown", "transcript_text": ""}
            except Exception:
                pass
            if elapsed > 30:
                interval = 5
    log.warning("Call %s polling timed out after %ds", call_id, timeout)
    return {"status": "timeout", "transcript_text": ""}
