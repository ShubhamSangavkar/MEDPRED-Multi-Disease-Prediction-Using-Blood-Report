
# python "C:\xampp\htdocs\MEGA_PROJECT\Backend\Api\app.py"

from __future__ import annotations

import os
import tempfile
import shutil
import logging
import hmac
import hmac
from typing import List

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Any

from lab_report_extractor import extract_report
from feature_standardizer import standardize_tests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lab_report_api")

MAX_FILE_SIZE_MB = 25
ALLOWED_CONTENT_TYPES = {"application/pdf"}

app = FastAPI(
    title="Lab Report Extractor API",
    description="Upload a medical lab report PDF (any template/lab) and "
                 "get back structured test-name / result / unit / "
                 "reference-range rows as JSON.",
    version="1.0.0",
)

API_KEY = os.environ.get("MEDPREDICT_API_KEY", "").strip()

@app.middleware("http")
async def require_api_key(request, call_next):
    # Keep health/docs available for deployment checks and developer reference.
    if request.url.path in {"/health", "/docs", "/openapi.json", "/redoc"}:
        return await call_next(request)
    # Set MEDPREDICT_API_KEY in the hosting dashboard. Without it, local development remains convenient.
    if API_KEY:
        supplied = request.headers.get("x-medpredict-key", "")
        if not hmac.compare_digest(supplied, API_KEY):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)




class TestRow(BaseModel):
    test_name: str
    result: str
    unit: str = ""
    ref_range: str = ""
    flag: str = ""
    section: str = ""
    source_page: int
    source_file: str


class ExtractResponse(BaseModel):
    filename: str
    row_count: int
    rows: List[TestRow]


# class BatchExtractResponse(BaseModel):
#     results: List[ExtractResponse]
#     errors: List[dict] = []

def _validate_upload(file: UploadFile) -> None:
    if file.content_type not in ALLOWED_CONTENT_TYPES and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail=f"Only PDF files are accepted (got content_type={file.content_type!r}, "
                   f"filename={file.filename!r}).",
        )


def _save_upload_to_temp(file: UploadFile) -> str:
    suffix = ".pdf"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    size = 0
    with open(tmp_path, "wb") as out:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_FILE_SIZE_MB * 1024 * 1024:
                out.close()
                os.remove(tmp_path)
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large; limit is {MAX_FILE_SIZE_MB} MB.",
                )
            out.write(chunk)
    return tmp_path


def _run_extraction(tmp_path: str, original_filename: str) -> ExtractResponse:
    try:
        rows = extract_report(tmp_path)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Extraction failed for %s", original_filename)
        raise HTTPException(
            status_code=422,
            detail=f"Could not extract data from {original_filename!r}: {exc}",
        ) from exc

    
    for r in rows:
        r["source_file"] = original_filename

    return ExtractResponse(
        filename=original_filename,
        row_count=len(rows),
        rows=rows,  # pydantic will coerce dicts -> TestRow
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}


@app.post("/extract", response_model=ExtractResponse, tags=["extraction"])
async def extract_single(file: UploadFile = File(..., description="A lab report PDF")):
    """Upload a single PDF and get back structured test rows."""
    _validate_upload(file)
    tmp_path = _save_upload_to_temp(file)
    try:
        return _run_extraction(tmp_path, file.filename)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# @app.post("/extract/batch", response_model=BatchExtractResponse, tags=["extraction"])
# async def extract_batch(files: List[UploadFile] = File(..., description="Multiple lab report PDFs")):
#     """Upload several PDFs in one request; each is processed independently.
#     A failure on one file does not abort the others -- it is reported in
#     the `errors` list instead."""
#     results: List[ExtractResponse] = []
#     errors: List[dict] = []

#     for file in files:
#         try:
#             _validate_upload(file)
#         except HTTPException as exc:
#             errors.append({"filename": file.filename, "error": exc.detail})
#             continue

#         tmp_path = _save_upload_to_temp(file)
#         try:
#             results.append(_run_extraction(tmp_path, file.filename))
#         except HTTPException as exc:
#             errors.append({"filename": file.filename, "error": exc.detail})
#         finally:
#             if os.path.exists(tmp_path):
#                 os.remove(tmp_path)

#     return BatchExtractResponse(results=results, errors=errors)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):  # noqa: ANN001
    logger.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


#------------------FEATURE SELECTION ___________________



class StandardizeRequest(BaseModel):
    tests: list[dict[str, Any]]


@app.post("/standardize")
def standardize_endpoint(request: StandardizeRequest):
    return standardize_tests(request.tests)



# ------------------------------------------------------------------------
from liver_api import router as liver_router

app.include_router(liver_router)

from diabetes_api import router as diabetes_router

app.include_router(diabetes_router)

from kidney_api import router as kidney_router

app.include_router(kidney_router)







if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

































"""
app.py
======
FastAPI wrapper around lab_report_extractor.py.

Run locally:
    pip install -r requirements.txt
    uvicorn app:app --reload --port 8000

Then open http://127.0.0.1:8000/docs for interactive Swagger UI, or:

    curl -X POST "http://127.0.0.1:8000/extract" \
         -F "file=@/path/to/report.pdf"

Endpoints
---------
GET  /health            -> liveness check
POST /extract           -> upload ONE pdf, get structured JSON back
POST /extract/batch     -> upload MULTIPLE pdfs, get JSON per file

Response shape for /extract:
{
    "filename": "report.pdf",
    "page_count": 13,
    "row_count": 42,
    "rows": [
        {
            "test_name": "Haemoglobin",
            "result": "13.6",
            "unit": "gm/dL",
            "ref_range": "13.0 - 17.0",
            "flag": "",
            "section": "CBC",
            "source_page": 6,
            "source_file": "report.pdf"
        },
        ...
    ]
}
"""