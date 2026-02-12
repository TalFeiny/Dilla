"""
Pytest fixtures for document processing and extraction tests.
"""

import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest


# Known text for extraction tests
SAMPLE_EXTRACTION_TEXT = "Acme Corp. ARR $1.2M. Runway 18 months."


def _create_minimal_pdf(content: str) -> bytes:
    """Create a minimal PDF with the given text using reportlab."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from io import BytesIO

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.drawString(100, 750, content[:200])  # First 200 chars fit on one line
    c.save()
    return buffer.getvalue()


def _create_minimal_docx(content: str) -> bytes:
    """Create a minimal DOCX with the given text using python-docx."""
    from docx import Document as DocxDocument
    from io import BytesIO

    doc = DocxDocument()
    doc.add_paragraph(content)
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def mock_storage():
    """Storage that returns fixed content on download()."""

    def _make_storage(content: bytes, suffix: str = ".pdf"):
        storage = MagicMock()
        storage.download.return_value = content
        return storage

    return _make_storage


@pytest.fixture
def mock_document_repo():
    """In-memory document repo that records update() calls."""
    updates: list = []

    class MockRepo:
        def get(self, id: str) -> Dict[str, Any] | None:
            return None

        def list_(self, filters=None, limit=100, offset=0):
            return []

        def update(self, id: str, payload: Dict[str, Any]) -> None:
            updates.append((id, payload))

        def insert(self, payload: Dict[str, Any]) -> Dict[str, Any]:
            return {"id": "mock-1", **payload}

    repo = MockRepo()
    repo._updates = updates  # Expose for assertions
    return repo


@pytest.fixture
def sample_pdf_bytes():
    """Raw bytes of a minimal PDF with sample text."""
    return _create_minimal_pdf(SAMPLE_EXTRACTION_TEXT)


@pytest.fixture
def sample_pdf_path():
    """Create a temp PDF with known text, yield path, clean up after."""
    content = _create_minimal_pdf(SAMPLE_EXTRACTION_TEXT)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(content)
        path = f.name
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def sample_docx_path():
    """Create a temp DOCX with known text, yield path, clean up after."""
    content = _create_minimal_docx(SAMPLE_EXTRACTION_TEXT)
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        f.write(content)
        path = f.name
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def sample_extraction_json():
    """Sample extraction output with value_explanations for assertion."""
    return {
        "company_name": "Acme",
        "arr": 1_200_000,
        "revenue": 1_200_000,
        "value_explanations": {
            "arr": "Doc states $1.2M ARR",
            "runway_months": "Doc states 18 months runway",
        },
    }


@pytest.fixture
def sample_signal_extraction():
    """Sample monthly_update extraction with value_explanations."""
    return {
        "company_name": "Acme",
        "business_updates": {
            "product_updates": ["Launched new feature"],
            "achievements": [],
            "challenges": [],
            "risks": [],
            "key_milestones": [],
            "asks": [],
            "latest_update": "Q3 exceeded target",
            "defensive_language": [],
        },
        "operational_metrics": {
            "new_hires": [],
            "headcount": 45,
            "customer_count": None,
            "enterprise_customers": None,
            "smb_customers": None,
        },
        "extracted_entities": {"competitors_mentioned": [], "industry_terms": [], "partners_mentioned": []},
        "red_flags": [],
        "implications": [],
        "period_date": "2024-09-30",
        "financial_metrics": {
            "arr": 1_200_000,
            "revenue": 1_200_000,
            "mrr": None,
            "burn_rate": 50000,
            "runway_months": 18,
            "cash_balance": 900000,
            "gross_margin": 0.75,
            "growth_rate": 0.5,
        },
        "value_explanations": {
            "arr": "Q3 exceeded target; doc states $1.2M ARR",
            "runway_months": "Doc states 18 months runway",
        },
    }


@pytest.fixture
def sample_memo_extraction():
    """Sample investment_memo extraction."""
    return {
        "company_name": "Acme",
        "investment_date": "2024-06-01",
        "round": "Series A",
        "valuation_pre_money": 12_000_000,
        "market_size": {
            "tam_usd": 5_000_000_000,
            "sam_usd": 500_000_000,
            "som_usd": 50_000_000,
            "tam_description": "Enterprise software",
            "methodology": "Top-down",
        },
        "arr": 1_200_000,
        "runway_months": 18,
        "value_explanations": {"arr": "Memo states $1.2M ARR as of Q2"},
    }
