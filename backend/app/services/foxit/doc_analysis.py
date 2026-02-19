"""
Document analysis using Foxit PDF Services API.

Flow:
  1. Upload the file to Foxit → they convert the PDF (or doc) to text.
  2. We get back the extracted text.
  3. That text is passed to our agent for processing (e.g. summarization, negotiation
     context, Carfax highlights, or other downstream logic).

So: upload to Foxit → Foxit returns text → pass that text to the agent.

Use for: Carfax PDFs, inspection reports, and other vehicle docs.
"""

import asyncio
import logging
from pathlib import Path
from typing import BinaryIO, Union

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Foxit API (upload → extract → poll → download)
# ---------------------------------------------------------------------------


async def _upload_document(content: bytes, filename: str) -> str:
    """Upload file to Foxit; returns documentId."""
    settings = get_settings()
    if not settings.foxit_client_id or not settings.foxit_client_secret:
        raise ValueError("Foxit credentials not configured (FOXIT_CLIENT_ID, FOXIT_CLIENT_SECRET)")

    url = f"{settings.foxit_api_host.rstrip('/')}/pdf-services/api/documents/upload"
    headers = {
        "client_id": settings.foxit_client_id,
        "client_secret": settings.foxit_client_secret,
    }
    files = {"file": (filename or "document.pdf", content)}

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, files=files)
        resp.raise_for_status()
        data = resp.json()
    return data["documentId"]


async def _start_extract_task(document_id: str, extract_type: str = "TEXT") -> str:
    """Start pdf-extract job; returns taskId."""
    settings = get_settings()
    url = f"{settings.foxit_api_host.rstrip('/')}/pdf-services/api/documents/modify/pdf-extract"
    headers = {
        "client_id": settings.foxit_client_id,
        "client_secret": settings.foxit_client_secret,
        "Content-Type": "application/json",
    }
    body = {"documentId": document_id, "extractType": extract_type}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
    return data["taskId"]


async def _poll_task_until_done(task_id: str, poll_interval: float = 2.0) -> str:
    """Poll task status; returns resultDocumentId when COMPLETED."""
    settings = get_settings()
    url = f"{settings.foxit_api_host.rstrip('/')}/pdf-services/api/tasks/{task_id}"
    headers = {
        "client_id": settings.foxit_client_id,
        "client_secret": settings.foxit_client_secret,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status", "").upper()
            if status == "COMPLETED":
                return data["resultDocumentId"]
            if status == "FAILED":
                raise RuntimeError(f"Foxit task failed: {data}")
            logger.debug("Foxit task %s: %s (progress: %s)", task_id, status, data.get("progress"))
            await asyncio.sleep(poll_interval)


async def _download_result(document_id: str) -> str:
    """Download extracted text result by resultDocumentId."""
    settings = get_settings()
    url = f"{settings.foxit_api_host.rstrip('/')}/pdf-services/api/documents/{document_id}/download"
    headers = {
        "client_id": settings.foxit_client_id,
        "client_secret": settings.foxit_client_secret,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def extract_text_from_file(
    content: bytes,
    filename: str = "document.pdf",
) -> str:
    """
    Upload the file to Foxit; they convert the PDF to text and we return it.

    This is the text you pass to the agent for processing (summarization, context
    for negotiation, Carfax analysis, etc.). Use as-is or feed into analyze_document
    for an LLM summary on top.
    """
    doc_id = await _upload_document(content, filename)
    task_id = await _start_extract_task(doc_id, extract_type="TEXT")
    result_doc_id = await _poll_task_until_done(task_id)
    return await _download_result(result_doc_id)


async def get_document_text_for_agent(
    content: bytes,
    filename: str = "document.pdf",
) -> str:
    """
    Same as extract_text_from_file: upload to Foxit, get back text.

    Use this when the next step is to pass the result to the agent. The returned
    string is ready to be sent to the agent for processing.
    """
    return await extract_text_from_file(content, filename)


async def extract_text_from_path(file_path: Union[str, Path]) -> str:
    """Convenience: read file from disk and extract text."""
    path = Path(file_path)
    content = path.read_bytes()
    return await extract_text_from_file(content, path.name)


async def analyze_document(
    content: bytes,
    filename: str = "document.pdf",
    *,
    include_summary: bool = True,
) -> dict:
    """
    Upload to Foxit → get text → pass that text to our agent (LLM) for processing.

    Returns full extracted text plus an optional agent-generated summary (e.g. for
    Carfax: accidents, title history, service, red flags). The agent processes the
    Foxit-extracted text to produce the summary.

    Returns:
      - extracted_text: full text from Foxit (what we pass to the agent)
      - summary: agent output when include_summary=True and OpenAI key set
    """
    extracted = await extract_text_from_file(content, filename)
    result: dict = {"extracted_text": extracted, "summary": None}

    if not include_summary:
        return result

    settings = get_settings()
    if not settings.openai_api_key:
        result["summary"] = (
            "Summary not available (OpenAI key not set). Use extracted_text for full content."
        )
        return result

    # Use LLM to summarize, especially for vehicle/Carfax-style content
    import openai

    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    prompt = """Summarize this vehicle document (e.g. Carfax, inspection report) in a short, clear way.
Highlight: title history, accidents or damage, service history, mileage/odometer, number of owners, and any red flags.
If it's not a vehicle document, summarize the main points.
Keep the summary to 1–2 short paragraphs."""

    # Truncate if very long to stay within token limits
    text_for_llm = extracted if len(extracted) <= 12000 else extracted[:12000] + "\n\n[Document truncated.]"

    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text_for_llm},
        ],
        temperature=0.3,
        max_tokens=600,
    )
    result["summary"] = (response.choices[0].message.content or "").strip()
    return result
