"""Main API Router - robust loading of available endpoints."""

import importlib
import logging
from typing import Dict, Optional

from fastapi import APIRouter

from app.api.endpoints.unified_brain import router as unified_brain_router
from app.api.endpoints.deck_export import router as deck_export_router
from app.api.endpoints.cell_actions import router as cell_actions_router
from app.api.endpoints.matrix_charts import router as matrix_charts_router

logger = logging.getLogger(__name__)

# Track which optional routers loaded (for health/debug)
LOADED_OPTIONAL_ROUTERS: Dict[str, bool] = {}


def _include_optional_router(
    router: APIRouter,
    module_path: str,
    include_kwargs: Optional[Dict[str, object]] = None,
    router_key: Optional[str] = None,
) -> bool:
    """Import an optional router module if available and include it. Returns True if loaded."""
    include_kwargs = include_kwargs or {}
    key = router_key or module_path.split(".")[-1]
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError:
        logger.debug("Skipping router %s (module not found)", module_path)
        LOADED_OPTIONAL_ROUTERS[key] = False
        return False
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to import %s: %s", module_path, exc)
        LOADED_OPTIONAL_ROUTERS[key] = False
        return False

    route_obj = getattr(module, "router", None)
    if not isinstance(route_obj, APIRouter):
        logger.debug("Module %s has no FastAPI router", module_path)
        LOADED_OPTIONAL_ROUTERS[key] = False
        return False

    router.include_router(route_obj, **include_kwargs)
    LOADED_OPTIONAL_ROUTERS[key] = True
    return True


api_router = APIRouter()

# Always-on routers
api_router.include_router(unified_brain_router, tags=["unified"])
api_router.include_router(deck_export_router, tags=["export"])
api_router.include_router(cell_actions_router, tags=["cell-actions"])
api_router.include_router(matrix_charts_router, tags=["matrix-charts"])

# Optional routers that may rely on heavy service dependencies
# Use short key for health response (e.g. cell_actions, valuation)
OPTIONAL_ROUTERS = {
    "app.api.endpoints.email_inbound": {"tags": ["email"], "key": "email_inbound"},
    "app.api.endpoints.model_router_test": {"tags": ["test"], "key": "model_router_test"},
    # DISABLED — code execution endpoints not in use, re-enable with auth when needed
    # "app.api.endpoints.python_executor": {"tags": ["python"], "key": "python_executor"},
    # "app.api.endpoints.python_exec": {"prefix": "/python-scripts", "tags": ["python-scripts"], "key": "python_exec"},
    # "app.api.endpoints.javascript_executor": {"tags": ["javascript"], "key": "javascript_executor"},
    "app.api.endpoints.mcp": {"tags": ["mcp"], "key": "mcp"},
    "app.api.endpoints.companies": {"prefix": "/companies", "tags": ["companies"], "key": "companies"},
    "app.api.endpoints.portfolio": {"prefix": "/portfolio", "tags": ["portfolio"], "key": "portfolio"},
    "app.api.endpoints.agents": {"prefix": "/agents", "tags": ["agents"], "key": "agents"},
    "app.api.endpoints.advanced_analytics": {"prefix": "/advanced-analytics", "tags": ["advanced-analytics"], "key": "advanced_analytics"},
    "app.api.endpoints.rl": {"prefix": "/rl", "tags": ["rl"], "key": "rl"},
    "app.api.endpoints.deck_builder": {"prefix": "/deck-builder", "tags": ["deck"], "key": "deck_builder"},
    "app.api.endpoints.pwerm": {"prefix": "/pwerm", "tags": ["pwerm"], "key": "pwerm"},
    "app.api.endpoints.scenarios": {"prefix": "/scenarios", "tags": ["scenarios"], "key": "scenarios"},
    "app.api.endpoints.world_models": {"prefix": "/world-models", "tags": ["world-models"], "key": "world_models"},
    "app.api.endpoints.fund_modeling": {"prefix": "/fund-modeling", "tags": ["fund-modeling"], "key": "fund_modeling"},
    "app.api.endpoints.nl_scenarios": {"prefix": "/nl-scenarios", "tags": ["nl-scenarios"], "key": "nl_scenarios"},
    "app.api.endpoints.spreadsheet_formulas": {"prefix": "/spreadsheet-formulas", "tags": ["formulas"], "key": "spreadsheet_formulas"},
    "app.api.endpoints.valuation_engine": {"prefix": "/valuation", "tags": ["valuation"], "key": "valuation"},
    "app.api.endpoints.advanced_debt": {"prefix": "/debt", "tags": ["debt"], "key": "advanced_debt"},
    "app.api.endpoints.fpa_query": {"tags": ["fpa"], "key": "fpa_query"},
    "app.api.endpoints.documents_process": {"prefix": "/documents", "tags": ["documents"], "key": "documents_process"},
    "app.api.endpoints.portfolio_analysis": {"prefix": "/portfolio", "tags": ["portfolio-analysis"], "key": "portfolio_analysis"},
    "app.api.endpoints.compliance": {"prefix": "/compliance", "tags": ["compliance"], "key": "compliance"},
}

for module_path, kwargs in OPTIONAL_ROUTERS.items():
    key = kwargs.get("key")
    include_kwargs = {k: v for k, v in kwargs.items() if v is not None and k != "key"}
    _include_optional_router(api_router, module_path, include_kwargs, router_key=key)

logger.info("Optional routers loaded: %s", LOADED_OPTIONAL_ROUTERS)

# Health check: report which optional routers are loaded (e.g. cell_actions: true/false)
@api_router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "dilla-ai-backend",
    }
