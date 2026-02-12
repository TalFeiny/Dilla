"""
Company full-history analysis: POST company-history (async/sync), GET job status.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class CompanyHistoryRequest(BaseModel):
    company_ids: Optional[List[str]] = Field(None, description="Limit to these companies")
    document_ids: Optional[List[str]] = Field(None, description="Limit to these documents")
    async_mode: bool = Field(True, description="If true, enqueue Celery task and return job_id; else run sync (long timeout)")


class CompanyHistoryResponse(BaseModel):
    job_id: Optional[str] = None
    status: Optional[str] = None
    result: Optional[dict] = None
    message: Optional[str] = None


@router.post("/{fund_id}/analysis/company-history", response_model=CompanyHistoryResponse)
async def post_company_history(fund_id: str, body: CompanyHistoryRequest):
    """
    Run company full-history pipeline: resolve docs, bulk extract, aggregate per company,
    follow-on/round/ownership analytics, portfolio-relative (DPI Sankey).
    Default: async (returns job_id). Use async_mode=false for synchronous run (long timeout).
    """
    if not fund_id:
        raise HTTPException(status_code=400, detail="fund_id required")
    try:
        if body.async_mode:
            from app.tasks import run_company_history_analysis
            task = run_company_history_analysis.delay(
                fund_id=fund_id,
                company_ids=body.company_ids,
                document_ids=body.document_ids,
            )
            return CompanyHistoryResponse(
                job_id=task.id,
                status="queued",
                message="Analysis queued; poll GET /api/portfolio/{fund_id}/analysis/jobs/{job_id} for status",
            )
        else:
            from app.core.adapters import get_storage, get_document_repo, get_company_repo
            from app.services.company_history_analysis_service import run as run_pipeline
            storage = get_storage()
            document_repo = get_document_repo()
            company_repo = get_company_repo()
            result = run_pipeline(
                fund_id=fund_id,
                company_ids=body.company_ids,
                document_ids=body.document_ids,
                storage=storage,
                document_repo=document_repo,
                company_repo=company_repo,
            )
            return CompanyHistoryResponse(status="completed", result=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error("Company history runtime error: %s", e)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Company history failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{fund_id}/analysis/jobs/{job_id}")
async def get_analysis_job(fund_id: str, job_id: str):
    """
    Return status and result for an async company-history job.
    job_id is the Celery task id returned from POST company-history.
    """
    try:
        from app.core.celery_app import celery_app
        res = celery_app.AsyncResult(job_id)
        state = res.state
        info = res.info if isinstance(res.info, dict) else ({"message": str(res.info)} if res.info else {})
        if state == "SUCCESS" and res.result:
            return {"status": state.lower(), "progress": info, "result": res.result}
        if state == "FAILURE":
            return {"status": "failure", "error": str(res.result) if res.result else info.get("error", "Unknown error")}
        return {"status": state.lower() if state else "pending", "progress": info}
    except Exception as e:
        logger.warning("Job status failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
