# Foxit PDF Services in the Dealership Agent

Foxit is a **hackathon requirement**. We use it to extract and analyze vehicle documents (Carfax, inspection reports, etc.) so the app can surface key info to users and use it in negotiation flows.

---

## What Foxit’s PDF Services Do

- **REST API** (no SDK required): upload a document, run jobs (extract, convert, merge, etc.), poll for completion, download results.
- **Extract API**: pull **TEXT**, **IMAGE**, or **PAGE** content from PDFs. We use **TEXT** to get full text from Carfax and other PDFs.
- **Auth**: `client_id` and `client_secret` from the [Foxit developer portal](https://app.developer-api.foxit.com/).
- **Flow**: Upload → create extract task → poll `GET /pdf-services/api/tasks/{taskId}` until `COMPLETED` → `GET /documents/{resultDocumentId}/download` for the extracted text.

So Foxit handles **document parsing and text extraction**; we add an **optional LLM summary** on top for a short, car-focused summary (accidents, title, service, red flags).

---

## Where It Fits in the App

| Use case | How we use Foxit |
|----------|-------------------|
| **Carfax / history reports** | User or system uploads a PDF → we extract all text → optionally summarize with LLM → show summary and/or raw text in UI or to the agent. |
| **Inspection / condition reports** | Same flow: extract text, summarize, use in vehicle comparison or negotiation. |
| **Future: forms/tables** | Foxit supports other endpoints; we can add a second integration (e.g. structured extraction) when needed. |

**Code layout:**

- **`backend/app/services/foxit/`** – Foxit integration:
  - **`doc_analysis.py`**: upload, extract text, optional LLM summary (`extract_text_from_file`, `analyze_document`).
- **`backend/app/api/documents.py`** – API:
  - **`POST /api/documents/analyze`**: upload a file, get `extracted_text` + `summary`.

So: **Foxit = extract from PDF; our service = extract + summarize; API = file in, text + summary out.**

---

## Config

In `.env` or environment:

- `FOXIT_CLIENT_ID` – from Foxit developer portal  
- `FOXIT_CLIENT_SECRET` – from Foxit developer portal  
- `FOXIT_API_HOST` – optional; default `https://na1.fusion.foxit.com`

---

## API Usage

```bash
curl -X POST "http://localhost:8000/api/documents/analyze?include_summary=true" \
  -F "file=@carfax_report.pdf"
```

Response:

```json
{
  "extracted_text": "Full text from the PDF...",
  "summary": "Short paragraph(s) on title history, accidents, service, red flags.",
  "filename": "carfax_report.pdf"
}
```

Use `include_summary=false` to get only `extracted_text` (no LLM call).

---

## Limits

- File size: 25 MB (Foxit limit; enforced in the API).
- Only PDF is accepted for the analyze endpoint; Foxit may support other types for other endpoints.
