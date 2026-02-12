"""
FPA Model Editor
CRUD operations for FPA models and versions
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from typing import Optional

from app.core.database import supabase_service

logger = logging.getLogger(__name__)


class FPAModelEditor:
    """Manages FPA models and versions"""
    
    def __init__(self):
        self.supabase = supabase_service
    
    async def create_model(
        self,
        name: str,
        model_type: str,
        model_definition: Dict[str, Any],
        formulas: Dict[str, str],
        assumptions: Dict[str, Any],
        created_by: str,
        fund_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new FPA model"""
        try:
            result = await self.supabase.table("fpa_models").insert({
                "name": name,
                "model_type": model_type,
                "model_definition": model_definition,
                "formulas": formulas,
                "assumptions": assumptions,
                "created_by": created_by,
                "fund_id": fund_id
            }).execute()
            
            return result.data[0] if result.data else {}
        except Exception as e:
            logger.error(f"Error creating model: {e}")
            raise
    
    async def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get a model by ID"""
        try:
            result = await self.supabase.table("fpa_models").select("*").eq("id", model_id).single().execute()
            return result.data if result.data else None
        except Exception as e:
            logger.error(f"Error getting model: {e}")
            return None
    
    async def update_formula(
        self,
        model_id: str,
        step_id: str,
        formula: str
    ) -> Dict[str, Any]:
        """Update a formula for a specific step"""
        try:
            # Get current model
            model = await self.get_model(model_id)
            if not model:
                raise ValueError(f"Model {model_id} not found")
            
            # Update formulas
            formulas = model.get("formulas", {})
            formulas[step_id] = formula
            
            # Update model
            result = await self.supabase.table("fpa_models").update({
                "formulas": formulas,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", model_id).execute()
            
            return result.data[0] if result.data else {}
        except Exception as e:
            logger.error(f"Error updating formula: {e}")
            raise
    
    async def update_assumptions(
        self,
        model_id: str,
        assumptions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update assumptions for a model"""
        try:
            result = await self.supabase.table("fpa_models").update({
                "assumptions": assumptions,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", model_id).execute()
            
            return result.data[0] if result.data else {}
        except Exception as e:
            logger.error(f"Error updating assumptions: {e}")
            raise
    
    async def create_version(
        self,
        model_id: str,
        model_definition: Dict[str, Any],
        changed_by: str,
        change_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new version of a model"""
        try:
            # Get current version number
            model = await self.get_model(model_id)
            if not model:
                raise ValueError(f"Model {model_id} not found")
            
            # Get latest version
            versions_result = await self.supabase.table("fpa_model_versions").select("version_number").eq("model_id", model_id).order("version_number", desc=True).limit(1).execute()
            
            next_version = 1
            if versions_result.data:
                next_version = versions_result.data[0].get("version_number", 0) + 1
            
            # Create version
            result = await self.supabase.table("fpa_model_versions").insert({
                "model_id": model_id,
                "version_number": next_version,
                "model_definition": model_definition,
                "changed_by": changed_by,
                "change_description": change_description
            }).execute()
            
            return result.data[0] if result.data else {}
        except Exception as e:
            logger.error(f"Error creating version: {e}")
            raise
