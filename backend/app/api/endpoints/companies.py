from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from app.core.database import supabase_service
from app.schemas.company import Company, CompanyMinimal
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=List[Company])
async def get_companies(
    limit: Optional[int] = Query(500, le=1000, description="Maximum number of companies to return"),
    offset: int = Query(0, ge=0, description="Number of companies to skip"),
    fields: Optional[str] = Query(None, description="Comma-separated list of fields to return or 'minimal'")
):
    """
    Get list of companies with optional filtering and field selection.
    """
    try:
        client = supabase_service.get_client()
        
        # Determine which fields to select
        select_string = "*"
        if fields == "minimal":
            select_string = "id,name,current_arr_usd,sector,current_valuation_usd,founded_year"
        elif fields:
            select_string = fields
        
        # Build query
        query = client.from_("companies").select(select_string).order("name")
        
        # Apply pagination
        query = query.range(offset, offset + limit - 1)
        
        response = query.execute()
        
        return response.data
    
    except Exception as e:
        logger.error(f"Error fetching companies: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch companies")


@router.get("/{company_id}", response_model=Company)
async def get_company(company_id: str):
    """
    Get a specific company by ID.
    """
    try:
        client = supabase_service.get_client()
        
        response = client.from_("companies").select("*").eq("id", company_id).single().execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Company not found")
        
        return response.data
    
    except Exception as e:
        logger.error(f"Error fetching company {company_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch company")


@router.post("/", response_model=Company)
async def create_company(company: Company):
    """
    Create a new company.
    """
    try:
        client = supabase_service.get_client()
        
        response = client.from_("companies").insert(company.dict()).execute()
        
        return response.data[0]
    
    except Exception as e:
        logger.error(f"Error creating company: {e}")
        raise HTTPException(status_code=500, detail="Failed to create company")


@router.patch("/{company_id}", response_model=Company)
async def update_company(company_id: str, company_update: dict):
    """
    Update a company.
    """
    try:
        client = supabase_service.get_client()
        
        response = client.from_("companies").update(company_update).eq("id", company_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Company not found")
        
        return response.data[0]
    
    except Exception as e:
        logger.error(f"Error updating company {company_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update company")


@router.get("/search", response_model=List[Company])
async def search_companies(
    q: Optional[str] = Query(None, description="Search query for company name or sector"),
    limit: Optional[int] = Query(100, le=1000, description="Maximum number of companies to return"),
    offset: int = Query(0, ge=0, description="Number of companies to skip")
):
    """
    Search companies by name or sector.
    """
    try:
        client = supabase_service.get_client()
        
        # Build query
        query = client.from_("companies").select("*").order("name")
        
        # Add search filter if provided
        if q:
            # Search in name and sector fields
            query = query.or_(f"name.ilike.%{q}%,sector.ilike.%{q}%")
        
        # Apply pagination
        query = query.range(offset, offset + limit - 1)
        
        response = query.execute()
        
        return response.data
    
    except Exception as e:
        logger.error(f"Error searching companies: {e}")
        raise HTTPException(status_code=500, detail="Failed to search companies")


@router.delete("/{company_id}")
async def delete_company(company_id: str):
    """
    Delete a company.
    """
    try:
        client = supabase_service.get_client()
        
        response = client.from_("companies").delete().eq("id", company_id).execute()
        
        return {"message": "Company deleted successfully"}
    
    except Exception as e:
        logger.error(f"Error deleting company {company_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete company")