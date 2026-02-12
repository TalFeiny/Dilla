"""
Skills Package - Concrete Skill Implementations
Each skill uses specific MCP tools to accomplish focused tasks
"""

from .company_research_skill import CompanyResearchSkill
from .chart_generation_skill import ChartGenerationSkill

__all__ = [
    'CompanyResearchSkill',
    'ChartGenerationSkill',
]