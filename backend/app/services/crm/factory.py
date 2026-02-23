"""
CRM provider factory — returns the appropriate MCP-backed provider.

Reads CRM_PROVIDER env var ("attio" or "affinity") and returns an instance.
The caller must call set_tool_caller() on the returned provider before use.
"""
import os
import logging
from typing import Optional

from .base import CRMProvider
from .attio import AttioCRMProvider
from .affinity import AffinityCRMProvider

logger = logging.getLogger(__name__)

_PROVIDERS = {
    "attio": AttioCRMProvider,
    "affinity": AffinityCRMProvider,
}

_singleton: Optional[CRMProvider] = None


def get_crm_provider(provider_name: Optional[str] = None) -> CRMProvider:
    """Return a CRM provider singleton.

    Args:
        provider_name: "attio" or "affinity". If None, reads CRM_PROVIDER env var.
                       Defaults to "attio" when nothing is configured.
    """
    global _singleton
    if _singleton is not None:
        return _singleton

    name = (provider_name or os.getenv("CRM_PROVIDER", "attio")).lower().strip()
    cls = _PROVIDERS.get(name)
    if cls is None:
        logger.warning(f"[CRM Factory] Unknown provider '{name}', falling back to attio")
        cls = AttioCRMProvider

    _singleton = cls()
    logger.info(f"[CRM Factory] Initialized {cls.__name__}")
    return _singleton


def reset_crm_provider() -> None:
    """Clear the singleton (useful for tests)."""
    global _singleton
    _singleton = None
