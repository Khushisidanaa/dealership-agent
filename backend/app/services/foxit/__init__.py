"""
Foxit PDF Services integration (hackathon requirement).

Upload a file to Foxit → they convert the PDF to text → we pass that text to our
agent for processing (summarization, Carfax analysis, negotiation context, etc.).
"""

from app.services.foxit.doc_analysis import (
    extract_text_from_file,
    get_document_text_for_agent,
    analyze_document,
)

__all__ = [
    "extract_text_from_file",
    "get_document_text_for_agent",
    "analyze_document",
]
