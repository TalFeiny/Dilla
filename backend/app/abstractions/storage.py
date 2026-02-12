"""
Blob storage abstraction for document files.
Implementations: Supabase storage, S3, GCS; client DW blob access via S3/GCS.
"""

from abc import ABC, abstractmethod
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DocumentBlobStorage(ABC):
    """Interface for document blob storage (download/upload)."""

    @abstractmethod
    def download(self, path: str) -> bytes:
        """Download file content at path. Raises if not found or error."""
        pass

    @abstractmethod
    def upload(self, path: str, content: bytes) -> None:
        """Upload content to path. Overwrites if exists."""
        pass

    def get_download_url(self, path: str) -> Optional[str]:
        """Optional: presigned or public URL for direct download."""
        return None


class SupabaseStorageProvider(DocumentBlobStorage):
    """Supabase Storage implementation. Bucket and optional prefix from config."""

    def __init__(self, client, bucket: str = "documents", prefix: str = ""):
        self._client = client
        self._bucket = bucket
        self._prefix = (prefix.rstrip("/") + "/") if prefix else ""

    def _full_path(self, path: str) -> str:
        path = path.lstrip("/")
        return f"{self._prefix}{path}" if self._prefix else path

    def download(self, path: str) -> bytes:
        full = self._full_path(path)
        try:
            data = self._client.storage.from_(self._bucket).download(full)
            if isinstance(data, bytes):
                return data
            # Supabase Python client may return bytearray or memoryview
            return bytes(data)
        except Exception as e:
            # Try basename-only path for backward compatibility (e.g. frontend sends full path)
            name = path.split("/")[-1] if "/" in path else path
            if name != full:
                try:
                    data = self._client.storage.from_(self._bucket).download(name)
                    return bytes(data) if data else b""
                except Exception:
                    pass
            logger.error(f"Supabase storage download failed for {path}: {e}")
            raise

    def upload(self, path: str, content: bytes) -> None:
        full = self._full_path(path)
        self._client.storage.from_(self._bucket).upload(full, content, upsert=True)

    def get_download_url(self, path: str) -> Optional[str]:
        try:
            full = self._full_path(path)
            return self._client.storage.from_(self._bucket).get_public_url(full)
        except Exception as e:
            logger.warning(f"get_download_url failed: {e}")
            return None
