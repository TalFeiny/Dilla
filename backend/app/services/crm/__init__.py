"""
CRM Integration Scaffolding — Attio & Affinity

Abstract CRM provider with concrete implementations for Attio and Affinity.
Used by the orchestrator to sync company data, notes, and deal flow.
"""
from .base import CRMProvider, CRMCompany, CRMNote, CRMDeal, CRMSyncResult
from .attio import AttioCRMProvider
from .affinity import AffinityCRMProvider
from .factory import get_crm_provider

__all__ = [
    "CRMProvider",
    "CRMCompany",
    "CRMNote",
    "CRMDeal",
    "CRMSyncResult",
    "AttioCRMProvider",
    "AffinityCRMProvider",
    "get_crm_provider",
]
