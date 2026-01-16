import sys
import types
from pathlib import Path

import pytest
from unittest.mock import patch

# Ensure backend package is importable when tests run from repo root
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Provide lightweight stubs for external libraries that require system resources
fake_yfinance = types.ModuleType("yfinance")


class _FakeTicker:
    def __init__(self, *args, **kwargs):
        self.info = {}

    def history(self, *args, **kwargs):
        return None


fake_yfinance.Ticker = _FakeTicker
sys.modules.setdefault("yfinance", fake_yfinance)

fake_requests = types.ModuleType("requests")
fake_requests.get = lambda *args, **kwargs: None  # type: ignore
fake_requests.Session = object  # type: ignore
sys.modules.setdefault("requests", fake_requests)

with patch("dotenv.load_dotenv", return_value=True):
    from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator


def _build_company_stub(name: str) -> dict:
    """Create a minimal company payload accepted by the orchestrator."""
    return {
        "company": name,
        "market_size": {},
        "competitive_landscape": {},
        "pwerm_scenarios": [],
        "business_model": "saas",
        "stage": "Seed"
    }


@pytest.mark.asyncio
async def test_comparison_llm_recovers_from_trailing_prose(monkeypatch):
    orchestrator = UnifiedMCPOrchestrator()

    async def fake_completion(*args, **kwargs):
        return {
            "response": (
                '{"winner": "company_b", "overall_reasoning": "b beats a", "dimension_analysis": {}}'
                "\n\nAdditional commentary outside JSON."
            ),
            "model": "claude-sonnet-4-5",
            "cost": 0.01,
        }

    monkeypatch.setattr(orchestrator.model_router, "get_completion", fake_completion)

    company_a = _build_company_stub("Company A")
    company_b = _build_company_stub("Company B")

    result = await orchestrator._call_consolidated_comparison_llm(company_a, company_b)

    assert result is not None
    assert result["winner"] == "company_b"


@pytest.mark.asyncio
async def test_comparison_llm_parses_leading_instruction_block(monkeypatch):
    orchestrator = UnifiedMCPOrchestrator()

    async def fake_completion(*args, **kwargs):
        return {
            "response": (
                "Return a JSON object with the requested schema:\n"
                '{"winner": "company_a", "overall_reasoning": "a beats b", "dimension_analysis": {}}'
            ),
            "model": "claude-sonnet-4-5",
            "cost": 0.01,
        }

    monkeypatch.setattr(orchestrator.model_router, "get_completion", fake_completion)

    company_a = _build_company_stub("Company A")
    company_b = _build_company_stub("Company B")

    result = await orchestrator._call_consolidated_comparison_llm(company_a, company_b)

    assert result is not None
    assert result["winner"] == "company_a"


def test_growth_inference_populates_missing_metrics():
    orchestrator = UnifiedMCPOrchestrator()
    company = _build_company_stub("GrowthCo")
    company.update(
        {
            "category": "AI-first SaaS",
            "valuation": 120_000_000,
            "inferred_valuation": 120_000_000,
            "inferred_revenue": 6_000_000,
            "net_retention": 1.12,
            "profit_margin": -0.15,
        }
    )

    metrics = orchestrator._ensure_growth_metrics(company)

    assert metrics
    status = company.get("growth_inference_status", {})
    assert status.get("success") is True
    assert company.get("projected_growth_rate") and company["projected_growth_rate"] > 1
    assert company.get("growth_rate") and company["growth_rate"] > 1


def test_growth_inference_uses_stage_defaults_when_revenue_missing():
    orchestrator = UnifiedMCPOrchestrator()
    company = _build_company_stub("DefaultCo")
    company.update(
        {
            "stage": "Series B",
            "valuation": 400_000_000,
            "net_retention": None,
        }
    )
    # Explicitly remove revenue hints
    company.pop("revenue", None)
    company.pop("inferred_revenue", None)
    company.pop("arr", None)

    metrics = orchestrator._ensure_growth_metrics(company)

    assert metrics
    status = company.get("growth_inference_status", {})
    assert status.get("success") is True
    revenue_meta = status.get("inputs", {}).get("revenue", {})
    assert revenue_meta.get("source") == "default"
    assert company.get("projected_growth_rate") and company["projected_growth_rate"] > 1

