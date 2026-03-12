"""
Backend-agnostic document processing endpoint.
POST /process: download via storage, run extraction, update via document metadata repo.
POST /process-async: enqueue single doc to Celery (scale, rate-limit respect).
POST /process-batch: parallel batch processing via asyncio.gather + asyncio.to_thread.
POST /process-batch-stream: NDJSON streaming — sends per-doc progress as each completes.
  - 1 doc  → single-provider extraction via run_document_process
  - 2+ docs → multi-provider fan-out via ParallelDocProcessor.ingest_batch()
POST /process-batch-async: enqueue each doc to Celery, return immediately.
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any

from app.core.adapters import get_storage, get_document_repo
from app.services.document_process_service import run_document_process, run_post_extraction_pipeline, _text_from_file, _iso_now
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
    erp_category_hint: Optional[str] = Field(None, description="ERP category hint from P&L context")
    erp_subcategory_hint: Optional[str] = Field(None, description="ERP subcategory hint from P&L context")


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
            erp_category_hint=body.erp_category_hint,
            erp_subcategory_hint=body.erp_subcategory_hint,
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
    erp_category_hint: Optional[str] = Field(None, description="ERP category hint from P&L context (revenue, cogs, opex_rd, etc.)")
    erp_subcategory_hint: Optional[str] = Field(None, description="ERP subcategory hint from P&L context")


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
                        erp_category_hint=doc.erp_category_hint,
                        erp_subcategory_hint=doc.erp_subcategory_hint,
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

    Branching logic:
      - 1 doc  → existing single-provider path (run_document_process)
      - 2+ docs → ParallelDocProcessor.ingest_batch() with multi-provider fan-out
    """
    if not body.documents:
        return StreamingResponse(
            iter([json.dumps({"type": "done", "total": 0}) + "\n"]),
            media_type="application/x-ndjson",
        )

    storage = get_storage()
    document_repo = get_document_repo()
    total = len(body.documents)

    # ── 1 doc: existing single-provider path ──
    if total == 1:
        return StreamingResponse(
            _stream_single_doc(body.documents[0], storage, document_repo),
            media_type="application/x-ndjson",
        )

    # ── 2+ docs: ParallelDocProcessor with multi-provider fan-out ──
    return StreamingResponse(
        _stream_parallel_batch(body.documents, storage, document_repo),
        media_type="application/x-ndjson",
    )


async def _stream_single_doc(doc: DocumentBatchDocItem, storage, document_repo):
    """Single-doc path — delegates to run_document_process (existing behavior)."""
    sem = asyncio.Semaphore(MAX_CONCURRENT_DOCS)
    yield json.dumps({"type": "progress", "message": "Processing 1 document...", "total": 1, "completed": 0}) + "\n"
    try:
        async with sem:
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
                    erp_category_hint=doc.erp_category_hint,
                    erp_subcategory_hint=doc.erp_subcategory_hint,
                ),
                timeout=DOCUMENT_PROCESS_TIMEOUT,
            )
            yield json.dumps({
                "type": "result",
                "success": out.get("success", False),
                "document_id": doc.document_id,
                "fields_extracted": (out.get("result") or {}).get("processing_summary", {}).get("fields_extracted", 0),
                "error": out.get("error"),
                "completed": 1,
                "total": 1,
            }) + "\n"
    except asyncio.TimeoutError:
        yield json.dumps({"type": "result", "success": False, "document_id": doc.document_id, "error": "timeout", "completed": 1, "total": 1}) + "\n"
    except Exception as e:
        yield json.dumps({"type": "result", "success": False, "document_id": doc.document_id, "error": str(e), "completed": 1, "total": 1}) + "\n"
    yield json.dumps({"type": "done", "total": 1, "completed": 1}) + "\n"


async def _stream_parallel_batch(docs: List[DocumentBatchDocItem], storage, document_repo):
    """Multi-doc path — download + text extract, then ParallelDocProcessor.ingest_batch()."""
    from app.services.model_router import ModelRouter
    from app.services.parallel_doc_processor import ParallelDocProcessor

    total = len(docs)
    yield json.dumps({"type": "progress", "message": f"Processing {total} documents (multi-provider)...", "total": total, "completed": 0}) + "\n"

    # ── Phase 1: Download files and extract text in parallel ──
    yield json.dumps({"type": "progress", "message": "Downloading and extracting text...", "total": total, "completed": 0, "stage": "downloading"}) + "\n"

    # Build a map from doc_id → original doc item for DB writes later
    doc_item_map: Dict[str, DocumentBatchDocItem] = {d.document_id: d for d in docs}

    async def _download_and_extract_text(doc: DocumentBatchDocItem) -> Dict[str, Any]:
        """Download from storage, extract text, return {doc_id, text, file_name, doc_type} or {error}."""
        tmp_path = None
        try:
            content = await asyncio.to_thread(storage.download, doc.file_path)
            if not content:
                return {"doc_id": doc.document_id, "error": "Empty file from storage"}

            suffix = Path(doc.file_path).suffix or ".pdf"
            fd, tmp_path = tempfile.mkstemp(suffix=suffix, prefix="pdp_")
            try:
                os.write(fd, content)
            finally:
                os.close(fd)

            raw_text = await asyncio.to_thread(_text_from_file, tmp_path, suffix)
            if not raw_text.strip():
                return {"doc_id": doc.document_id, "error": "No text extracted from document"}

            return {
                "doc_id": doc.document_id,
                "text": raw_text,
                "file_name": Path(doc.file_path).name,
                "doc_type": doc.document_type or "other",
            }
        except Exception as e:
            logger.warning("[PARALLEL_BATCH] Download/text-extract failed for %s: %s", doc.document_id, e)
            return {"doc_id": doc.document_id, "error": str(e)}
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    text_results = await asyncio.gather(*[_download_and_extract_text(d) for d in docs])

    # Separate successes from failures
    ready_docs: List[Dict[str, Any]] = []
    download_errors = 0
    for tr in text_results:
        if tr.get("error"):
            download_errors += 1
            # Mark failed docs in DB
            try:
                document_repo.update(tr["doc_id"], {
                    "status": "failed",
                    "processing_summary": {"error": tr["error"], "updated_at": _iso_now()},
                })
            except Exception:
                pass
            yield json.dumps({
                "type": "result", "success": False, "document_id": tr["doc_id"],
                "error": tr["error"], "completed": download_errors, "total": total,
            }) + "\n"
        else:
            ready_docs.append(tr)

    if not ready_docs:
        yield json.dumps({"type": "done", "total": total, "completed": download_errors}) + "\n"
        return

    # ── Phase 2: Multi-provider LLM extraction via ParallelDocProcessor ──
    yield json.dumps({
        "type": "progress", "message": f"Running AI extraction on {len(ready_docs)} documents (multi-provider fan-out)...",
        "total": total, "completed": download_errors, "stage": "extracting",
    }) + "\n"

    router = ModelRouter()
    processor = ParallelDocProcessor(model_router=router, max_concurrent=MAX_CONCURRENT_DOCS)

    completed = download_errors
    async for event in processor.ingest_batch(ready_docs):
        event_type = event.get("type", "")

        if event_type == "doc_extracted":
            completed += 1
            doc_id = event.get("doc_id", "unknown")
            extracted_data = event.get("extracted_data", {})
            doc_item = doc_item_map.get(doc_id)

            # Write extracted data to DB (same as run_document_process does)
            field_count = sum(
                1 for k, v in extracted_data.items()
                if v is not None and k not in ("_extraction_error", "value_explanations", "period_date")
                and not (isinstance(v, (list, dict)) and len(v) == 0)
                and not (isinstance(v, str) and not v.strip())
            )
            try:
                # Find raw_text for preview from ready_docs
                raw_text = ""
                for rd in ready_docs:
                    if rd["doc_id"] == doc_id:
                        raw_text = rd.get("text", "")
                        break
                raw_text_preview = (raw_text[:5000] + "…") if len(raw_text) > 5000 else raw_text

                update_payload: Dict[str, Any] = {
                    "status": "completed",
                    "processed_at": _iso_now(),
                    "document_type": doc_item.document_type if doc_item else "other",
                    "extracted_data": extracted_data,
                    "issue_analysis": {},
                    "comparables_analysis": {},
                    "processing_summary": {
                        "step": "completed",
                        "message": f"Extraction completed — {field_count} fields extracted (parallel)",
                        "updated_at": _iso_now(),
                        "fields_extracted": field_count,
                        "text_length": len(raw_text),
                        "provider": event.get("provider", ""),
                    },
                    "raw_text_preview": raw_text_preview,
                }
                if doc_item and doc_item.company_id:
                    update_payload["company_id"] = doc_item.company_id
                if doc_item and doc_item.fund_id:
                    update_payload["fund_id"] = doc_item.fund_id
                document_repo.update(doc_id, update_payload)
            except Exception as e:
                logger.warning("[PARALLEL_BATCH] DB write failed for %s: %s", doc_id, e)

            # Run the full post-extraction pipeline (suggestions → grid upsert → bridges → cap table)
            try:
                await asyncio.to_thread(
                    run_post_extraction_pipeline,
                    extracted_data=extracted_data,
                    document_id=doc_id,
                    document_type=doc_item.document_type if doc_item else "other",
                    company_id=doc_item.company_id if doc_item else None,
                    fund_id=doc_item.fund_id if doc_item else None,
                    document_name=Path(doc_item.file_path).stem if doc_item else "",
                    field_count=field_count,
                )
            except Exception as e:
                logger.warning("[PARALLEL_BATCH] Post-extraction pipeline failed for %s: %s", doc_id, e)

            yield json.dumps({
                "type": "result", "success": True, "document_id": doc_id,
                "fields_extracted": field_count, "provider": event.get("provider", ""),
                "completed": completed, "total": total,
            }) + "\n"

        elif event_type == "doc_error":
            completed += 1
            doc_id = event.get("doc_id", "unknown")
            error_msg = event.get("error", "Unknown extraction error")
            try:
                document_repo.update(doc_id, {
                    "status": "failed",
                    "processing_summary": {"error": error_msg, "updated_at": _iso_now()},
                })
            except Exception:
                pass
            yield json.dumps({
                "type": "result", "success": False, "document_id": doc_id,
                "error": error_msg, "completed": completed, "total": total,
            }) + "\n"

        elif event_type == "doc_processing_progress":
            yield json.dumps({
                "type": "progress",
                "message": f"Extracting: {event.get('current_doc', '')}",
                "completed": completed,
                "total": total,
                "provider": event.get("provider", ""),
                "stage": event.get("stage", "extracting"),
            }) + "\n"

        elif event_type == "batch_complete":
            summary = event.get("summary", {})
            yield json.dumps({
                "type": "done", "total": total, "completed": completed,
                "providers_used": summary.get("providers_used", []),
                "succeeded": summary.get("succeeded", 0),
                "failed": summary.get("failed", 0) + download_errors,
            }) + "\n"


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
