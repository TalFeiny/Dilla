"""
Document metadata abstraction (processed_documents table / equivalent).
Implementations: Supabase, optional SQL over Snowflake/BigQuery/Redshift.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import logging

logger = logging.getLogger(__name__)


class DocumentMetadataRepo(ABC):
    """Interface for document metadata (processed_documents)."""

    @abstractmethod
    def get(self, id: str) -> Optional[Dict[str, Any]]:
        """Get a single document by id. Returns None if not found."""
        pass

    @abstractmethod
    def list_(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List documents with optional filters. filters: e.g. status, fund_id, company_id."""
        pass

    @abstractmethod
    def update(self, id: str, payload: Dict[str, Any]) -> None:
        """Update document by id. Partial update; only provided keys are set."""
        pass

    @abstractmethod
    def insert(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new document. Returns inserted row including id."""
        pass

    def claim_for_processing(self, id: str) -> bool:
        """Atomically transition status from 'pending' to 'processing'.

        Returns True if this caller won the claim (status was 'pending' and is
        now 'processing').  Returns False if the document was already claimed by
        another caller (status was 'processing' or 'completed').

        Default implementation uses get+update (not truly atomic).
        Subclasses should override with a DB-level atomic operation.
        """
        doc = self.get(id)
        if not doc or doc.get("status") != "pending":
            return False
        self.update(id, {"status": "processing"})
        return True


class SupabaseDocumentMetadataRepo(DocumentMetadataRepo):
    """Supabase implementation for processed_documents table."""

    def __init__(self, client):
        self._client = client
        self._table = "processed_documents"

    def get(self, id: str) -> Optional[Dict[str, Any]]:
        try:
            r = self._client.table(self._table).select("*").eq("id", id).single().execute()
            return r.data if r.data else None
        except Exception as e:
            logger.debug("get document %s: %s", id, e)
            return None

    def list_(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        try:
            q = self._client.table(self._table).select("*")
            if filters:
                for key, value in filters.items():
                    if value is None:
                        continue
                    if isinstance(value, (list, tuple)):
                        q = q.in_(key, value)
                    else:
                        q = q.eq(key, value)
            q = q.range(offset, offset + limit - 1)
            r = q.execute()
            return list(r.data or [])
        except Exception as e:
            logger.error("list documents: %s", e)
            return []

    def update(self, id: str, payload: Dict[str, Any]) -> None:
        self._client.table(self._table).update(payload).eq("id", id).execute()

    def insert(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = self._client.table(self._table).insert(payload).execute()
        if not r.data or len(r.data) == 0:
            raise ValueError("insert returned no data")
        return r.data[0]

    def claim_for_processing(self, id: str) -> bool:
        """Atomically claim a pending document for processing.

        Uses Supabase's UPDATE ... eq(status, pending) which translates to
        ``UPDATE ... WHERE id = $1 AND status = 'pending'``.
        If 0 rows are returned the document was already claimed.
        """
        try:
            r = (
                self._client.table(self._table)
                .update({"status": "processing"})
                .eq("id", id)
                .eq("status", "pending")
                .execute()
            )
            claimed = bool(r.data and len(r.data) > 0)
            if not claimed:
                logger.info("claim_for_processing(%s): already claimed or not pending", id)
            return claimed
        except Exception as e:
            logger.warning("claim_for_processing(%s) failed: %s", id, e)
            return False
