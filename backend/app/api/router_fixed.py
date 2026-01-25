"""Main API Router - robust loading of available endpoints."""

import importlib
import logging
from typing import Dict, Optional

from fastapi import APIRouter

from app.api.endpoints.unified_brain import router as unified_brain_router
from app.api.endpoints.deck_export import router as deck_export_router

logger = logging.getLogger(__name__)


def _include_optional_router(
    router: APIRouter,
    module_path: str,
    include_kwargs: Optional[Dict[str, object]] = None,
) -> None:
    """Import an optional router module if available and include it."""
    include_kwargs = include_kwargs or {}
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError:
        logger.debug("Skipping router %s (module not found)", module_path)
        return
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to import %s: %s", module_path, exc)
        return

    route_obj = getattr(module, "router", None)
    if not isinstance(route_obj, APIRouter):
        logger.debug("Module %s has no FastAPI router", module_path)
        return

    router.include_router(route_obj, **include_kwargs)


api_router = APIRouter()

# Always-on routers
api_router.include_router(unified_brain_router, tags=["unified"])
api_router.include_router(deck_export_router, tags=["export"])

# Optional routers that may rely on heavy service dependencies
OPTIONAL_ROUTERS = {
    "app.api.endpoints.model_router_test": {"tags": ["test"]},  # Debug test endpoint
    "app.api.endpoints.python_executor": {"tags": ["python"]},
    "app.api.endpoints.python_exec": {"prefix": "/python-scripts", "tags": ["python-scripts"]},
    "app.api.endpoints.javascript_executor": {"tags": ["javascript"]},
    "app.api.endpoints.mcp": {"tags": ["mcp"]},  # Already includes /mcp prefix internally
    "app.api.endpoints.companies": {"prefix": "/companies", "tags": ["companies"]},
    "app.api.endpoints.portfolio": {"prefix": "/portfolio", "tags": ["portfolio"]},
    "app.api.endpoints.agents": {"prefix": "/agents", "tags": ["agents"]},
    "app.api.endpoints.advanced_analytics": {"prefix": "/advanced-analytics", "tags": ["advanced-analytics"]},
    "app.api.endpoints.rl": {"prefix": "/rl", "tags": ["rl"]},
    "app.api.endpoints.deck_builder": {"prefix": "/deck-builder", "tags": ["deck"]},
    "app.api.endpoints.pwerm": {"prefix": "/pwerm", "tags": ["pwerm"]},
    "app.api.endpoints.scenarios": {"prefix": "/scenarios", "tags": ["scenarios"]},
    "app.api.endpoints.world_models": {"prefix": "/world-models", "tags": ["world-models"]},
    "app.api.endpoints.stress_testing": {"prefix": "/stress-testing", "tags": ["stress-testing"]},
    "app.api.endpoints.fund_modeling": {"prefix": "/fund-modeling", "tags": ["fund-modeling"]},
    "app.api.endpoints.nl_scenarios": {"prefix": "/nl-scenarios", "tags": ["nl-scenarios"]},
    "app.api.endpoints.spreadsheet_formulas": {"prefix": "/spreadsheet-formulas", "tags": ["formulas"]},
    "app.api.endpoints.valuation_engine": {"prefix": "/valuation", "tags": ["valuation"]},
    "app.api.endpoints.advanced_debt": {"prefix": "/debt", "tags": ["debt"]},
    "app.api.endpoints.cell_actions": {"tags": ["cell-actions"]},  # Already includes /cell-actions prefix internally
    "app.api.endpoints.fpa_query": {"tags": ["fpa"]},  # Already includes /fpa prefix internally
}

for module_path, kwargs in OPTIONAL_ROUTERS.items():
    # Filter out None values so FastAPI defaults remain intact
    include_kwargs = {k: v for k, v in kwargs.items() if v is not None}
    _include_optional_router(api_router, module_path, include_kwargs)

# Health check
@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "dilla-ai-backend"}
