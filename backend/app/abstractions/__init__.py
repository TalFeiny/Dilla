"""
Backend-agnostic abstractions for storage, document metadata, and company/portfolio data.
Implementations can target Supabase, S3, GCS, Snowflake, BigQuery, etc.
"""

from app.abstractions.storage import (
    DocumentBlobStorage,
    SupabaseStorageProvider,
)
from app.abstractions.document_metadata import (
    DocumentMetadataRepo,
    SupabaseDocumentMetadataRepo,
)
from app.abstractions.company_data import (
    CompanyDataRepo,
    SupabaseCompanyDataRepo,
)

__all__ = [
    "DocumentBlobStorage",
    "SupabaseStorageProvider",
    "DocumentMetadataRepo",
    "SupabaseDocumentMetadataRepo",
    "CompanyDataRepo",
    "SupabaseCompanyDataRepo",
]
