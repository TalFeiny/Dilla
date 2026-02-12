"""
Matrix Query Orchestrator - Universal query system for matrix generation
Combines DocumentQueryService, search, citation manager, and LLM calls
to create portfolio-aware matrix outputs.
"""

import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from copy import deepcopy

logger = logging.getLogger(__name__)

from app.services.document_query_service import (
    DocumentQueryService,
    DocumentType,
    MatrixQueryType
)

try:
    from app.services.citation_manager import CitationManager
    CITATION_MANAGER_AVAILABLE = True
except ImportError:
    CITATION_MANAGER_AVAILABLE = False
    logger.warning("CitationManager not available")

try:
    from app.services.model_router import get_model_router, ModelCapability
    MODEL_ROUTER_AVAILABLE = True
except ImportError:
    MODEL_ROUTER_AVAILABLE = False
    logger.warning("ModelRouter not available")


class MatrixQueryOrchestrator:
    """
    Orchestrates matrix queries by:
    1. Detecting query type
    2. Querying extracted_data from documents (portfolio-aware)
    3. Combining with search results if needed
    4. Using citation manager for source tracking
    5. Using LLM to format results into matrix structure
    """
    
    def __init__(self):
        self.document_query_service = DocumentQueryService()
        self.citation_manager = CitationManager() if CITATION_MANAGER_AVAILABLE else None
        self.model_router = get_model_router() if MODEL_ROUTER_AVAILABLE else None
    
    async def process_matrix_query(
        self,
        query: str,
        fund_id: Optional[str] = None,
        company_ids: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a matrix query and return formatted matrix data.
        
        Args:
            query: Natural language query (e.g., "Compare revenue and ARR for portfolio companies")
            fund_id: Optional fund ID for portfolio filtering
            company_ids: Optional list of company IDs to filter
            context: Additional context (session_id, user_id, etc.)
            
        Returns:
            Dictionary with matrix structure: {columns, rows, formulas, metadata, citations}
        """
        logger.info(f"Processing matrix query: {query[:100]}")
        
        # Step 1: Detect query type
        query_type = self.document_query_service.detect_query_type(query)
        logger.info(f"Detected query type: {query_type.value}")
        
        # Step 2: Extract entities and metrics from query
        entities, metrics = await self._extract_query_entities(query, query_type)
        logger.info(f"Extracted entities: {entities}, metrics: {metrics}")
        
        # Step 3: Query documents based on query type
        document_data = await self._query_documents(
            query_type=query_type,
            metrics=metrics,
            entities=entities,
            fund_id=fund_id,
            company_ids=company_ids
        )
        
        # Step 4: Combine with search if needed (for missing data)
        search_data = await self._supplement_with_search(
            query=query,
            document_data=document_data,
            missing_metrics=metrics
        )
        
        # Step 5: Format into matrix structure using LLM
        matrix_data = await self._format_as_matrix(
            query=query,
            query_type=query_type,
            document_data=document_data,
            search_data=search_data,
            metrics=metrics,
            entities=entities
        )
        
        # Step 6: Add citations
        citations = self.citation_manager.get_all_citations() if self.citation_manager else []
        
        return {
            "columns": matrix_data.get("columns", []),
            "rows": matrix_data.get("rows", []),
            "formulas": matrix_data.get("formulas", {}),
            "metadata": {
                "query": query,
                "query_type": query_type.value,
                "lastUpdated": datetime.utcnow().isoformat(),
                "dataSource": "document_extracted_data",
                "confidence": matrix_data.get("confidence", 0.8),
                "fund_id": fund_id,
                "company_count": len(entities.get("companies", []))
            },
            "citations": citations
        }
    
    async def _extract_query_entities(
        self,
        query: str,
        query_type: MatrixQueryType
    ) -> Tuple[Dict[str, List[str]], List[str]]:
        """
        Extract entities (companies, funds) and metrics from query.
        Uses simple pattern matching, can be enhanced with LLM.
        """
        entities = {
            "companies": [],
            "funds": [],
            "dates": []
        }
        metrics = []
        
        # Extract @mentions (companies)
        import re
        company_mentions = re.findall(r'@(\w+)', query)
        entities["companies"] = company_mentions
        
        # Extract common metrics
        metric_keywords = {
            'revenue': 'revenue',
            'arr': 'arr',
            'burn rate': 'burn_rate',
            'runway': 'runway_months',
            'ltv': 'ltv',
            'cac': 'cac',
            'margin': 'gross_margin',
            'valuation': 'valuation',
            'growth': 'growth_rate',
            'employees': 'employees'
        }
        
        query_lower = query.lower()
        for keyword, metric in metric_keywords.items():
            if keyword in query_lower:
                metrics.append(metric)
        
        # If no metrics found, use defaults based on query type
        if not metrics:
            if query_type == MatrixQueryType.FINANCIAL_METRICS:
                metrics = ['revenue', 'arr', 'burn_rate', 'runway_months']
            elif query_type == MatrixQueryType.PORTFOLIO_COMPARISON:
                metrics = ['revenue', 'arr', 'valuation', 'growth_rate']
            elif query_type == MatrixQueryType.TIME_SERIES:
                metrics = ['revenue', 'arr']
        
        return entities, metrics
    
    async def _query_documents(
        self,
        query_type: MatrixQueryType,
        metrics: List[str],
        entities: Dict[str, List[str]],
        fund_id: Optional[str] = None,
        company_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Query documents based on query type and metrics.
        Portfolio-aware: filters by fund_id and company_ids.
        """
        document_data = {}
        
        # Determine document types based on query type
        if query_type == MatrixQueryType.TIME_SERIES:
            doc_types = [DocumentType.MONTHLY_UPDATE, DocumentType.BOARD_DECK]
        elif query_type == MatrixQueryType.FINANCIAL_METRICS:
            doc_types = [DocumentType.BOARD_DECK, DocumentType.MONTHLY_UPDATE, DocumentType.FINANCIAL_STATEMENT]
        else:
            doc_types = [DocumentType.BOARD_DECK, DocumentType.MONTHLY_UPDATE]
        
        # Use company_ids from entities if not provided
        if not company_ids and entities.get("companies"):
            # Map company names to IDs (simplified - in production, query companies table)
            company_ids = entities.get("companies")
        
        # Query each metric
        for metric in metrics:
            if query_type == MatrixQueryType.TIME_SERIES:
                # Query time series for first company or all companies
                company_id = company_ids[0] if company_ids else None
                docs = self.document_query_service.query_time_series(
                    metric_name=metric,
                    company_id=company_id,
                    fund_id=fund_id,
                    document_type=DocumentType.MONTHLY_UPDATE
                )
            else:
                docs = self.document_query_service.query_by_metric(
                    metric_name=metric,
                    document_types=doc_types,
                    fund_id=fund_id,
                    company_id=company_ids[0] if company_ids and len(company_ids) == 1 else None
                )
            
            document_data[metric] = docs
            
            # Add citations for document sources
            if self.citation_manager:
                for doc in docs:
                    company_name = self.document_query_service._extract_company_name(doc)
                    doc_type = doc.get('document_type', 'unknown')
                    processed_at = doc.get('processed_at', '')
                    
                    self.citation_manager.add_citation(
                        source=f"{doc_type} - {company_name}",
                        date=processed_at[:10] if processed_at else datetime.utcnow().isoformat()[:10],
                        content=f"Metric {metric} extracted from {doc_type}",
                        metadata={
                            "document_id": doc.get('id'),
                            "metric": metric,
                            "value": doc.get('metric_value')
                        }
                    )
        
        # If portfolio comparison, get all portfolio documents
        if query_type == MatrixQueryType.PORTFOLIO_COMPARISON and fund_id:
            portfolio_docs = self.document_query_service.query_portfolio_documents(
                fund_id=fund_id,
                company_ids=company_ids,
                document_types=doc_types
            )
            document_data['_portfolio_documents'] = portfolio_docs
        
        return document_data
    
    async def _supplement_with_search(
        self,
        query: str,
        document_data: Dict[str, Any],
        missing_metrics: List[str]
    ) -> Dict[str, Any]:
        """
        Supplement document data with search results if data is missing.
        This is where external search (Tavily, etc.) would be integrated.
        """
        # For now, return empty - can be enhanced with MCP tools
        return {}
    
    async def _format_as_matrix(
        self,
        query: str,
        query_type: MatrixQueryType,
        document_data: Dict[str, Any],
        search_data: Dict[str, Any],
        metrics: List[str],
        entities: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """
        Format document data into matrix structure using LLM.
        Creates columns, rows, and formulas based on query type.
        """
        # Build context for LLM
        context = {
            "query": query,
            "query_type": query_type.value,
            "metrics": metrics,
            "entities": entities,
            "document_data_summary": self._summarize_document_data(document_data)
        }
        
        # If LLM is available, use it to format
        if self.model_router:
            try:
                prompt = self._build_formatting_prompt(context)
                response = await self.model_router.generate(
                    prompt=prompt,
                    capability=ModelCapability.STRUCTURED,
                    temperature=0.3
                )
                
                # Parse LLM response into matrix structure
                matrix_data = self._parse_llm_matrix_response(response, document_data)
                return matrix_data
            except Exception as e:
                logger.error(f"Error formatting with LLM: {e}")
        
        # Fallback: Simple formatting without LLM
        return self._format_simple_matrix(document_data, metrics, entities, query_type)
    
    def _summarize_document_data(self, document_data: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize document data for LLM context"""
        summary = {}
        for metric, docs in document_data.items():
            if metric.startswith('_'):
                continue
            
            summary[metric] = {
                "count": len(docs),
                "companies": list(set(self.document_query_service._extract_company_name(d) for d in docs)),
                "latest_values": [
                    {
                        "company": self.document_query_service._extract_company_name(d),
                        "value": d.get('metric_value'),
                        "date": d.get('processed_at', '')[:10]
                    }
                    for d in docs[:5]  # Top 5
                ]
            }
        return summary
    
    def _build_formatting_prompt(self, context: Dict[str, Any]) -> str:
        """Build prompt for LLM to format matrix"""
        return f"""You are a financial data analyst. Format the following data into a matrix structure.

Query: {context['query']}
Query Type: {context['query_type']}
Metrics: {', '.join(context['metrics'])}

Document Data Summary:
{json.dumps(context['document_data_summary'], indent=2)}

Create a matrix with:
1. Columns: One column per metric, plus a company/entity column
2. Rows: One row per company/entity with metric values
3. Formulas: Any calculated columns (e.g., margins, ratios)
4. Ensure all values are properly typed (currency, percentage, number)

Return JSON in this format:
{{
    "columns": [
        {{"id": "company", "name": "Company", "type": "text"}},
        {{"id": "revenue", "name": "Revenue", "type": "currency"}},
        ...
    ],
    "rows": [
        {{"company": "Company A", "revenue": 1000000, ...}},
        ...
    ],
    "formulas": {{
        "margin": "=revenue-expenses"
    }},
    "confidence": 0.85
}}
"""
    
    def _parse_llm_matrix_response(
        self,
        response: str,
        document_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse LLM response and merge with actual document data"""
        import json
        try:
            # Try to extract JSON from response
            if isinstance(response, str):
                # Look for JSON block
                json_match = None
                if '{' in response:
                    start = response.find('{')
                    end = response.rfind('}') + 1
                    json_match = response[start:end]
                
                if json_match:
                    parsed = json.loads(json_match)
                else:
                    parsed = json.loads(response)
            else:
                parsed = response
            
            # Merge with actual document data to ensure accuracy
            return self._merge_llm_with_data(parsed, document_data)
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return self._format_simple_matrix(document_data, [], {}, MatrixQueryType.CUSTOM)
    
    def _merge_llm_with_data(
        self,
        llm_matrix: Dict[str, Any],
        document_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge LLM-formatted structure with actual document values"""
        # Use LLM structure but replace values with actual document data
        rows = []
        
        # Collect all companies from document data
        companies = set()
        for metric, docs in document_data.items():
            if metric.startswith('_'):
                continue
            for doc in docs:
                companies.add(self.document_query_service._extract_company_name(doc))
        
        # Build rows from document data
        for company in companies:
            row = {"company": company}
            for metric, docs in document_data.items():
                if metric.startswith('_'):
                    continue
                
                # Find latest value for this company
                company_docs = [d for d in docs if self.document_query_service._extract_company_name(d) == company]
                if company_docs:
                    # Get most recent
                    latest_doc = max(company_docs, key=lambda d: d.get('processed_at', ''))
                    row[metric] = latest_doc.get('metric_value')
                else:
                    row[metric] = None
            
            rows.append(row)
        
        # Use LLM columns if available, otherwise generate from metrics
        columns = llm_matrix.get('columns', [])
        if not columns:
            columns = [{"id": "company", "name": "Company", "type": "text"}]
            for metric in document_data.keys():
                if not metric.startswith('_'):
                    columns.append({
                        "id": metric,
                        "name": metric.replace('_', ' ').title(),
                        "type": self._infer_column_type(metric)
                    })
        
        return {
            "columns": columns,
            "rows": rows,
            "formulas": llm_matrix.get('formulas', {}),
            "confidence": llm_matrix.get('confidence', 0.8)
        }
    
    def _format_simple_matrix(
        self,
        document_data: Dict[str, Any],
        metrics: List[str],
        entities: Dict[str, List[str]],
        query_type: MatrixQueryType
    ) -> Dict[str, Any]:
        """Simple matrix formatting without LLM"""
        # Collect all companies
        companies = set()
        for metric, docs in document_data.items():
            if metric.startswith('_'):
                continue
            for doc in docs:
                companies.add(self.document_query_service._extract_company_name(doc))
        
        # Build columns
        columns = [{"id": "company", "name": "Company", "type": "text"}]
        for metric in metrics:
            columns.append({
                "id": metric,
                "name": metric.replace('_', ' ').title(),
                "type": self._infer_column_type(metric)
            })
        
        # Build rows
        rows = []
        for company in companies:
            row = {"company": company}
            for metric in metrics:
                docs = document_data.get(metric, [])
                company_docs = [d for d in docs if self.document_query_service._extract_company_name(d) == company]
                if company_docs:
                    latest_doc = max(company_docs, key=lambda d: d.get('processed_at', ''))
                    row[metric] = latest_doc.get('metric_value')
                else:
                    row[metric] = None
            rows.append(row)
        
        return {
            "columns": columns,
            "rows": rows,
            "formulas": {},
            "confidence": 0.7
        }
    
    def _infer_column_type(self, metric: str) -> str:
        """Infer column type from metric name"""
        metric_lower = metric.lower()
        if any(term in metric_lower for term in ['revenue', 'arr', 'valuation', 'amount', 'price', 'cost']):
            return 'currency'
        elif any(term in metric_lower for term in ['rate', 'ratio', 'margin', 'percentage', 'growth']):
            return 'percentage'
        elif any(term in metric_lower for term in ['months', 'count', 'employees', 'number']):
            return 'number'
        else:
            return 'number'
