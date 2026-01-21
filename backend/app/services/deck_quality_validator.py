"""
Deck Quality Validator
Automated quality gates preventing substandard deck output
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import re

logger = logging.getLogger(__name__)


class QualityGateSeverity(Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass
class QualityGateResult:
    """Result of a quality gate check"""
    passed: bool
    severity: QualityGateSeverity
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class QualityGate:
    """A single quality gate"""
    name: str
    check: callable
    error_message: str
    severity: QualityGateSeverity = QualityGateSeverity.ERROR


class DeckQualityValidator:
    """
    Validates deck quality before finalization
    Implements McKinsey/Goldman Sachs standards
    """
    
    # Hardcoded default values that should not appear as actual data
    HARDCODED_DEFAULTS = {
        'revenue': [1_000_000, 500_000, 0],
        'arr': [1_000_000, 500_000, 0],
        'valuation': [0],
        'growth_rate': [0, 1.0],
    }
    
    # Realistic bounds for validation
    VALIDATION_BOUNDS = {
        'growth_rate': (0.10, 3.00),  # 10% - 300% for startups
        'ownership_percentage': (0.001, 0.50),  # 0.1% - 50%
        'revenue_multiple': (2.0, 50.0),  # 2x - 50x revenue multiple
        'gross_margin': (0.0, 1.0),  # 0% - 100%
    }
    
    def __init__(self):
        self.gates: List[QualityGate] = []
        self._register_gates()
    
    def _register_gates(self):
        """Register all quality gates"""
        self.gates = [
            QualityGate(
                name='Data Integrity',
                check=self._check_hardcoded_defaults,
                error_message='Hardcoded defaults detected in deck data',
                severity=QualityGateSeverity.ERROR
            ),
            QualityGate(
                name='Estimation Transparency',
                check=self._check_estimation_markers,
                error_message='Estimated values not properly marked',
                severity=QualityGateSeverity.ERROR
            ),
            QualityGate(
                name='Revenue/Valuation Consistency',
                check=self._check_revenue_valuation_consistency,
                error_message='Revenue and valuation are inconsistent',
                severity=QualityGateSeverity.WARNING
            ),
            QualityGate(
                name='Growth Rate Validation',
                check=self._check_growth_rate_bounds,
                error_message='Growth rates outside realistic bounds',
                severity=QualityGateSeverity.WARNING
            ),
            QualityGate(
                name='Markdown Artifacts',
                check=self._check_markdown_artifacts,
                error_message='Markdown syntax found in slide content',
                severity=QualityGateSeverity.ERROR
            ),
            QualityGate(
                name='Empty State Handling',
                check=self._check_empty_states,
                error_message='Unprofessional empty state text found',
                severity=QualityGateSeverity.WARNING
            ),
            QualityGate(
                name='Color Consistency',
                check=self._check_color_consistency,
                error_message='Non-monochrome colors detected',
                severity=QualityGateSeverity.WARNING
            ),
        ]
    
    def validate_deck(self, deck: Dict[str, Any]) -> Tuple[bool, List[QualityGateResult]]:
        """
        Validate entire deck against all quality gates
        
        Args:
            deck: Deck data structure
            
        Returns:
            Tuple of (all_passed, results_list)
        """
        results: List[QualityGateResult] = []
        
        for gate in self.gates:
            try:
                passed, details = gate.check(deck)
                results.append(QualityGateResult(
                    passed=passed,
                    severity=gate.severity,
                    message=gate.error_message if not passed else f"{gate.name} passed",
                    details=details
                ))
            except Exception as e:
                logger.error(f"Error in quality gate {gate.name}: {e}")
                results.append(QualityGateResult(
                    passed=False,
                    severity=QualityGateSeverity.ERROR,
                    message=f"Error checking {gate.name}: {str(e)}",
                    details={'error': str(e)}
                ))
        
        all_passed = all(r.passed for r in results if r.severity == QualityGateSeverity.ERROR)
        
        return all_passed, results
    
    def _check_hardcoded_defaults(self, deck: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Check for hardcoded default values"""
        issues = []
        
        def check_value(value: Any, field_name: str, path: str = ""):
            if isinstance(value, dict):
                for k, v in value.items():
                    check_value(v, field_name, f"{path}.{k}" if path else k)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    check_value(item, field_name, f"{path}[{i}]")
            elif isinstance(value, (int, float)):
                defaults = self.HARDCODED_DEFAULTS.get(field_name, [])
                if value in defaults and value != 0:  # Allow 0 as valid
                    issues.append({
                        'field': field_name,
                        'value': value,
                        'path': path,
                        'message': f"Hardcoded default {value} found at {path}"
                    })
        
        # Check slides for hardcoded values
        slides = deck.get('slides', [])
        for slide_idx, slide in enumerate(slides):
            content = slide.get('content', {})
            
            # Check metrics
            if 'metrics' in content:
                for metric_key, metric_value in content['metrics'].items():
                    if isinstance(metric_value, (int, float)):
                        check_value(metric_value, metric_key, f"slides[{slide_idx}].metrics.{metric_key}")
            
            # Check chart data
            if 'chart_data' in content:
                chart_data = content['chart_data']
                if isinstance(chart_data, dict):
                    # Check datasets
                    if 'datasets' in chart_data:
                        for ds_idx, dataset in enumerate(chart_data['datasets']):
                            if 'data' in dataset:
                                for data_idx, data_point in enumerate(dataset['data']):
                                    if isinstance(data_point, (int, float)):
                                        check_value(data_point, 'revenue', 
                                                   f"slides[{slide_idx}].chart_data.datasets[{ds_idx}].data[{data_idx}]")
        
        passed = len(issues) == 0
        return passed, {'issues': issues, 'count': len(issues)}
    
    def _check_estimation_markers(self, deck: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Check that estimated values are properly marked"""
        issues = []
        
        # Check for inferred/estimated values without markers
        slides = deck.get('slides', [])
        for slide_idx, slide in enumerate(slides):
            content = slide.get('content', {})
            
            # Check if content mentions estimated values without proper markers
            text_content = str(content.get('title', '')) + ' ' + str(content.get('subtitle', '')) + ' ' + str(content.get('body', ''))
            
            # Look for patterns that suggest estimation without markers
            if 'inferred' in text_content.lower() or 'estimated' in text_content.lower():
                # Check if properly marked
                if '(estimated)' not in text_content.lower() and '~' not in text_content:
                    issues.append({
                        'slide': slide_idx,
                        'message': 'Estimated value mentioned but not properly marked'
                    })
        
        passed = len(issues) == 0
        return passed, {'issues': issues, 'count': len(issues)}
    
    def _check_revenue_valuation_consistency(self, deck: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Check revenue vs valuation consistency"""
        issues = []
        
        # Extract revenue and valuation from deck
        company_data = deck.get('company_data', {})
        revenue = company_data.get('revenue') or company_data.get('arr') or company_data.get('inferred_revenue', 0)
        valuation = company_data.get('valuation') or company_data.get('last_valuation', 0)
        
        if revenue > 0 and valuation > 0:
            multiple = valuation / revenue
            min_multiple, max_multiple = self.VALIDATION_BOUNDS['revenue_multiple']
            
            if multiple < min_multiple or multiple > max_multiple:
                issues.append({
                    'revenue': revenue,
                    'valuation': valuation,
                    'multiple': multiple,
                    'message': f'Revenue multiple {multiple:.1f}x outside realistic bounds ({min_multiple}x - {max_multiple}x)'
                })
        
        passed = len(issues) == 0
        return passed, {'issues': issues, 'count': len(issues)}
    
    def _check_growth_rate_bounds(self, deck: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Check growth rates are within realistic bounds"""
        issues = []
        
        company_data = deck.get('company_data', {})
        growth_rate = company_data.get('growth_rate', 0)
        
        if growth_rate > 0:
            min_rate, max_rate = self.VALIDATION_BOUNDS['growth_rate']
            # Convert percentage to decimal if needed
            if growth_rate > 1:
                growth_rate = growth_rate / 100
            
            if growth_rate < min_rate or growth_rate > max_rate:
                issues.append({
                    'growth_rate': growth_rate,
                    'message': f'Growth rate {growth_rate:.1%} outside realistic bounds ({min_rate:.0%} - {max_rate:.0%})'
                })
        
        passed = len(issues) == 0
        return passed, {'issues': issues, 'count': len(issues)}
    
    def _check_markdown_artifacts(self, deck: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Check for markdown syntax in slide content"""
        issues = []
        markdown_patterns = [
            (r'\*\*.*?\*\*', 'Bold markdown (**text**)'),
            (r'\*[^*].*?\*', 'Italic markdown (*text*)'),
            (r'#{1,6}\s', 'Header markdown (# Header)'),
            (r'`.*?`', 'Inline code (`code`)'),
            (r'\[.*?\]\(.*?\)', 'Link markdown ([text](url))'),
        ]
        
        slides = deck.get('slides', [])
        for slide_idx, slide in enumerate(slides):
            content = slide.get('content', {})
            
            for field in ['title', 'subtitle', 'body']:
                text = content.get(field, '')
                if text:
                    for pattern, description in markdown_patterns:
                        if re.search(pattern, text):
                            issues.append({
                                'slide': slide_idx,
                                'field': field,
                                'pattern': description,
                                'message': f'Markdown artifact found in {field}'
                            })
                            break  # Only report once per field
        
        passed = len(issues) == 0
        return passed, {'issues': issues, 'count': len(issues)}
    
    def _check_empty_states(self, deck: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Check for unprofessional empty state text"""
        issues = []
        unprofessional_terms = ['unknown', 'n/a', 'na', 'none', 'null']
        
        slides = deck.get('slides', [])
        for slide_idx, slide in enumerate(slides):
            content = slide.get('content', {})
            
            # Check text fields
            for field in ['title', 'subtitle', 'body']:
                text = str(content.get(field, '')).lower()
                for term in unprofessional_terms:
                    if term in text:
                        issues.append({
                            'slide': slide_idx,
                            'field': field,
                            'term': term,
                            'message': f'Unprofessional term "{term}" found in {field}'
                        })
            
            # Check metrics
            if 'metrics' in content:
                for metric_key, metric_value in content['metrics'].items():
                    if isinstance(metric_value, str):
                        metric_lower = metric_value.lower()
                        for term in unprofessional_terms:
                            if term in metric_lower:
                                issues.append({
                                    'slide': slide_idx,
                                    'field': f'metrics.{metric_key}',
                                    'term': term,
                                    'message': f'Unprofessional term "{term}" in metric {metric_key}'
                                })
        
        passed = len(issues) == 0
        return passed, {'issues': issues, 'count': len(issues)}
    
    def _check_color_consistency(self, deck: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Check for non-monochrome colors"""
        issues = []
        non_monochrome_colors = [
            '#10b981', '#10B981',  # Green
            '#8b5cf6', '#8B5CF6', '#7c3aed', '#7C3AED',  # Purple
            '#f59e0b', '#F59E0B',  # Orange
            '#ef4444', '#EF4444',  # Red
            '#3b82f6', '#3B82F6',  # Blue (if not from design tokens)
        ]
        
        # This is a simplified check - in practice, would need to parse CSS/styles
        # For now, check if color strings appear in slide content
        slides = deck.get('slides', [])
        for slide_idx, slide in enumerate(slides):
            content = slide.get('content', {})
            content_str = str(content).lower()
            
            for color in non_monochrome_colors:
                if color.lower() in content_str:
                    issues.append({
                        'slide': slide_idx,
                        'color': color,
                        'message': f'Non-monochrome color {color} detected'
                    })
        
        passed = len(issues) == 0
        return passed, {'issues': issues, 'count': len(issues)}


# Create singleton instance
validator = DeckQualityValidator()

