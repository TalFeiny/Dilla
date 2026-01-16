import pytest

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator


def test_format_billions_handles_none():
    assert UnifiedMCPOrchestrator._format_billions(None) == "N/A"


def test_format_billions_handles_zero():
    assert UnifiedMCPOrchestrator._format_billions(0) == "$0B"


@pytest.mark.parametrize(
    "value,expected",
    [
        (1_000_000_000, "$1.0B"),
        (2_500_000_000, "$2.5B"),
        (7_650_000_000, "$7.6B"),
    ],
)
def test_format_billions_formats_positive_values(value, expected):
    assert UnifiedMCPOrchestrator._format_billions(value) == expected





