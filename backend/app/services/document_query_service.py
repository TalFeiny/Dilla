"""
Document Query Service - Query extracted_data JSONB from processed_documents
This service provides portfolio-aware querying of structured document data
without requiring complex RAG infrastructure.
Backend-agnostic: uses DocumentMetadataRepo and CompanyDataRepo when provided.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, TYPE_CHECKING
from datetime import datetime, timedelta
from enum import Enum
import json

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.abstractions.document_metadata import DocumentMetadataRepo
    from app.abstractions.company_data import CompanyDataRepo


class DocumentType(Enum):
    """Document types that can be queried"""
    BOARD_DECK = "board_deck"
    MONTHLY_UPDATE = "monthly_update"
    PITCH_DECK = "pitch_deck"
    FINANCIAL_STATEMENT = "financial_statement"
    COMPLIANCE_DOCUMENT = "compliance_document"
    LP_STATEMENT = "lp_statement"
    AUDIT_REPORT = "audit_report"
    REGULATORY_FILING = "regulatory_filing"
    FUND_DOCUMENT = "fund_document"
    INVESTMENT_MEMO = "investment_memo"
    OTHER = "other"


class MatrixQueryType(Enum):
    """Types of matrix queries supported"""
    FINANCIAL_METRICS = "financial_metrics"
    PORTFOLIO_COMPARISON = "portfolio_comparison"
    TIME_SERIES = "time_series"
    COMPANY_COMPARISON = "company_comparison"
    FUND_PERFORMANCE = "fund_performance"
    CUSTOM = "custom"


class DocumentQueryService:
    """
    Service for querying extracted_data JSONB from processed_documents.
    Portfolio-aware: filters by fund_id, company_id, and portfolio relationships.
    Backend-agnostic: pass document_repo and company_repo, or leave None to use adapters from config.
    """
    
    def __init__(
        self,
        document_repo: Optional["DocumentMetadataRepo"] = None,
        company_repo: Optional["CompanyDataRepo"] = None,
    ):
        self._document_repo = document_repo
        self._company_repo = company_repo
        self._supabase = None  # Legacy fallback
        if document_repo is None or company_repo is None:
            try:
                from app.core.adapters import get_document_repo, get_company_repo
                self._document_repo = self._document_repo or get_document_repo()
                self._company_repo = self._company_repo or get_company_repo()
                logger.info("DocumentQueryService using adapters from config")
            except Exception as e:
                logger.warning("DocumentQueryService adapters not available: %s; queries may be limited", e)
    
    def _doc_repo(self) -> Optional["DocumentMetadataRepo"]:
        return self._document_repo
    
    def _company_repo_opt(self) -> Optional["CompanyDataRepo"]:
        return self._company_repo
    
    def query_by_metric(
        self,
        metric_name: str,
        document_types: Optional[List[DocumentType]] = None,
        fund_id: Optional[str] = None,
        company_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Query documents by metric name from extracted_data JSONB.
        
        Args:
            metric_name: Name of the metric to query (e.g., 'revenue', 'arr', 'burn_rate')
            document_types: Filter by document types
            fund_id: Filter by fund ID (portfolio-aware)
            company_id: Filter by company ID (portfolio-aware)
            date_from: Start date for filtering
            date_to: End date for filtering
            limit: Maximum number of results
            
        Returns:
            List of documents with the metric value
        """
        repo = self._doc_repo()
        if not repo:
            logger.warning("Document metadata repo not available - returning empty results")
            return []
        
        try:
            filters: Dict[str, Any] = {"status": "completed"}
            if fund_id:
                filters["fund_id"] = fund_id
            if company_id:
                filters["company_id"] = company_id
            if document_types:
                filters["document_type"] = [dt.value for dt in document_types]
            
            docs = repo.list_(filters=filters, limit=limit * 2, offset=0)  # Over-fetch for date/metric filter
            
            # In-memory: date range and document_type (if list not supported by backend)
            if date_from or date_to:
                filtered = []
                for doc in docs:
                    processed_at = doc.get("processed_at")
                    if processed_at:
                        try:
                            dt_val = datetime.fromisoformat(processed_at.replace("Z", "+00:00"))
                            if date_from and dt_val < date_from:
                                continue
                            if date_to and dt_val > date_to:
                                continue
                        except Exception:
                            pass
                    filtered.append(doc)
                docs = filtered
            
            # Filter by document_type if backend didn't support in_ list
            if document_types and docs:
                doc_types_set = {dt.value for dt in document_types}
                docs = [d for d in docs if d.get("document_type") in doc_types_set]
            
            # Filter by metric presence in extracted_data
            results = []
            for doc in docs[:limit]:
                extracted_data = doc.get("extracted_data", {})
                if isinstance(extracted_data, str):
                    try:
                        extracted_data = json.loads(extracted_data)
                    except Exception:
                        continue
                
                metric_value = self._extract_nested_value(extracted_data, metric_name)
                if metric_value is not None:
                    doc = dict(doc)
                    doc["metric_value"] = metric_value
                    doc["metric_name"] = metric_name
                    results.append(doc)
            
            return results
            
        except Exception as e:
            logger.error("Error querying documents by metric %s: %s", metric_name, e)
            return []
    
    def query_by_metrics(
        self,
        metric_names: List[str],
        document_types: Optional[List[DocumentType]] = None,
        fund_id: Optional[str] = None,
        company_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        group_by_company: bool = True
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Query multiple metrics at once, optionally grouped by company.
        
        Returns:
            Dictionary mapping metric names to lists of documents
        """
        results = {}
        for metric_name in metric_names:
            docs = self.query_by_metric(
                metric_name=metric_name,
                document_types=document_types,
                fund_id=fund_id,
                company_id=company_id,
                date_from=date_from,
                date_to=date_to
            )
            results[metric_name] = docs
        
        if group_by_company:
            # Reorganize by company
            company_results = {}
            for metric_name, docs in results.items():
                for doc in docs:
                    company = self._extract_company_name(doc)
                    if company not in company_results:
                        company_results[company] = {}
                    if metric_name not in company_results[company]:
                        company_results[company][metric_name] = []
                    company_results[company][metric_name].append(doc)
            return company_results
        
        return results
    
    def query_portfolio_documents(
        self,
        fund_id: Optional[str] = None,
        company_ids: Optional[List[str]] = None,
        document_types: Optional[List[DocumentType]] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Query all documents for a portfolio (fund or specific companies).
        Portfolio-aware query that understands fund-company relationships.
        If fund_id is provided, uses CompanyDataRepo to get company_ids.
        """
        doc_repo = self._doc_repo()
        company_repo = self._company_repo_opt()
        if not doc_repo:
            return []
        
        try:
            if fund_id and not company_ids and company_repo:
                pcs = company_repo.get_portfolio_companies(fund_id, with_company_details=False)
                company_ids = [pc.get("company_id") for pc in pcs if pc.get("company_id")]
                if company_ids:
                    logger.info("Found %s companies for fund %s", len(company_ids), fund_id)
            
            filters: Dict[str, Any] = {"status": "completed"}
            if fund_id:
                filters["fund_id"] = fund_id
            if company_ids:
                filters["company_id"] = company_ids
            if document_types:
                filters["document_type"] = [dt.value for dt in document_types]
            
            docs = doc_repo.list_(filters=filters, limit=500, offset=0)
            
            if date_from or date_to:
                filtered = []
                for doc in docs:
                    processed_at = doc.get("processed_at")
                    if processed_at:
                        try:
                            dt_val = datetime.fromisoformat(processed_at.replace("Z", "+00:00"))
                            if date_from and dt_val < date_from:
                                continue
                            if date_to and dt_val > date_to:
                                continue
                        except Exception:
                            pass
                    filtered.append(doc)
                docs = filtered
            
            if company_ids and docs and company_repo:
                company_names = set()
                for cid in company_ids:
                    company = company_repo.get_company(cid)
                    if company and company.get("name"):
                        company_names.add(company["name"])
                if company_names:
                    filtered_docs = []
                    for doc in docs:
                        extracted_data = doc.get("extracted_data", {})
                        if isinstance(extracted_data, str):
                            try:
                                extracted_data = json.loads(extracted_data)
                            except Exception:
                                continue
                        doc_company = (
                            extracted_data.get("company") or
                            extracted_data.get("company_name") or
                            ""
                        )
                        if doc_company in company_names or doc.get("company_id") in company_ids:
                            filtered_docs.append(doc)
                    return filtered_docs
            
            return docs
            
        except Exception as e:
            logger.error("Error querying portfolio documents: %s", e)
            return []
    
    def query_time_series(
        self,
        metric_name: str,
        company_id: Optional[str] = None,
        fund_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        document_type: DocumentType = DocumentType.MONTHLY_UPDATE
    ) -> List[Dict[str, Any]]:
        """
        Query time series data for a metric (e.g., monthly revenue over time).
        Returns documents ordered by date with metric values.
        """
        docs = self.query_by_metric(
            metric_name=metric_name,
            document_types=[document_type],
            company_id=company_id,
            fund_id=fund_id,
            date_from=date_from,
            date_to=date_to
        )
        
        # Sort by processed_at or date from extracted_data
        def get_date(doc):
            processed_at = doc.get('processed_at')
            if processed_at:
                try:
                    return datetime.fromisoformat(processed_at.replace('Z', '+00:00'))
                except:
                    pass
            
            # Try to get date from extracted_data
            extracted_data = doc.get('extracted_data', {})
            if isinstance(extracted_data, str):
                try:
                    extracted_data = json.loads(extracted_data)
                except:
                    pass
            
            date_str = extracted_data.get('date') or extracted_data.get('period_date')
            if date_str:
                try:
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except:
                    pass
            
            return datetime.min
        
        docs.sort(key=get_date)
        return docs
    
    def _extract_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Extract value from nested dictionary using dot notation (e.g., 'key_metrics.revenue')"""
        keys = path.split('.')
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value
    
    def _extract_company_name(self, doc: Dict[str, Any]) -> str:
        """Extract company name from document"""
        extracted_data = doc.get('extracted_data', {})
        if isinstance(extracted_data, str):
            try:
                extracted_data = json.loads(extracted_data)
            except:
                pass
        
        if isinstance(extracted_data, dict):
            return (
                extracted_data.get('company') or
                extracted_data.get('company_name') or
                doc.get('company_id') or
                'Unknown'
            )
        return 'Unknown'
    
    async def extract_structured_data(
        self,
        document_id: str,
        extraction_type: str = "structured",
    ) -> Dict[str, Any]:
        """
        Extract structured data for a document. Used by cell action document.extract.
        Returns a dict with 'value' and optional 'summary'/'metadata' for the registry.
        If document is already completed, returns existing extracted_data; otherwise
        attempts to run document processing when storage path is available.
        """
        repo = self._doc_repo()
        if not repo:
            return {"value": None, "metadata": {"error": "Document service unavailable"}}

        doc = repo.get(document_id)
        if not doc:
            return {"value": None, "metadata": {"error": "Document not found"}}

        extracted = doc.get("extracted_data")
        if isinstance(extracted, str):
            try:
                extracted = json.loads(extracted)
            except Exception:
                extracted = {}
        if not isinstance(extracted, dict):
            extracted = {}

        if doc.get("status") == "completed":
            return {"value": extracted, "summary": "Extracted from completed document"}

        # Already being processed by another call (batch endpoint, Celery, etc.)
        # — poll until it finishes rather than returning empty data.
        if doc.get("status") == "processing":
            import asyncio
            max_polls = 60  # up to ~120 seconds
            for _ in range(max_polls):
                await asyncio.sleep(2)
                doc = repo.get(document_id)
                if not doc or doc.get("status") != "processing":
                    break
            if doc and doc.get("status") == "completed":
                extracted = doc.get("extracted_data") or {}
                if isinstance(extracted, str):
                    try:
                        extracted = json.loads(extracted)
                    except Exception:
                        extracted = {}
                return {"value": extracted, "summary": "Extracted from completed document"}
            # Still processing after timeout — return partial
            return {
                "value": extracted or None,
                "summary": "Document still processing after timeout",
                "metadata": {"status": doc.get("status") if doc else "unknown"},
            }

        # For pending documents: if extracted_data already exists (Celery beat us),
        # return it.  Otherwise fall through to process inline — the old early-return
        # left documents stuck in pending forever when Celery wasn't running.
        if doc.get("status") == "pending" and extracted:
            return {
                "value": extracted,
                "summary": "Extracted from pending document (data already available)",
                "metadata": {"status": "pending"},
            }

        storage_path = doc.get("file_path") or doc.get("storage_path")
        if storage_path:
            try:
                from app.core.adapters import get_storage, get_document_repo
                import asyncio

                storage = get_storage()
                doc_repo = get_document_repo()
                from app.services.document_process_service import run_document_process

                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: run_document_process(
                        document_id=document_id,
                        storage_path=storage_path,
                        document_type=doc.get("document_type") or "other",
                        storage=storage,
                        document_repo=doc_repo,
                        company_id=doc.get("company_id"),
                        fund_id=doc.get("fund_id"),
                    ),
                )
                if result.get("success") and result.get("result"):
                    data = result.get("result", {})
                    extracted = data.get("extracted_data", extracted)
                    # Mark document as completed if still pending
                    try:
                        repo = self._doc_repo()
                        if repo and doc.get("status") != "completed":
                            repo.update(document_id, {"status": "completed", "extracted_data": extracted})
                    except Exception as update_err:
                        logger.warning("Failed to update doc status to completed for %s: %s", document_id, update_err)
                    return {"value": extracted, "summary": "Extraction completed"}
                logger.warning("Document process returned failure for %s: %s", document_id, result.get("error", "unknown"))
                return {
                    "value": extracted or None,
                    "metadata": {"error": result.get("error", "Processing failed")},
                }
            except Exception as e:
                logger.warning("Document process run failed for %s: %s", document_id, e, exc_info=True)
                return {
                    "value": extracted or None,
                    "metadata": {"error": str(e)},
                }
        return {
            "value": extracted or None,
            "metadata": {"error": "Document not yet processed and no storage path"},
        }

    async def analyze_document(self, document_id: str) -> Dict[str, Any]:
        """
        Analyze a document. Used by cell action document.analyze.
        Returns a dict with 'value' and optional 'summary' for the registry.
        Tries document_processor._analyze_document when available; otherwise
        returns existing analysis from document metadata.
        """
        repo = self._doc_repo()
        if not repo:
            return {"value": None, "metadata": {"error": "Document service unavailable"}}

        doc = repo.get(document_id)
        if not doc:
            return {"value": None, "metadata": {"error": "Document not found"}}

        try:
            from app.services.document_service import document_processor

            doc_obj = await document_processor.get_document(document_id)
            if doc_obj:
                await document_processor._analyze_document(doc_obj)
                return {"value": True, "summary": "Analysis started"}
        except ImportError:
            pass
        except Exception as e:
            logger.debug("document_processor analyze not available: %s", e)

        value = {
            "issue_analysis": doc.get("issue_analysis"),
            "comparables_analysis": doc.get("comparables_analysis"),
            "processing_summary": doc.get("processing_summary"),
        }
        if any(v is not None for v in value.values()):
            return {"value": value, "summary": "Existing analysis"}
        return {"value": None, "metadata": {"reason": "No analysis available"}}

    def detect_query_type(self, query_text: str) -> MatrixQueryType:
        """
        Detect the type of matrix query from natural language.
        """
        query_lower = query_text.lower()
        
        # Financial metrics queries
        if any(term in query_lower for term in ['revenue', 'arr', 'burn rate', 'runway', 'margin', 'ltv', 'cac']):
            return MatrixQueryType.FINANCIAL_METRICS
        
        # Portfolio comparison
        if any(term in query_lower for term in ['compare', 'comparison', 'vs', 'versus', 'across portfolio']):
            return MatrixQueryType.PORTFOLIO_COMPARISON
        
        # Time series
        if any(term in query_lower for term in ['over time', 'trend', 'history', 'monthly', 'quarterly', 'growth']):
            return MatrixQueryType.TIME_SERIES
        
        # Company comparison
        if any(term in query_lower for term in ['compare companies', '@', 'company']):
            return MatrixQueryType.COMPANY_COMPARISON
        
        # Fund performance
        if any(term in query_lower for term in ['fund', 'portfolio performance', 'irr', 'multiple']):
            return MatrixQueryType.FUND_PERFORMANCE
        
        return MatrixQueryType.CUSTOM
