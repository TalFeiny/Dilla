"""
Resolve backend-agnostic adapters from config.
Default: Supabase for storage, document metadata, and company data.

Lazy initialization with retry: if Supabase is unavailable at first call,
adapters return None and will re-attempt on subsequent calls once the
SupabaseService retry interval has elapsed.
"""

from typing import Optional

from app.core.config import settings
from app.abstractions.storage import DocumentBlobStorage, SupabaseStorageProvider
from app.abstractions.document_metadata import DocumentMetadataRepo, SupabaseDocumentMetadataRepo
from app.abstractions.company_data import CompanyDataRepo, SupabaseCompanyDataRepo
from app.core.database import get_supabase_service
import logging

logger = logging.getLogger(__name__)

_storage: Optional[DocumentBlobStorage] = None
_document_repo: Optional[DocumentMetadataRepo] = None
_company_repo: Optional[CompanyDataRepo] = None


def _get_client():
    """Get the Supabase client, returning None if unavailable (will retry later)."""
    client = get_supabase_service().get_client()
    if not client:
        logger.warning("Supabase client not available yet — features will be limited until connection is established")
    return client


def get_storage() -> Optional[DocumentBlobStorage]:
    """Return configured blob storage (default: Supabase). Returns None if unavailable."""
    global _storage
    if _storage is not None:
        return _storage
    provider = (settings.STORAGE_PROVIDER or "supabase").lower()
    if provider == "supabase":
        client = _get_client()
        if not client:
            return None
        _storage = SupabaseStorageProvider(
            client,
            bucket=getattr(settings, "STORAGE_BUCKET", "documents") or "documents",
            prefix=getattr(settings, "STORAGE_PREFIX", "") or "",
        )
        logger.info("Storage adapter: Supabase (bucket=%s)", _storage._bucket)
    else:
        raise ValueError(f"Unknown STORAGE_PROVIDER: {provider}. Supported: supabase (s3/gcs later).")
    return _storage


def get_document_repo() -> Optional[DocumentMetadataRepo]:
    """Return configured document metadata repo (default: Supabase). Returns None if unavailable."""
    global _document_repo
    if _document_repo is not None:
        return _document_repo
    backend = (settings.DATA_BACKEND or "supabase").lower()
    if backend == "supabase":
        client = _get_client()
        if not client:
            return None
        _document_repo = SupabaseDocumentMetadataRepo(client)
        logger.info("Document metadata adapter: Supabase")
    else:
        raise ValueError(f"Unknown DATA_BACKEND: {backend}. Supported: supabase.")
    return _document_repo


def get_company_repo() -> Optional[CompanyDataRepo]:
    """Return configured company/portfolio data repo (default: Supabase). Returns None if unavailable."""
    global _company_repo
    if _company_repo is not None:
        return _company_repo
    backend = getattr(settings, "COMPANY_DATA_BACKEND", None) or settings.DATA_BACKEND or "supabase"
    backend = str(backend).lower()
    if backend == "supabase":
        client = _get_client()
        if not client:
            return None
        _company_repo = SupabaseCompanyDataRepo(client)
        logger.info("Company data adapter: Supabase")
    else:
        raise ValueError(f"Unknown COMPANY_DATA_BACKEND: {backend}. Supported: supabase.")
    return _company_repo


def reset_adapters() -> None:
    """Reset cached adapters (e.g. for tests or config change)."""
    global _storage, _document_repo, _company_repo
    _storage = None
    _document_repo = None
    _company_repo = None
