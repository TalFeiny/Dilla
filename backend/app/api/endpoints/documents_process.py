"""
Backend-agnostic document processing endpoint.
POST /process: download via storage, run extraction, update via document metadata repo.
POST /process-async: enqueue single doc to Celery (scale, rate-limit respect).
POST /process-batch: parallel batch processing via asyncio.gather + asyncio.to_thread.
POST /process-batch-stream: NDJSON streaming — sends per-doc progress as each completes.
POST /process-batch-async: enqueue each doc to Celery, return immediately.
"""

import asyncio
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any

from app.core.adapters import get_storage, get_document_repo
from app.services.document_process_service import run_document_process
import logging

logger = logging.getLogger(__name__)

# Lazy import to avoid loading Celery at module import
def _get_process_document_task():
    from app.tasks import process_document
    return process_document

router = APIRouter()

MAX_CONCURRENT_DOCS = 10
DOCUMENT_PROCESS_TIMEOUT = 300.0  # 5 min per doc, like deck agent


class DocumentProcessRequest(BaseModel):
    document_id: str = Field(..., description="Document ID (processed_documents.id)")

    @field_validator("document_id", mode="before")
    @classmethod
    def coerce_document_id(cls, v):
        if v is None:
            return ""
        return str(v)
    file_path: str = Field(..., description="Storage path of the file (e.g. in documents bucket)")
    document_type: Optional[str] = Field("other", description="Document type for extraction")
    company_id: Optional[str] = Field(None, description="Optional company to link after processing")
    fund_id: Optional[str] = Field(None, description="Optional fund to link after processing")


class DocumentProcessResponse(BaseModel):
    success: bool
    document_id: str
    message: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None


class DocumentProcessAsyncResponse(BaseModel):
    queued: bool = True
    document_id: str
    message: str = "Processing queued"


@router.post("/process-async", response_model=DocumentProcessAsyncResponse)
def process_document_async(body: DocumentProcessRequest):
    """
    Enqueue single document for background processing via Celery.
    Returns immediately. Use for scale and rate-limit respect.
    """
    if not body.document_id or not body.file_path:
        raise HTTPException(status_code=400, detail="document_id and file_path are required")
    try:
        task = _get_process_document_task()
        task.apply_async(
            args=[body.document_id, body.file_path],
            kwargs={
                "document_type": body.document_type or "other",
                "company_id": body.company_id,
                "fund_id": body.fund_id,
            },
        )
        return DocumentProcessAsyncResponse(
            queued=True,
            document_id=body.document_id,
            message="Processing queued",
        )
    except Exception as e:
        logger.exception("Failed to enqueue document process: %s", e)
        raise HTTPException(status_code=503, detail="Celery unavailable; cannot enqueue task")


@router.post("/process", response_model=DocumentProcessResponse)
async def process_document(body: DocumentProcessRequest):
    """
    Process a single document: download from configured storage, run extraction
    via document_process_service (run_document_process), write result to document metadata repo.
    """
    logger.info("Document process: document_id=%s", body.document_id)
    if not body.document_id or not body.file_path:
        raise HTTPException(status_code=400, detail="document_id and file_path are required")
    try:
        storage = get_storage()
        document_repo = get_document_repo()
        out = await asyncio.to_thread(
            run_document_process,
            document_id=body.document_id,
            storage_path=body.file_path,
            document_type=body.document_type or "other",
            storage=storage,
            document_repo=document_repo,
            company_id=body.company_id,
            fund_id=body.fund_id,
        )
        return DocumentProcessResponse(
            success=out.get("success", False),
            document_id=out.get("document_id", body.document_id),
            message="Document processed successfully" if out.get("success") else None,
            result=out.get("result"),
            error=out.get("error"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error("Process document runtime error: %s", e)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Process document failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


class DocumentBatchDocItem(BaseModel):
    document_id: str = Field(..., description="Document ID (processed_documents.id)")
    file_path: str = Field(..., description="Storage path of the file")
    document_type: Optional[str] = Field("other", description="Document type for extraction")
    company_id: Optional[str] = Field(None, description="Optional company to link after processing")
    fund_id: Optional[str] = Field(None, description="Optional fund to link after processing")


class DocumentBatchProcessRequest(BaseModel):
    documents: List[DocumentBatchDocItem] = Field(..., description="List of documents to process in parallel")


class DocumentBatchProcessResponse(BaseModel):
    results: List[Dict[str, Any]] = Field(..., description="Per-document results (success, document_id, error)")


def _normalize_batch_result(r: Any) -> Dict[str, Any]:
    """Normalize asyncio.gather result: exception or dict."""
    if isinstance(r, Exception):
        return {"success": False, "document_id": "?", "error": str(r)}
    if isinstance(r, dict):
        return r
    return {"success": False, "document_id": "?", "error": "unexpected result type"}


@router.post("/process-batch", response_model=DocumentBatchProcessResponse)
async def process_batch(body: DocumentBatchProcessRequest):
    """
    Process multiple documents in parallel via asyncio.gather + asyncio.to_thread.
    Modeled on deck agent's _execute_skill_chain pattern. Each doc has 5 min timeout.
    """
    if not body.documents:
        return DocumentBatchProcessResponse(results=[])

    storage = get_storage()
    document_repo = get_document_repo()
    sem = asyncio.Semaphore(MAX_CONCURRENT_DOCS)

    async def process_one(doc: DocumentBatchDocItem) -> Dict[str, Any]:
        async with sem:
            try:
                out = await asyncio.wait_for(
                    asyncio.to_thread(
                        run_document_process,
                        document_id=doc.document_id,
                        storage_path=doc.file_path,
                        document_type=doc.document_type or "other",
                        storage=storage,
                        document_repo=document_repo,
                        company_id=doc.company_id,
                        fund_id=doc.fund_id,
                    ),
                    timeout=DOCUMENT_PROCESS_TIMEOUT,
                )
                return {
                    "success": out.get("success", False),
                    "document_id": doc.document_id,
                    "result": out.get("result"),
                    "error": out.get("error"),
                }
            except asyncio.TimeoutError:
                return {"success": False, "document_id": doc.document_id, "error": "timeout"}
            except Exception as e:
                logger.warning("Batch process doc %s failed: %s", doc.document_id, e)
                return {"success": False, "document_id": doc.document_id, "error": str(e)}

    tasks = [process_one(d) for d in body.documents]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return DocumentBatchProcessResponse(
        results=[_normalize_batch_result(r) for r in results]
    )


@router.post("/process-batch-stream")
async def process_batch_stream(body: DocumentBatchProcessRequest):
    """
    Streaming batch processing — sends an NDJSON line for each document as it completes.
    Frontend can render progress incrementally instead of waiting for all docs.
    Each line: {"type": "progress"|"result"|"done", "document_id": ..., ...}
    """
    if not body.documents:
        return StreamingResponse(
            iter([json.dumps({"type": "done", "total": 0}) + "\n"]),
            media_type="application/x-ndjson",
        )

    storage = get_storage()
    document_repo = get_document_repo()
    sem = asyncio.Semaphore(MAX_CONCURRENT_DOCS)
    total = len(body.documents)

    async def stream_results():
        completed = 0
        # Yield initial progress
        yield json.dumps({"type": "progress", "message": f"Processing {total} document(s)...", "total": total, "completed": 0}) + "\n"

        async def process_one(doc: DocumentBatchDocItem) -> Dict[str, Any]:
            async with sem:
                try:
                    out = await asyncio.wait_for(
                        asyncio.to_thread(
                            run_document_process,
                            document_id=doc.document_id,
                            storage_path=doc.file_path,
                            document_type=doc.document_type or "other",
                            storage=storage,
                            document_repo=document_repo,
                            company_id=doc.company_id,
                            fund_id=doc.fund_id,
                        ),
                        timeout=DOCUMENT_PROCESS_TIMEOUT,
                    )
                    return {
                        "type": "result",
                        "success": out.get("success", False),
                        "document_id": doc.document_id,
                        "fields_extracted": (out.get("result") or {}).get("processing_summary", {}).get("fields_extracted", 0),
                        "error": out.get("error"),
                    }
                except asyncio.TimeoutError:
                    return {"type": "result", "success": False, "document_id": doc.document_id, "error": "timeout"}
                except Exception as e:
                    return {"type": "result", "success": False, "document_id": doc.document_id, "error": str(e)}

        # Use asyncio.as_completed to yield results as they finish (not all at once)
        tasks = {asyncio.ensure_future(process_one(d)): d for d in body.documents}
        for coro in asyncio.as_completed(tasks.keys()):
            result = await coro
            completed += 1
            result["completed"] = completed
            result["total"] = total
            yield json.dumps(result) + "\n"

        yield json.dumps({"type": "done", "total": total, "completed": completed}) + "\n"

    return StreamingResponse(stream_results(), media_type="application/x-ndjson")


class DocumentBatchProcessAsyncResponse(BaseModel):
    queued: bool = True
    document_ids: List[str] = Field(..., description="Document IDs enqueued")
    message: str = "Batch processing queued"


@router.post("/process-batch-async", response_model=DocumentBatchProcessAsyncResponse)
def process_batch_async(body: DocumentBatchProcessRequest):
    """
    Enqueue each document for background processing via Celery.
    Returns immediately. Use for scale and rate-limit respect.
    """
    if not body.documents:
        return DocumentBatchProcessAsyncResponse(document_ids=[], message="No documents to process")
    try:
        task = _get_process_document_task()
        doc_ids = []
        for doc in body.documents:
            task.apply_async(
                args=[doc.document_id, doc.file_path],
                kwargs={
                    "document_type": doc.document_type or "other",
                    "company_id": doc.company_id,
                    "fund_id": doc.fund_id,
                },
            )
            doc_ids.append(doc.document_id)
        return DocumentBatchProcessAsyncResponse(
            queued=True,
            document_ids=doc_ids,
            message=f"Queued {len(doc_ids)} document(s) for processing",
        )
    except Exception as e:
        logger.exception("Failed to enqueue batch: %s", e)
        raise HTTPException(status_code=503, detail="Celery unavailable; cannot enqueue tasks")
