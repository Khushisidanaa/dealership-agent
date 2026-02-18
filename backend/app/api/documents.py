"""
Document analysis API: upload a PDF (e.g. Carfax, inspection report) and get
extracted text + optional summary. Powered by Foxit PDF Services + optional LLM.
"""

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.schemas import DocumentAnalysisResponse
from app.services.foxit import analyze_document

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_CONTENT_TYPES = {"application/pdf"}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB (Foxit limit)


@router.post("/analyze", response_model=DocumentAnalysisResponse)
async def analyze_uploaded_document(
    file: UploadFile = File(..., description="PDF or supported document (e.g. Carfax)"),
    include_summary: bool = True,
):
    """
    Upload a document and get full extracted text plus an optional summary.

    Use for Carfax reports, inspection reports, or any vehicle document.
    Extraction uses Foxit PDF Services; summary uses the app LLM when configured.
    """
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only PDF is supported. Content-Type must be application/pdf.",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)} MB.",
        )

    filename = file.filename or "document.pdf"
    try:
        result = await analyze_document(
            content,
            filename=filename,
            include_summary=include_summary,
        )
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Document analysis failed: {e}")

    return DocumentAnalysisResponse(
        extracted_text=result["extracted_text"],
        summary=result.get("summary"),
        filename=filename,
    )
