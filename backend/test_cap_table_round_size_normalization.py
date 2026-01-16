#!/usr/bin/env python3
"""
Tests for cap table normalization and investor ownership chart generation.
Ensures round_size/size fields map to amount and ownership summaries drive charts.
"""

import asyncio
import os
import sys
import types
from enum import Enum

# Provide dummy API keys so IntelligentGapFiller skips loading restricted .env
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("OPENAI_API_KEY", "test-key")

# Stub valuation engine module to avoid heavy dependencies during import
valuation_stub = types.ModuleType("valuation_engine_service_stub")


class _DummyStage(str, Enum):
    PRE_SEED = "pre_seed"
    SEED = "seed"
    SERIES_A = "series_a"
    SERIES_B = "series_b"
    SERIES_C = "series_c"


class _DummyValuationMethod(str, Enum):
    AUTO = "auto"


class _DummyValuationRequest:
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs


class _DummyValuationEngineService:
    def __init__(self, *args, **kwargs):
        pass


valuation_stub.Stage = _DummyStage
valuation_stub.ValuationMethod = _DummyValuationMethod
valuation_stub.ValuationRequest = _DummyValuationRequest
valuation_stub.ValuationEngineService = _DummyValuationEngineService

sys.modules.setdefault("app.services.valuation_engine_service", valuation_stub)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.pre_post_cap_table import PrePostCapTable
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator


def _round_size_company():
    """Generate company payload with round_size but no amount."""
    return {
        "company": "RoundSizeCo",
        "stage": "Series A",
        "geography": "US",
        "founders": [{"name": "Alice"}, {"name": "Bob"}],
        "funding_rounds": [
            {
                "round": "Series A",
                "round_size": "5,000,000",
                "pre_money_valuation": 20_000_000,
                "date": "2024-01-01",
                "investors": ["Alpha Ventures", "Beta Capital"],
                "lead_investor": "Alpha Ventures",
            }
        ],
    }


def test_round_size_normalization_into_cap_table_history():
    """round_size should normalize into amount for cap table calculations."""
    cap_table_service = PrePostCapTable()
    company = _round_size_company()

    result = cap_table_service.calculate_full_cap_table_history(company)

    assert result["num_rounds"] == 1, "Expected single processed funding round"
    history_entry = result["history"][0]
    assert (
        history_entry["investment_amount"] == 5_000_000
    ), "round_size should populate investment_amount"
    assert result["total_raised"] == 5_000_000, "Total raised should reflect normalized amount"

    ownership_summary = result.get("ownership_summary")
    assert ownership_summary, "Ownership summary should be present"
    assert ownership_summary["investors_total"] > 0, "Investor ownership should be captured"

    investor_names = [item["name"] for item in ownership_summary["investor_breakdown"]]
    assert (
        "Alpha Ventures (Lead)" in investor_names
    ), "Lead investor should appear in ownership summary"


def test_investor_pie_chart_generation_from_cap_table():
    """Investor ownership pie chart should be generated with normalized data."""
    company = _round_size_company()
    orchestrator = UnifiedMCPOrchestrator()
    orchestrator.shared_data["companies"] = [company]

    result = asyncio.run(orchestrator._execute_cap_table_generation({"context": {}}))

    cap_table = result["cap_tables"]["RoundSizeCo"]
    charts = cap_table.get("charts", {})
    pie_chart = charts.get("investor_ownership_pie")

    assert pie_chart, "Investor ownership pie chart should be present"
    assert pie_chart["type"] == "pie", "Chart type should be pie"

    labels = pie_chart["data"]["labels"]
    data_points = pie_chart["data"]["datasets"][0]["data"]

    assert "Founders" in labels, "Founders slice should be included"
    assert any("Alpha Ventures" in label for label in labels), "Lead investor slice expected"
    assert sum(data_points) > 99, "Ownership slices should approximately sum to 100%"

    # Ensure the funding rounds were normalized in place for downstream consumers
    normalized_round = company["funding_rounds"][0]
    assert normalized_round.get("amount") == 5_000_000, "Normalized amount should persist on company data"


if __name__ == "__main__":
    test_round_size_normalization_into_cap_table_history()
    asyncio.run(UnifiedMCPOrchestrator()._execute_cap_table_generation({"context": {}}))

