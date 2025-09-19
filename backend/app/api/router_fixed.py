"""
Main API Router - Properly wired with all services
"""
from fastapi import APIRouter
from app.api.endpoints.unified_brain import router as unified_brain_router

# Import all existing routers
from app.api.endpoints import mcp
try:
    from app.api.endpoints.python_executor import router as python_router
    from app.api.endpoints.javascript_executor import router as javascript_router
except ImportError as e:
    print(f"Could not import executors: {e}")
    python_router = None
    javascript_router = None
try:
    from app.api.endpoints import (
        companies, portfolio, agents, advanced_analytics, rl, deck_builder, pwerm,
        scenarios, spreadsheet_formulas, valuation_engine, advanced_debt
    )
except ImportError as e:
    print(f"Import error: {e}")
    pass

api_router = APIRouter()

# Include unified brain endpoint (already has /agent prefix)
api_router.include_router(unified_brain_router, tags=["unified"])

# Include Python executor endpoint if available
if python_router:
    api_router.include_router(python_router, tags=["python"])

# Include JavaScript executor endpoint if available
if javascript_router:
    api_router.include_router(javascript_router, tags=["javascript"])

# Include existing endpoints if available
try:
    api_router.include_router(companies.router, prefix="/companies", tags=["companies"])
    api_router.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
    api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
    api_router.include_router(mcp.router, tags=["mcp"])  # MCP already has /mcp prefix
    api_router.include_router(advanced_analytics.router, prefix="/advanced-analytics", tags=["advanced-analytics"])
    api_router.include_router(rl.router, prefix="/rl", tags=["rl"])
    api_router.include_router(deck_builder.router, prefix="/deck-builder", tags=["deck"])
    api_router.include_router(pwerm.router, prefix="/pwerm", tags=["pwerm"])
    api_router.include_router(scenarios.router, prefix="/scenarios", tags=["scenarios"])
    api_router.include_router(spreadsheet_formulas.router, prefix="/spreadsheet-formulas", tags=["formulas"])
    api_router.include_router(valuation_engine.router, prefix="/valuation", tags=["valuation"])
    api_router.include_router(advanced_debt.router, prefix="/debt", tags=["debt"])
except:
    pass

# Health check
@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "dilla-ai-backend"}
