"""
Cell Action Registry Service

Centralized registry for all cell actions (formulas, workflows, document actions).
Handles different output formats from various services and transforms them appropriately
for matrix cell display.

Services register their available actions on startup, and the registry provides
mode-aware filtering and execution routing.
"""

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ActionCategory(Enum):
    """Action categories"""
    FORMULA = "formula"
    WORKFLOW = "workflow"
    DOCUMENT = "document"


class ExecutionType(Enum):
    """Execution types"""
    FORMULA = "formula"
    WORKFLOW = "workflow"
    DOCUMENT = "document"


class OutputType(Enum):
    """Output format types - matches different service return formats"""
    NUMBER = "number"  # Single numeric value (IRR, NPV, valuation fair_value)
    STRING = "string"  # Text result (explanation, method name)
    ARRAY = "array"  # Array of values (cash flows, comparables list)
    TIME_SERIES = "time_series"  # Time series data (NAV over time, revenue projections)
    CHART = "chart"  # Chart configuration (ChartConfig object)
    OBJECT = "object"  # Complex object (ValuationResult, fund metrics, follow-on strategy)
    BOOLEAN = "boolean"  # Boolean result
    MULTI_COLUMN = "multi_column"  # Creates new columns + optional chart (e.g. PWERM 2027/2028 revenue)


@dataclass
class ActionDefinition:
    """Definition of a cell action"""
    action_id: str  # e.g., 'valuation_engine.pwerm', 'revenue_projection.build'
    name: str
    description: Optional[str] = None
    category: ActionCategory = ActionCategory.WORKFLOW
    service_name: str = ""  # e.g., 'valuation_engine', 'revenue_projection_service'
    service_type: str = "service"  # 'service', 'crud', 'agentic'
    api_endpoint: Optional[str] = None
    execution_type: ExecutionType = ExecutionType.WORKFLOW
    required_inputs: Dict[str, Any] = field(default_factory=dict)  # Schema for inputs
    output_type: OutputType = OutputType.NUMBER
    output_transform: Optional[str] = None  # How to extract cell value from output
    mode_availability: List[str] = field(default_factory=lambda: ['portfolio', 'query', 'custom', 'lp'])
    column_compatibility: List[str] = field(default_factory=lambda: ['number', 'currency'])
    config: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True


class CellActionRegistry:
    """
    Centralized registry for cell actions.
    
    Services register their actions, and the registry provides:
    - Mode-aware filtering
    - Output format transformation
    - Execution routing
    """
    
    def __init__(self):
        self._actions: Dict[str, ActionDefinition] = {}
        self._initialized = False
    
    def register_action(self, action: ActionDefinition) -> None:
        """Register a cell action"""
        if action.action_id in self._actions:
            logger.warning(f"Action {action.action_id} already registered, updating...")
        
        self._actions[action.action_id] = action
        logger.info(f"Registered action: {action.action_id} ({action.category.value})")
    
    def register_formula(
        self,
        action_id: str,
        name: str,
        service_name: str,
        required_inputs: Dict[str, Any],
        output_type: OutputType = OutputType.NUMBER,
        description: Optional[str] = None,
        mode_availability: Optional[List[str]] = None,
        column_compatibility: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """Convenience method to register a formula"""
        action = ActionDefinition(
            action_id=action_id,
            name=name,
            description=description,
            category=ActionCategory.FORMULA,
            service_name=service_name,
            execution_type=ExecutionType.FORMULA,
            required_inputs=required_inputs,
            output_type=output_type,
            mode_availability=mode_availability or ['portfolio', 'query', 'custom', 'lp'],
            column_compatibility=column_compatibility or ['number'],
            config=config or {}
        )
        self.register_action(action)
    
    def register_workflow(
        self,
        action_id: str,
        name: str,
        service_name: str,
        api_endpoint: Optional[str] = None,
        required_inputs: Optional[Dict[str, Any]] = None,
        output_type: OutputType = OutputType.OBJECT,
        output_transform: Optional[str] = None,
        description: Optional[str] = None,
        mode_availability: Optional[List[str]] = None,
        column_compatibility: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """Convenience method to register a workflow"""
        action = ActionDefinition(
            action_id=action_id,
            name=name,
            description=description,
            category=ActionCategory.WORKFLOW,
            service_name=service_name,
            api_endpoint=api_endpoint,
            execution_type=ExecutionType.WORKFLOW,
            required_inputs=required_inputs or {},
            output_type=output_type,
            output_transform=output_transform,
            mode_availability=mode_availability or ['portfolio', 'query', 'custom', 'lp'],
            column_compatibility=column_compatibility or ['number', 'currency'],
            config=config or {}
        )
        self.register_action(action)
    
    def get_action(self, action_id: str) -> Optional[ActionDefinition]:
        """Get action by ID"""
        return self._actions.get(action_id)
    
    def get_available_actions(
        self,
        mode: str,
        category: Optional[str] = None,
        column_id: Optional[str] = None,
        column_type: Optional[str] = None
    ) -> List[ActionDefinition]:
        """
        Get available actions filtered by mode, category, and column compatibility
        
        Args:
            mode: Matrix mode ('portfolio', 'query', 'custom', 'lp')
            category: Optional category filter ('formula', 'workflow', 'document')
            column_id: Optional column ID for compatibility check
            column_type: Optional column type for compatibility check
        """
        actions = []
        
        for action in self._actions.values():
            if not action.is_active:
                continue
            
            # Filter by mode
            if mode not in action.mode_availability:
                continue
            
            # Filter by category
            if category and action.category.value != category:
                continue
            
            # Filter by column compatibility
            if column_type and action.column_compatibility:
                if column_type not in action.column_compatibility:
                    continue
            
            actions.append(action)
        
        return sorted(actions, key=lambda a: a.name)
    
    def transform_output(
        self,
        action_id: str,
        service_output: Any
    ) -> Dict[str, Any]:
        """
        Transform service output to cell-appropriate format.
        
        Different services return different formats:
        - ValuationResult: Extract fair_value, method_used, explanation
        - RevenueProjectionService: Extract final value or time series
        - ChartIntelligence: Return chart config
        - NAV: Return number or time series
        - Fund metrics: Extract key metrics
        - Follow-on strategy: Extract strategy recommendation
        
        Returns:
            {
                'value': <cell value>,
                'displayValue': <formatted display>,
                'metadata': {
                    'method': <method used>,
                    'explanation': <explanation>,
                    'raw_output': <original output>,
                    'output_type': <output type>
                }
            }
        """
        action = self.get_action(action_id)
        if not action:
            logger.warning(f"Action {action_id} not found, returning raw output")
            result = {
                'value': service_output,
                'displayValue': str(service_output),
                'metadata': {'raw_output': service_output}
            }
            if isinstance(service_output, dict) and service_output.get('citations'):
                result.setdefault('metadata', {})['citations'] = service_output['citations']
            return result
        elif action_id == "document.extract":
            result = self._transform_document_extract_output(service_output)
        else:
            # Handle different output types
            if action.output_type == OutputType.NUMBER:
                result = self._transform_number_output(action, service_output)
            elif action.output_type == OutputType.OBJECT:
                result = self._transform_object_output(action, service_output)
            elif action.output_type == OutputType.TIME_SERIES:
                result = self._transform_time_series_output(action, service_output)
            elif action.output_type == OutputType.CHART:
                result = self._transform_chart_output(action, service_output)
            elif action.output_type == OutputType.STRING:
                result = self._transform_string_output(action, service_output)
            elif action.output_type == OutputType.ARRAY:
                result = self._transform_array_output(action, service_output)
            elif action.output_type == OutputType.MULTI_COLUMN:
                result = self._transform_multi_column_output(action, service_output)
            else:
                result = {
                    'value': service_output,
                    'displayValue': str(service_output),
                    'metadata': {'raw_output': service_output, 'output_type': action.output_type.value}
                }

        # Passthrough citations from service output (e.g. market/search-backed actions)
        if isinstance(service_output, dict) and service_output.get('citations'):
            result.setdefault('metadata', {})['citations'] = service_output['citations']
        return result
    
    def _transform_number_output(
        self,
        action: ActionDefinition,
        output: Any
    ) -> Dict[str, Any]:
        """Transform numeric output"""
        if isinstance(output, (int, float)):
            value = float(output)
        elif isinstance(output, dict):
            # Try to extract numeric value from dict
            value = output.get('value') or output.get('result') or output.get('fair_value') or 0
            value = float(value) if value is not None else 0
        else:
            value = float(output) if output else 0
        
        return {
            'value': value,
            'displayValue': f"{value:,.2f}" if value else "0",
            'metadata': {
                'raw_output': output,
                'output_type': 'number'
            }
        }
    
    def _transform_object_output(
        self,
        action: ActionDefinition,
        output: Any
    ) -> Dict[str, Any]:
        """Transform object output (ValuationResult, fund metrics, etc.)"""
        # Handle ValuationResult dataclass objects
        if hasattr(output, 'fair_value'):
            # It's a ValuationResult object
            method = output.method_used
            explanation = output.explanation
            confidence = output.confidence
            raw_output = {
                'fair_value': output.fair_value,
                'method_used': output.method_used,
                'explanation': output.explanation,
                'confidence': output.confidence,
                'common_stock_value': output.common_stock_value,
                'preferred_value': output.preferred_value
            }
            # Use output_transform if specified, otherwise use fair_value
            if action.output_transform:
                value = self._extract_nested_value(raw_output, action.output_transform)
            else:
                value = output.fair_value
        elif not isinstance(output, dict):
            # Convert to dict if it's an object
            raw_output = output.__dict__ if hasattr(output, '__dict__') else {'value': output}
            # Use output_transform if specified
            if action.output_transform:
                value = self._extract_nested_value(raw_output, action.output_transform)
            else:
                value = self._extract_default_value(action, raw_output)
            method = raw_output.get('method_used') or raw_output.get('method') or action.name
            explanation = raw_output.get('explanation') or raw_output.get('description') or ""
            confidence = raw_output.get('confidence')
        else:
            raw_output = output
            # Use output_transform if specified
            if action.output_transform:
                value = self._extract_nested_value(raw_output, action.output_transform)
            else:
                value = self._extract_default_value(action, raw_output)
            method = raw_output.get('method_used') or raw_output.get('method') or action.name
            explanation = raw_output.get('explanation') or raw_output.get('description') or ""
            confidence = raw_output.get('confidence')
        
        # Format display value
        if isinstance(value, (int, float)):
            display_value = f"{value:,.2f}"
        elif isinstance(value, str):
            display_value = value
        else:
            display_value = str(value)
        
        return {
            'value': value,
            'displayValue': display_value,
            'metadata': {
                'method': method,
                'explanation': explanation,
                'confidence': confidence,
                'raw_output': raw_output,
                'output_type': 'object'
            }
        }
    
    def _transform_time_series_output(
        self,
        action: ActionDefinition,
        output: Any
    ) -> Dict[str, Any]:
        """Transform time series output (revenue projections, NAV over time)"""
        if isinstance(output, list):
            # List of dicts: [{year: 1, revenue: X}, ...]
            if len(output) > 0 and isinstance(output[0], dict):
                # Extract final value from last entry
                final_entry = output[-1]
                value = final_entry.get('revenue') or final_entry.get('value') or final_entry.get('nav') or 0
                time_series = output
            else:
                # List of numbers
                value = output[-1] if output else 0
                time_series = output
        elif isinstance(output, dict):
            # Dict with time series data
            value = output.get('final_value') or output.get('value') or 0
            time_series = output.get('series') or output.get('projections') or []
        else:
            value = float(output) if output else 0
            time_series = []
        
        return {
            'value': value,
            'displayValue': f"{value:,.2f}" if isinstance(value, (int, float)) else str(value),
            'metadata': {
                'time_series': time_series,
                'raw_output': output,
                'output_type': 'time_series'
            }
        }
    
    def _transform_chart_output(
        self,
        action: ActionDefinition,
        output: Any
    ) -> Dict[str, Any]:
        """Transform chart output to standardized ChartConfig in metadata.chart_config."""
        if isinstance(output, dict):
            chart_type = output.get('type', 'bar')
            title = output.get('title', 'Chart')
            value = f"{chart_type}: {title}"
            # Standardize chart_config shape for ChartViewport/AgentChat: { type, title, data, renderType }
            chart_config = {
                'type': chart_type,
                'title': title,
                'data': output.get('data', {}),
                'renderType': output.get('renderType', 'tableau'),
            }
            # Preserve metrics, etc. for tooltips
            if output.get('metrics'):
                chart_config['metrics'] = output['metrics']
        else:
            value = str(output)
            chart_config = {}
        
        return {
            'value': value,
            'displayValue': value,
            'metadata': {
                'chart_config': chart_config,
                'chart_to_create': chart_config if isinstance(output, dict) else {},
                'raw_output': output,
                'output_type': 'chart'
            }
        }
    
    def _transform_string_output(
        self,
        action: ActionDefinition,
        output: Any
    ) -> Dict[str, Any]:
        """Transform string output"""
        value = str(output) if output else ""
        
        return {
            'value': value,
            'displayValue': value,
            'metadata': {
                'raw_output': output,
                'output_type': 'string'
            }
        }
    
    def _transform_multi_column_output(
        self,
        action: ActionDefinition,
        output: Any
    ) -> Dict[str, Any]:
        """
        Transform multi_column output. Service returns {
            'value': primary_value,
            'columns_to_create': [{'id': '...', 'name': '...', 'type': '...', 'values': {row_id: val, ...}}, ...],
            'chart_to_create': {...} (optional),
        }. Pass through to metadata for frontend to create columns.
        """
        if not isinstance(output, dict):
            output = {}
        primary = output.get('value') or output.get('fair_value') or 0
        columns_to_create = output.get('columns_to_create') or []
        chart_to_create = output.get('chart_to_create')
        raw_output = output
        
        display = f"{primary:,.2f}" if isinstance(primary, (int, float)) else str(primary)
        metadata = {
            'output_type': 'multi_column',
            'columns_to_create': columns_to_create,
            'raw_output': raw_output,
        }
        if chart_to_create is not None:
            metadata['chart_to_create'] = chart_to_create
        
        return {
            'value': primary,
            'displayValue': display,
            'metadata': metadata,
        }
    
    def _transform_array_output(
        self,
        action: ActionDefinition,
        output: Any
    ) -> Dict[str, Any]:
        """Transform array output - automatically generates charts for arrays and structures custom arrays"""
        # Get custom array structure from config
        output_structure = action.config.get('output_structure', 'default_array')
        
        # Handle dict with array value (e.g., {'comparables': [...], 'citations': [...]})
        if isinstance(output, dict) and 'comparables' in output:
            array_data = output['comparables']
            raw_output = output  # Keep full dict for raw_output
        elif isinstance(output, dict) and any(isinstance(v, list) for v in output.values()):
            # Find first list value in dict
            array_data = next((v for v in output.values() if isinstance(v, list)), output)
            raw_output = output
        elif isinstance(output, list):
            array_data = output
            raw_output = output
        else:
            # If output is a single object/dict, wrap it in an array for structured output
            if isinstance(output, dict):
                array_data = [output]
                raw_output = output
            else:
                array_data = [output] if output is not None else []
                raw_output = output
        
        # Structure the array data based on output_structure config
        structured_array = self._structure_custom_array(array_data, output_structure, action)
        
        # For arrays, use length or sum as cell value
        if isinstance(array_data, list):
            if len(array_data) > 0 and isinstance(array_data[0], (int, float)):
                value = sum(array_data)
            else:
                value = len(array_data)
        else:
            value = array_data
        
        # Automatically generate chart config for arrays with numeric data
        chart_config = None
        if isinstance(array_data, list) and len(array_data) > 0:
            # Check if array contains numeric data suitable for charting
            first_item = array_data[0]
            if isinstance(first_item, (int, float)):
                # Numeric array - generate line/bar chart
                chart_config = self._generate_chart_from_numeric_array(array_data, action)
            elif isinstance(first_item, dict):
                # Array of objects - try to extract chartable data
                chart_config = self._generate_chart_from_object_array(array_data, action)
        
        metadata = {
            'raw_output': raw_output,
            'output_type': 'array',
            'array_length': len(array_data) if isinstance(array_data, list) else 0,
            'output_structure': output_structure,
            'structured_array': structured_array  # Add structured array to metadata
        }
        
        # Add chart config to metadata if generated
        if chart_config:
            metadata['chart_config'] = chart_config
        
        return {
            'value': value,
            'displayValue': str(value),
            'metadata': metadata
        }
    
    def _transform_document_extract_output(self, service_output: Any) -> Dict[str, Any]:
        """Transform document extract output for matrix cell display."""
        if not isinstance(service_output, dict):
            return {
                'value': service_output,
                'displayValue': str(service_output),
                'metadata': {'raw_output': service_output, 'output_type': 'document_extract'}
            }
        extracted = service_output.get('value')
        summary = service_output.get('summary', '')
        meta = service_output.get('metadata') or {}
        # Build display: summary or count of top-level keys
        if summary:
            display_value = summary
        elif isinstance(extracted, dict):
            n = len([k for k, v in extracted.items() if v])
            display_value = f"{n} metrics extracted"
        else:
            display_value = str(extracted) if extracted else "No data"
        return {
            'value': extracted,
            'displayValue': display_value,
            'metadata': {
                **meta,
                'raw_output': service_output,
                'output_type': 'document_extract',
                'extracted_data': extracted,
            }
        }
    
    def _structure_custom_array(
        self,
        array_data: List[Any],
        output_structure: str,
        action: ActionDefinition
    ) -> List[Dict[str, Any]]:
        """
        Structure array data based on output_structure config.
        Creates custom arrays with consistent schemas for frontend consumption.
        """
        if not isinstance(array_data, list) or len(array_data) == 0:
            return []
        
        structured = []
        
        for item in array_data:
            if output_structure == 'company_data_array':
                # Structure: [{company, metrics, funding, team, ...}]
                structured_item = {
                    'company': item.get('company') or item.get('name') or item.get('company_name', ''),
                    'metrics': item.get('metrics') or {},
                    'funding': item.get('funding') or item.get('funding_history') or [],
                    'team': item.get('team') or item.get('employees') or [],
                    'valuation': item.get('valuation') or item.get('fair_value'),
                    'revenue': item.get('revenue') or item.get('arr'),
                    'sector': item.get('sector') or item.get('industry'),
                    'raw': item
                }
            elif output_structure == 'funding_rounds_array':
                # Structure: [{round, date, amount, investors, valuation, ...}]
                structured_item = {
                    'round': item.get('round') or item.get('round_type') or item.get('stage', ''),
                    'date': item.get('date') or item.get('announced_date') or item.get('closed_date', ''),
                    'amount': item.get('amount') or item.get('raised_amount') or item.get('value', 0),
                    'investors': item.get('investors') or item.get('lead_investor') or [],
                    'valuation': item.get('valuation') or item.get('post_money_valuation'),
                    'raw': item
                }
            elif output_structure == 'market_analysis_array':
                # Structure: [{metric, value, trend, ...}]
                structured_item = {
                    'metric': item.get('metric') or item.get('name') or item.get('key', ''),
                    'value': item.get('value') or item.get('data') or 0,
                    'trend': item.get('trend') or item.get('direction'),
                    'tam': item.get('tam') or item.get('total_addressable_market'),
                    'growth': item.get('growth') or item.get('growth_rate'),
                    'raw': item
                }
            elif output_structure == 'competitors_array':
                # Structure: [{company, similarity_score, metrics, ...}]
                structured_item = {
                    'company': item.get('company') or item.get('name') or item.get('competitor_name', ''),
                    'similarity_score': item.get('similarity_score') or item.get('score') or 0,
                    'metrics': item.get('metrics') or {},
                    'valuation': item.get('valuation') or item.get('fair_value'),
                    'revenue': item.get('revenue') or item.get('arr'),
                    'raw': item
                }
            elif output_structure == 'valuation_results_array':
                # Structure: [{method, fair_value, confidence, explanation, ...}]
                structured_item = {
                    'method': item.get('method') or item.get('method_used') or item.get('valuation_method', ''),
                    'fair_value': item.get('fair_value') or item.get('value') or item.get('valuation', 0),
                    'confidence': item.get('confidence') or item.get('confidence_score', 0),
                    'explanation': item.get('explanation') or item.get('rationale', ''),
                    'common_stock_value': item.get('common_stock_value'),
                    'preferred_value': item.get('preferred_value'),
                    'raw': item
                }
            elif output_structure == 'pwerm_scenarios_array':
                # Structure: [{scenario, probability, exit_value, return, ...}]
                structured_item = {
                    'scenario': item.get('scenario') or item.get('name') or item.get('exit_scenario', ''),
                    'probability': item.get('probability') or item.get('prob', 0),
                    'exit_value': item.get('exit_value') or item.get('exit_valuation', 0),
                    'return': item.get('return') or item.get('moic') or item.get('multiple', 0),
                    'raw': item
                }
            elif output_structure == 'financial_metrics_array':
                # Structure: [{metric, value, period, ...}]
                structured_item = {
                    'metric': item.get('metric') or item.get('name') or item.get('key', ''),
                    'value': item.get('value') or item.get('data') or 0,
                    'period': item.get('period') or item.get('date') or item.get('year', ''),
                    'type': item.get('type') or item.get('metric_type', ''),
                    'raw': item
                }
            elif output_structure == 'scenario_results_array':
                # Structure: [{scenario, metrics, outcomes, ...}]
                structured_item = {
                    'scenario': item.get('scenario') or item.get('name', ''),
                    'metrics': item.get('metrics') or {},
                    'outcomes': item.get('outcomes') or item.get('results', {}),
                    'probability': item.get('probability') or 0,
                    'raw': item
                }
            elif output_structure == 'comparison_matrix_array':
                # Structure: [{company, metrics_comparison, ...}]
                structured_item = {
                    'company': item.get('company') or item.get('name') or item.get('company_name', ''),
                    'metrics_comparison': item.get('metrics_comparison') or item.get('metrics', {}),
                    'rank': item.get('rank') or item.get('position'),
                    'raw': item
                }
            elif output_structure == 'deck_slides_array':
                # Structure: [{slide_number, title, content, type, ...}]
                structured_item = {
                    'slide_number': item.get('slide_number') or item.get('number') or 0,
                    'title': item.get('title') or item.get('heading', ''),
                    'content': item.get('content') or item.get('text') or item.get('body', ''),
                    'type': item.get('type') or item.get('slide_type', ''),
                    'raw': item
                }
            elif output_structure == 'spreadsheet_data_array':
                # Structure: [{row, columns, values, ...}]
                structured_item = {
                    'row': item.get('row') or item.get('row_index') or 0,
                    'columns': item.get('columns') or item.get('headers', []),
                    'values': item.get('values') or item.get('data', []),
                    'raw': item
                }
            elif output_structure == 'memo_sections_array':
                # Structure: [{section, title, content, ...}]
                structured_item = {
                    'section': item.get('section') or item.get('section_name') or '',
                    'title': item.get('title') or item.get('heading', ''),
                    'content': item.get('content') or item.get('text') or item.get('body', ''),
                    'raw': item
                }
            elif output_structure == 'cap_table_rows_array':
                # Structure: [{shareholder, shares, ownership, dilution, ...}]
                structured_item = {
                    'shareholder': item.get('shareholder') or item.get('name') or item.get('investor', ''),
                    'shares': item.get('shares') or item.get('share_count', 0),
                    'ownership': item.get('ownership') or item.get('ownership_percentage', 0),
                    'dilution': item.get('dilution') or item.get('dilution_impact', 0),
                    'raw': item
                }
            elif output_structure == 'portfolio_metrics_array':
                # Structure: [{metric, value, company, ...}]
                structured_item = {
                    'metric': item.get('metric') or item.get('name') or item.get('key', ''),
                    'value': item.get('value') or item.get('data') or 0,
                    'company': item.get('company') or item.get('company_name', ''),
                    'raw': item
                }
            elif output_structure == 'fund_metrics_array':
                # Structure: [{metric, value, period, ...}]
                structured_item = {
                    'metric': item.get('metric') or item.get('name') or item.get('key', ''),
                    'value': item.get('value') or item.get('data') or 0,
                    'period': item.get('period') or item.get('date', ''),
                    'raw': item
                }
            elif output_structure == 'stage_analysis_array':
                # Structure: [{stage, companies, metrics, ...}]
                structured_item = {
                    'stage': item.get('stage') or item.get('stage_name') or '',
                    'companies': item.get('companies') or item.get('company_list', []),
                    'metrics': item.get('metrics') or {},
                    'raw': item
                }
            elif output_structure == 'exit_scenarios_array':
                # Structure: [{scenario, exit_value, return, probability, ...}]
                structured_item = {
                    'scenario': item.get('scenario') or item.get('name') or item.get('exit_type', ''),
                    'exit_value': item.get('exit_value') or item.get('exit_valuation', 0),
                    'return': item.get('return') or item.get('moic') or item.get('multiple', 0),
                    'probability': item.get('probability') or item.get('prob', 0),
                    'raw': item
                }
            else:
                # Default structure: preserve as much as possible
                structured_item = {
                    'data': item if isinstance(item, dict) else {'value': item},
                    'raw': item
                }
            
            structured.append(structured_item)
        
        return structured
    
    def _generate_chart_from_numeric_array(
        self,
        array_data: List[Union[int, float]],
        action: ActionDefinition
    ) -> Optional[Dict[str, Any]]:
        """Generate chart config from numeric array"""
        try:
            # Determine chart type based on data characteristics
            chart_type = 'line'  # Default for time series
            if len(array_data) <= 10:
                chart_type = 'bar'  # Bar chart for small datasets
            
            # Generate labels
            labels = [f'Item {i+1}' for i in range(len(array_data))]
            
            # Create chart config
            chart_config = {
                'type': chart_type,
                'title': f'{action.name} Visualization',
                'data': {
                    'labels': labels,
                    'datasets': [{
                        'label': action.name,
                        'data': array_data,
                        'backgroundColor': '#4285F4' if chart_type == 'bar' else 'rgba(66, 133, 244, 0.2)',
                        'borderColor': '#4285F4',
                        'borderWidth': 2
                    }]
                },
                'renderType': 'basic',
                'config': {
                    'width': '100%',
                    'height': 300,
                    'interactive': True
                }
            }
            
            return chart_config
        except Exception as e:
            logger.warning(f"Failed to generate chart from numeric array: {e}")
            return None
    
    def _generate_chart_from_object_array(
        self,
        array_data: List[Dict[str, Any]],
        action: ActionDefinition
    ) -> Optional[Dict[str, Any]]:
        """Generate chart config from array of objects"""
        try:
            if not array_data or len(array_data) == 0:
                return None
            
            first_item = array_data[0]
            
            # Try to find common numeric fields
            numeric_fields = [k for k, v in first_item.items() if isinstance(v, (int, float))]
            name_fields = [k for k in first_item.keys() if k.lower() in ['name', 'label', 'title', 'company', 'id']]
            
            if not numeric_fields:
                return None
            
            # Use first numeric field as value
            value_field = numeric_fields[0]
            label_field = name_fields[0] if name_fields else None
            
            # Extract data
            labels = [str(item.get(label_field, f'Item {i+1}')) for i, item in enumerate(array_data)]
            values = [item.get(value_field, 0) for item in array_data]
            
            # Determine chart type
            chart_type = 'bar' if len(array_data) <= 20 else 'line'
            
            chart_config = {
                'type': chart_type,
                'title': f'{action.name} - {value_field}',
                'data': {
                    'labels': labels,
                    'datasets': [{
                        'label': value_field.replace('_', ' ').title(),
                        'data': values,
                        'backgroundColor': '#4285F4' if chart_type == 'bar' else 'rgba(66, 133, 244, 0.2)',
                        'borderColor': '#4285F4',
                        'borderWidth': 2
                    }]
                },
                'renderType': 'basic',
                'config': {
                    'width': '100%',
                    'height': 300,
                    'interactive': True
                }
            }
            
            return chart_config
        except Exception as e:
            logger.warning(f"Failed to generate chart from object array: {e}")
            return None
    
    def _extract_nested_value(self, obj: Any, path: str) -> Any:
        """Extract value from nested object using dot notation"""
        keys = path.split('.')
        current = obj
        
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            elif hasattr(current, key):
                current = getattr(current, key)
            else:
                return None
        
        return current
    
    def _extract_default_value(self, action: ActionDefinition, output: Dict[str, Any]) -> Any:
        """Extract default value based on service type"""
        service_name = action.service_name.lower()
        
        # Valuation services - handle ValuationResult objects
        if 'valuation' in service_name or 'pwerm' in action.action_id:
            # Handle ValuationResult dataclass
            if hasattr(output, 'fair_value'):
                return output.fair_value
            # Handle dict with raw_result containing ValuationResult
            if 'raw_result' in output and hasattr(output['raw_result'], 'fair_value'):
                return output['raw_result'].fair_value
            # Handle dict format
            return output.get('fair_value') or output.get('value') or output.get('common_stock_value') or 0
        
        # Revenue projection services
        if 'revenue' in service_name or 'projection' in service_name:
            if isinstance(output, list):
                return output[-1].get('revenue') if output else 0
            return output.get('revenue') or output.get('final_value') or output.get('value') or 0
        
        # Fund metrics
        if 'fund' in service_name or 'metrics' in service_name:
            return output.get('total_nav') or output.get('nav') or output.get('total_invested') or output.get('value') or 0
        
        # Follow-on strategy
        if 'follow' in service_name or 'strategy' in service_name:
            return output.get('strategy') or output.get('recommendation') or output.get('value') or ""
        
        # NAV services
        if 'nav' in service_name:
            if isinstance(output, dict) and 'valuation' in output:
                return output.get('valuation', 0)
            return output.get('nav') or output.get('value') or 0
        
        # Market intelligence - comparables
        if 'market' in service_name and 'comparables' in action.action_id:
            # Return count of comparables found
            if isinstance(output, list):
                return len(output)
            return output.get('count', 0) if isinstance(output, dict) else 0
        
        # Document (document_query_service) - extract/analyze return value, summary
        if 'document' in service_name:
            return output.get('value') or output.get('summary') or ""
        
        # Debt (advanced_debt_structures) - dataclass __dict__ has total_debt, debt_to_equity_ratio
        if 'debt' in service_name or 'debt' in action.action_id:
            return (
                output.get('value')
                or output.get('total_debt')
                or output.get('debt_to_equity_ratio')
                or output.get('recommendation')
                or output.get('summary')
                or 0
            )
        
        # Scoring (company_scoring_visualizer) - CompanyScore has overall_score
        if 'scoring' in service_name or 'scoring' in action.action_id:
            return (
                output.get('overall_score')
                or output.get('score')
                or output.get('total_score')
                or output.get('value')
                or 0
            )
        
        # Gap filler (intelligent_gap_filler) - various analysis dicts
        if 'gap_filler' in service_name:
            return (
                output.get('value')
                or output.get('overall_score')
                or output.get('score')
                or output.get('ai_adjusted_multiple')
                or output.get('momentum_score')
                or output.get('tam_value')
                or output.get('recommendation')
                or 0
            )
        
        # Default: try common keys
        return output.get('value') or output.get('result') or output.get('data') or 0
    
    def initialize_core_services(self) -> None:
        """Initialize core service registrations"""
        if self._initialized:
            return
        
        # Financial formulas
        self.register_formula(
            action_id="financial.irr",
            name="IRR",
            service_name="financial_tools",
            required_inputs={"cash_flows": "array"},
            output_type=OutputType.NUMBER,
            description="Internal Rate of Return",
            column_compatibility=['number', 'percentage']
        )
        
        self.register_formula(
            action_id="financial.npv",
            name="NPV",
            service_name="financial_tools",
            required_inputs={"cash_flows": "array", "discount_rate": "number"},
            output_type=OutputType.NUMBER,
            description="Net Present Value",
            column_compatibility=['number', 'currency']
        )
        
        self.register_formula(
            action_id="financial.moic",
            name="MOIC",
            service_name="financial_tools",
            required_inputs={"exit_value": "number", "investment": "number"},
            output_type=OutputType.NUMBER,
            description="Multiple on Invested Capital",
            column_compatibility=['number']
        )
        
        self.register_formula(
            action_id="financial.cagr",
            name="CAGR",
            service_name="financial_tools",
            required_inputs={"beginning_value": "number", "ending_value": "number", "years": "number"},
            output_type=OutputType.NUMBER,
            description="Compound Annual Growth Rate",
            column_compatibility=['number', 'percentage']
        )
        
        # Valuation workflows
        self.register_workflow(
            action_id="valuation_engine.pwerm",
            name="PWERM Valuation",
            service_name="valuation_engine",
            api_endpoint="/api/valuation/pwerm",
            required_inputs={"company_id": "string"},
            output_type=OutputType.OBJECT,
            output_transform="fair_value",
            description="Probability-Weighted Expected Return Method",
            column_compatibility=['number', 'currency']
        )
        
        self.register_workflow(
            action_id="valuation_engine.dcf",
            name="DCF Valuation",
            service_name="valuation_engine_service",
            required_inputs={"company_id": "string"},
            output_type=OutputType.OBJECT,
            output_transform="fair_value",
            description="Discounted Cash Flow",
            column_compatibility=['number', 'currency']
        )
        
        self.register_workflow(
            action_id="valuation_engine.auto",
            name="Auto Valuation",
            service_name="valuation_engine_service",
            required_inputs={"company_id": "string"},
            output_type=OutputType.OBJECT,
            output_transform="fair_value",
            description="Automatic valuation method selection",
            column_compatibility=['number', 'currency']
        )
        
        # Revenue projection workflow
        self.register_workflow(
            action_id="revenue_projection.build",
            name="Build Revenue Projection",
            service_name="revenue_projection_service",
            api_endpoint="/api/revenue/project",
            required_inputs={"base_revenue": "number", "initial_growth": "number", "years": "number"},
            output_type=OutputType.MULTI_COLUMN,
            description="Project revenue with growth decay (creates columns for each year + chart)",
            column_compatibility=['number', 'currency']
        )
        
        # Chart generation workflow
        self.register_workflow(
            action_id="chart_intelligence.generate",
            name="Generate Chart",
            service_name="chart_intelligence",
            api_endpoint="/api/charts/generate",
            required_inputs={"data": "object"},
            output_type=OutputType.CHART,
            description="Generate chart from data",
            column_compatibility=['string', 'chart']
        )
        
        # NAV calculation workflow
        self.register_workflow(
            action_id="nav.calculate",
            name="Calculate NAV",
            service_name="nav_service",
            api_endpoint="/api/portfolio/{fund_id}/nav",
            required_inputs={"company_id": "string", "fund_id": "string"},
            output_type=OutputType.NUMBER,
            description="Calculate Net Asset Value",
            column_compatibility=['number', 'currency']
        )
        
        # NAV time series workflow
        self.register_workflow(
            action_id="nav.timeseries",
            name="NAV Time Series",
            service_name="nav_service",
            api_endpoint="/api/portfolio/{fund_id}/nav-timeseries",
            required_inputs={"fund_id": "string"},
            output_type=OutputType.TIME_SERIES,
            description="NAV over time",
            column_compatibility=['number', 'currency', 'time_series']
        )
        
        # Fund metrics workflow
        self.register_workflow(
            action_id="fund_metrics.calculate",
            name="Fund Metrics",
            service_name="fund_metrics_service",
            api_endpoint="/api/funds/{fund_id}/metrics",
            required_inputs={"fund_id": "string"},
            output_type=OutputType.OBJECT,
            output_transform="total_nav",
            description="Calculate fund-level metrics",
            column_compatibility=['number', 'currency', 'object']
        )
        
        # Follow-on strategy workflow
        self.register_workflow(
            action_id="followon_strategy.recommend",
            name="Follow-On Strategy",
            service_name="followon_strategy_service",
            api_endpoint="/api/portfolio/{fund_id}/followon-strategy",
            required_inputs={"company_id": "string", "fund_id": "string"},
            output_type=OutputType.OBJECT,
            output_transform="strategy",
            description="Recommend follow-on investment strategy",
            column_compatibility=['string', 'object']
        )
        
        # Market Intelligence - Find Comparables (CRITICAL)
        self.register_workflow(
            action_id="market.find_comparables",
            name="Find Comparables",
            service_name="market_intelligence_service",
            required_inputs={
                "company_id": "string",
                "geography": "string",
                "sector": "string",
                "arr": "number",
                "limit": "number"
            },
            output_type=OutputType.ARRAY,
            description="Find comparable companies by geography and sector",
            column_compatibility=['array', 'object']
        )
        
        # Document services
        self.register_workflow(
            action_id="document.extract",
            name="Extract Document Data",
            service_name="document_query_service",
            required_inputs={"document_id": "string", "extraction_type": "string"},
            output_type=OutputType.OBJECT,
            description="Extract structured data from document",
            column_compatibility=['object', 'string']
        )
        
        self.register_workflow(
            action_id="document.analyze",
            name="Analyze Document",
            service_name="document_query_service",
            required_inputs={"document_id": "string"},
            output_type=OutputType.OBJECT,
            description="Analyze document content",
            column_compatibility=['object', 'string']
        )
        
        # Portfolio services
        self.register_workflow(
            action_id="portfolio.total_nav",
            name="Total NAV",
            service_name="portfolio_service",
            required_inputs={"fund_id": "string"},
            output_type=OutputType.NUMBER,
            description="Calculate total portfolio NAV",
            column_compatibility=['number', 'currency']
        )
        
        self.register_workflow(
            action_id="portfolio.total_invested",
            name="Total Invested",
            service_name="portfolio_service",
            required_inputs={"fund_id": "string"},
            output_type=OutputType.NUMBER,
            description="Calculate total invested capital",
            column_compatibility=['number', 'currency']
        )
        
        self.register_workflow(
            action_id="portfolio.dpi",
            name="DPI (Distributed to Paid-In)",
            service_name="portfolio_service",
            required_inputs={"fund_id": "string"},
            output_type=OutputType.NUMBER,
            description="Calculate DPI ratio",
            column_compatibility=['number', 'percentage']
        )
        
        self.register_workflow(
            action_id="portfolio.tvpi",
            name="TVPI (Total Value to Paid-In)",
            service_name="portfolio_service",
            required_inputs={"fund_id": "string"},
            output_type=OutputType.NUMBER,
            description="Calculate TVPI ratio",
            column_compatibility=['number']
        )
        
        self.register_workflow(
            action_id="portfolio.dpi_sankey",
            name="DPI Sankey Visualization",
            service_name="portfolio_service",
            required_inputs={"fund_id": "string"},
            output_type=OutputType.CHART,
            description="Generate DPI flow Sankey: Fund → Companies → Exits → Distributions",
            column_compatibility=['chart', 'object']
        )
        
        self.register_workflow(
            action_id="portfolio.optimize",
            name="Portfolio Optimization",
            service_name="portfolio_service",
            api_endpoint="/api/position-sizing/optimize-portfolio",
            required_inputs={"fund_id": "string", "constraints": "object"},
            output_type=OutputType.OBJECT,
            description="Mean-variance portfolio optimization with efficient frontier",
            column_compatibility=['object', 'chart']
        )
        
        # Waterfall services
        self.register_workflow(
            action_id="waterfall.calculate",
            name="Calculate Liquidation Waterfall",
            service_name="advanced_cap_table",
            required_inputs={
                "exit_value": "number",
                "company_id": "string",
                "fund_id": "string"
            },
            output_type=OutputType.OBJECT,
            description="Calculate liquidation waterfall distribution",
            column_compatibility=['number', 'currency', 'object']
        )
        
        self.register_workflow(
            action_id="waterfall.breakpoints",
            name="Waterfall Breakpoints",
            service_name="advanced_cap_table",
            required_inputs={
                "exit_value": "number",
                "company_id": "string"
            },
            output_type=OutputType.OBJECT,
            description="Calculate waterfall breakpoints for visualization",
            column_compatibility=['object']
        )
        
        self.register_workflow(
            action_id="waterfall.exit_scenarios",
            name="Exit Scenario Waterfall",
            service_name="advanced_cap_table",
            required_inputs={
                "exit_value": "number",
                "company_id": "string",
                "exit_type": "string"
            },
            output_type=OutputType.OBJECT,
            description="Calculate waterfall for specific exit scenarios",
            column_compatibility=['object']
        )
        
        # Cap table services
        self.register_workflow(
            action_id="cap_table.calculate",
            name="Calculate Cap Table",
            service_name="pre_post_cap_table",
            required_inputs={"company_id": "string"},
            output_type=OutputType.OBJECT,
            description="Calculate full cap table history through all rounds",
            column_compatibility=['object']
        )
        
        self.register_workflow(
            action_id="cap_table.ownership",
            name="Calculate Ownership",
            service_name="advanced_cap_table",
            required_inputs={
                "company_id": "string",
                "as_of_date": "string"
            },
            output_type=OutputType.OBJECT,
            description="Calculate ownership percentages at a point in time",
            column_compatibility=['object', 'percentage']
        )
        
        self.register_workflow(
            action_id="cap_table.dilution",
            name="Calculate Dilution Path",
            service_name="pre_post_cap_table",
            required_inputs={"company_id": "string"},
            output_type=OutputType.OBJECT,
            description="Calculate dilution path through funding rounds",
            column_compatibility=['object']
        )
        
        # Ownership & Return Analysis services
        self.register_workflow(
            action_id="ownership.analyze",
            name="Analyze Ownership Scenarios",
            service_name="ownership_return_analyzer",
            required_inputs={
                "company_id": "string",
                "investment_amount": "number",
                "pre_money_valuation": "number"
            },
            output_type=OutputType.OBJECT,
            description="Calculate ownership scenarios with dilution",
            column_compatibility=['object', 'percentage']
        )
        
        self.register_workflow(
            action_id="ownership.return_scenarios",
            name="Return Scenarios Analysis",
            service_name="ownership_return_analyzer",
            required_inputs={
                "company_id": "string",
                "investment_amount": "number",
                "exit_value": "number"
            },
            output_type=OutputType.OBJECT,
            description="Calculate return scenarios with different exit values",
            column_compatibility=['object']
        )
        
        # M&A Workflow services
        self.register_workflow(
            action_id="ma.model_acquisition",
            name="Model M&A Transaction",
            service_name="ma_workflow_service",
            required_inputs={
                "acquirer": "string",
                "target": "string",
                "deal_rationale": "string"
            },
            output_type=OutputType.OBJECT,
            description="Model complete M&A transaction with synergies",
            column_compatibility=['object']
        )
        
        self.register_workflow(
            action_id="ma.transactions",
            name="M&A Transaction Search",
            service_name="ma_workflow_service",
            required_inputs={
                "target": "string",
                "industry": "string"
            },
            output_type=OutputType.ARRAY,
            description="Search for comparable M&A transactions",
            column_compatibility=['array', 'object']
        )
        
        # Additional Valuation Methods
        self.register_workflow(
            action_id="valuation_engine.opm",
            name="OPM Valuation",
            service_name="valuation_engine_service",
            required_inputs={"company_id": "string"},
            output_type=OutputType.OBJECT,
            output_transform="fair_value",
            description="Option Pricing Model valuation method",
            column_compatibility=['number', 'currency']
        )
        
        self.register_workflow(
            action_id="valuation_engine.waterfall",
            name="Waterfall Valuation",
            service_name="valuation_engine_service",
            required_inputs={"company_id": "string"},
            output_type=OutputType.OBJECT,
            output_transform="fair_value",
            description="Waterfall-based valuation method",
            column_compatibility=['number', 'currency']
        )
        
        self.register_workflow(
            action_id="valuation_engine.recent_transaction",
            name="Recent Transaction Valuation",
            service_name="valuation_engine_service",
            required_inputs={"company_id": "string"},
            output_type=OutputType.OBJECT,
            output_transform="fair_value",
            description="Valuation based on recent transaction multiples",
            column_compatibility=['number', 'currency']
        )
        
        self.register_workflow(
            action_id="valuation_engine.cost_method",
            name="Cost Method Valuation",
            service_name="valuation_engine_service",
            required_inputs={"company_id": "string"},
            output_type=OutputType.OBJECT,
            output_transform="fair_value",
            description="Cost-based valuation method",
            column_compatibility=['number', 'currency']
        )
        
        self.register_workflow(
            action_id="valuation_engine.milestone",
            name="Milestone Valuation",
            service_name="valuation_engine_service",
            required_inputs={"company_id": "string"},
            output_type=OutputType.OBJECT,
            output_transform="fair_value",
            description="Milestone-based valuation method",
            column_compatibility=['number', 'currency']
        )
        
        # Unified MCP Orchestrator Skills - Data Gathering (ALL skills from registry)
        self.register_workflow(
            action_id="skill.company_data_fetch",
            name="Fetch Company Data",
            service_name="unified_mcp_orchestrator",
            required_inputs={"company": "string"},
            output_type=OutputType.ARRAY,  # Changed to ARRAY for structured data
            description="Fetch company metrics, funding, team data",
            column_compatibility=['array', 'object', 'string'],
            config={"output_structure": "company_data_array"}  # Custom array structure
        )
        
        self.register_workflow(
            action_id="skill.funding_aggregation",
            name="Aggregate Funding History",
            service_name="unified_mcp_orchestrator",
            required_inputs={"company_id": "string"},
            output_type=OutputType.ARRAY,
            description="Aggregate funding rounds and history",
            column_compatibility=['array', 'object'],
            config={"output_structure": "funding_rounds_array"}
        )
        
        self.register_workflow(
            action_id="skill.market_research",
            name="Market Research",
            service_name="unified_mcp_orchestrator",
            required_inputs={"company": "string", "sector": "string"},
            output_type=OutputType.ARRAY,  # Changed to ARRAY for structured data
            description="Market analysis, TAM, trends",
            column_compatibility=['array', 'object', 'string'],
            config={"output_structure": "market_analysis_array"}
        )
        
        self.register_workflow(
            action_id="skill.competitive_analysis",
            name="Competitive Analysis",
            service_name="unified_mcp_orchestrator",
            required_inputs={"company": "string"},
            output_type=OutputType.ARRAY,
            description="Competitor analysis and comparison",
            column_compatibility=['array', 'object'],
            config={"output_structure": "competitors_array"}
        )
        
        # Unified MCP Orchestrator Skills - Analysis
        self.register_workflow(
            action_id="skill.valuation_engine",
            name="Valuation Engine",
            service_name="unified_mcp_orchestrator",
            required_inputs={"company_id": "string"},
            output_type=OutputType.ARRAY,  # Changed to ARRAY for structured valuation data
            description="DCF, comparables valuation",
            column_compatibility=['array', 'object', 'number', 'currency'],
            config={"output_structure": "valuation_results_array"}
        )
        
        self.register_workflow(
            action_id="skill.pwerm_calculator",
            name="PWERM Calculator",
            service_name="unified_mcp_orchestrator",
            required_inputs={"company_id": "string"},
            output_type=OutputType.ARRAY,  # Changed to ARRAY for structured PWERM data
            description="PWERM valuation",
            column_compatibility=['array', 'object', 'number', 'currency'],
            config={"output_structure": "pwerm_scenarios_array"}
        )
        
        self.register_workflow(
            action_id="skill.financial_analysis",
            name="Financial Analysis",
            service_name="unified_mcp_orchestrator",
            required_inputs={"company_id": "string"},
            output_type=OutputType.ARRAY,  # Changed to ARRAY for structured metrics
            description="Ratios, projections, financial metrics",
            column_compatibility=['array', 'object', 'number'],
            config={"output_structure": "financial_metrics_array"}
        )
        
        self.register_workflow(
            action_id="skill.scenario_analysis",
            name="Scenario Analysis",
            service_name="unified_mcp_orchestrator",
            required_inputs={"company_id": "string", "scenarios": "array"},
            output_type=OutputType.ARRAY,
            description="Monte Carlo, sensitivity analysis",
            column_compatibility=['array', 'object'],
            config={"output_structure": "scenario_results_array"}
        )
        
        self.register_workflow(
            action_id="skill.deal_comparison",
            name="Deal Comparison",
            service_name="unified_mcp_orchestrator",
            required_inputs={"company_ids": "array"},
            output_type=OutputType.ARRAY,
            description="Multi-company comparison analysis",
            column_compatibility=['array', 'object'],
            config={"output_structure": "comparison_matrix_array"}
        )
        
        # Unified MCP Orchestrator Skills - Generation
        self.register_workflow(
            action_id="skill.deck_storytelling",
            name="Generate Deck/Presentation",
            service_name="unified_mcp_orchestrator",
            required_inputs={"company_id": "string", "deck_type": "string"},
            output_type=OutputType.ARRAY,  # Changed to ARRAY for structured slides
            description="Presentation generation",
            column_compatibility=['array', 'object', 'string'],
            config={"output_structure": "deck_slides_array"}
        )
        
        self.register_workflow(
            action_id="skill.excel_generation",
            name="Generate Excel/Spreadsheet",
            service_name="unified_mcp_orchestrator",
            required_inputs={"data": "object", "format": "string"},
            output_type=OutputType.ARRAY,  # Changed to ARRAY for structured spreadsheet data
            description="Create spreadsheet from data",
            column_compatibility=['array', 'object', 'string'],
            config={"output_structure": "spreadsheet_data_array"}
        )
        
        self.register_workflow(
            action_id="skill.memo_generation",
            name="Generate Memo",
            service_name="unified_mcp_orchestrator",
            required_inputs={"company_id": "string", "memo_type": "string"},
            output_type=OutputType.ARRAY,  # Changed to ARRAY for structured memo sections
            description="Generate investment memo document",
            column_compatibility=['array', 'object', 'string'],
            config={"output_structure": "memo_sections_array"}
        )
        
        self.register_workflow(
            action_id="skill.chart_generation",
            name="Generate Chart",
            service_name="unified_mcp_orchestrator",
            required_inputs={"data": "object", "chart_type": "string"},
            output_type=OutputType.CHART,
            description="Data visualization",
            column_compatibility=['chart', 'object'],
            config={"output_structure": "chart_config"}
        )
        
        # Unified MCP Orchestrator Skills - Portfolio & Fund
        self.register_workflow(
            action_id="skill.cap_table_generation",
            name="Generate Cap Table",
            service_name="unified_mcp_orchestrator",
            required_inputs={"company_id": "string"},
            output_type=OutputType.ARRAY,  # Changed to ARRAY for structured cap table rows
            description="Generate cap tables with ownership",
            column_compatibility=['array', 'object'],
            config={"output_structure": "cap_table_rows_array"}
        )
        
        self.register_workflow(
            action_id="skill.portfolio_analysis",
            name="Portfolio Analysis",
            service_name="unified_mcp_orchestrator",
            required_inputs={"fund_id": "string"},
            output_type=OutputType.ARRAY,  # Changed to ARRAY for structured portfolio metrics
            description="Analyze fund portfolio performance",
            column_compatibility=['array', 'object'],
            config={"output_structure": "portfolio_metrics_array"}
        )
        
        self.register_workflow(
            action_id="skill.fund_metrics_calculator",
            name="Fund Metrics Calculator",
            service_name="unified_mcp_orchestrator",
            required_inputs={"fund_id": "string"},
            output_type=OutputType.ARRAY,  # Changed to ARRAY for structured fund metrics
            description="Calculate DPI, TVPI, IRR",
            column_compatibility=['array', 'object', 'number'],
            config={"output_structure": "fund_metrics_array"}
        )
        
        self.register_workflow(
            action_id="skill.stage_analysis",
            name="Stage Analysis",
            service_name="unified_mcp_orchestrator",
            required_inputs={"company_ids": "array"},
            output_type=OutputType.ARRAY,
            description="Multi-stage investment analysis",
            column_compatibility=['array', 'object'],
            config={"output_structure": "stage_analysis_array"}
        )
        
        self.register_workflow(
            action_id="skill.exit_modeling",
            name="Exit Modeling",
            service_name="unified_mcp_orchestrator",
            required_inputs={"company_id": "string", "exit_scenarios": "array"},
            output_type=OutputType.ARRAY,
            description="Model exit scenarios and returns",
            column_compatibility=['array', 'object'],
            config={"output_structure": "exit_scenarios_array"}
        )
        
        # Enhanced NAV services with better time series support
        self.register_workflow(
            action_id="nav.calculate_company",
            name="Calculate Company NAV",
            service_name="nav_service",
            required_inputs={"company_id": "string", "fund_id": "string"},
            output_type=OutputType.NUMBER,
            description="Calculate NAV for a specific company",
            column_compatibility=['number', 'currency']
        )
        
        self.register_workflow(
            action_id="nav.calculate_portfolio",
            name="Calculate Portfolio NAV",
            service_name="nav_service",
            required_inputs={"fund_id": "string"},
            output_type=OutputType.NUMBER,
            description="Calculate total portfolio NAV",
            column_compatibility=['number', 'currency']
        )
        
        self.register_workflow(
            action_id="nav.timeseries_company",
            name="Company NAV Time Series",
            service_name="nav_service",
            required_inputs={"company_id": "string", "fund_id": "string"},
            output_type=OutputType.TIME_SERIES,
            description="NAV over time for a company",
            column_compatibility=['time_series', 'number']
        )
        
        self.register_workflow(
            action_id="nav.forecast",
            name="NAV Forecast",
            service_name="nav_service",
            required_inputs={"fund_id": "string", "periods": "number"},
            output_type=OutputType.TIME_SERIES,
            description="Forecast NAV using linear regression (like pacing)",
            column_compatibility=['time_series', 'number']
        )
        
        # Market Intelligence Workflows
        self.register_workflow(
            action_id="market.timing_analysis",
            name="Market Timing Analysis",
            service_name="market_intelligence_service",
            required_inputs={"sector": "string", "geography": "string"},
            output_type=OutputType.OBJECT,
            description="Analyze market timing for investment decisions",
            mode_availability=['query', 'custom'],
            column_compatibility=['object', 'string']
        )
        
        self.register_workflow(
            action_id="market.investment_readiness",
            name="Investment Readiness Scoring",
            service_name="market_intelligence_service",
            required_inputs={"companies": "array"},
            output_type=OutputType.ARRAY,
            description="Score companies for investment readiness",
            mode_availability=['query', 'custom'],
            column_compatibility=['array', 'object']
        )
        
        self.register_workflow(
            action_id="market.sector_landscape",
            name="Sector Landscape",
            service_name="market_intelligence_service",
            required_inputs={"sector": "string", "geography": "string"},
            output_type=OutputType.CHART,
            description="Generate sector landscape visualization",
            mode_availability=['query', 'custom'],
            column_compatibility=['chart', 'object']
        )
        
        # Company Scoring Workflows
        self.register_workflow(
            action_id="scoring.score_company",
            name="Score Company",
            service_name="company_scoring_visualizer",
            required_inputs={"company_id": "string"},
            output_type=OutputType.OBJECT,
            description="Comprehensive company scoring with scenarios",
            mode_availability=['portfolio', 'query'],
            column_compatibility=['object', 'number']
        )
        
        self.register_workflow(
            action_id="scoring.portfolio_dashboard",
            name="Portfolio Dashboard",
            service_name="company_scoring_visualizer",
            required_inputs={"fund_id": "string"},
            output_type=OutputType.OBJECT,
            description="Generate portfolio-level dashboard",
            mode_availability=['portfolio'],
            column_compatibility=['object', 'chart']
        )
        
        # Intelligent Gap Filler Components
        self.register_workflow(
            action_id="gap_filler.ai_impact",
            name="AI Impact Analysis",
            service_name="intelligent_gap_filler",
            required_inputs={"company_id": "string"},
            output_type=OutputType.OBJECT,
            description="Analyze AI impact on company",
            mode_availability=['portfolio', 'query'],
            column_compatibility=['object', 'string']
        )
        
        self.register_workflow(
            action_id="gap_filler.ai_valuation",
            name="AI-Adjusted Valuation",
            service_name="intelligent_gap_filler",
            required_inputs={"company_id": "string"},
            output_type=OutputType.OBJECT,
            description="Calculate AI-adjusted valuation",
            mode_availability=['portfolio', 'query'],
            column_compatibility=['object', 'number', 'currency']
        )
        
        self.register_workflow(
            action_id="gap_filler.market_opportunity",
            name="Market Opportunity Analysis",
            service_name="intelligent_gap_filler",
            required_inputs={"company_id": "string"},
            output_type=OutputType.OBJECT,
            description="Analyze market opportunity",
            mode_availability=['portfolio', 'query'],
            column_compatibility=['object']
        )
        
        self.register_workflow(
            action_id="gap_filler.momentum",
            name="Company Momentum Analysis",
            service_name="intelligent_gap_filler",
            required_inputs={"company_id": "string"},
            output_type=OutputType.OBJECT,
            description="Analyze company momentum signals",
            mode_availability=['portfolio', 'query'],
            column_compatibility=['object', 'number']
        )
        
        self.register_workflow(
            action_id="gap_filler.fund_fit",
            name="Fund Fit Scoring",
            service_name="intelligent_gap_filler",
            required_inputs={"company_id": "string", "fund_id": "string"},
            output_type=OutputType.OBJECT,
            description="Score company for fund fit",
            mode_availability=['portfolio'],
            column_compatibility=['object', 'number', 'percentage']
        )
        
        # M&A Synergy
        self.register_workflow(
            action_id="ma.synergy",
            name="Calculate M&A Synergy",
            service_name="ma_workflow_service",
            required_inputs={"acquirer": "string", "target": "string", "deal_rationale": "string"},
            output_type=OutputType.OBJECT,
            description="Calculate M&A synergy value",
            mode_availability=['query', 'custom'],
            column_compatibility=['object', 'number', 'currency']
        )
        
        # Chain Execution — run multiple actions in sequence, piping outputs forward
        self.register_workflow(
            action_id="chain.execute",
            name="Chain Execute",
            service_name="chain_executor",
            required_inputs={"steps": "array"},
            output_type=OutputType.OBJECT,
            description=(
                "Execute multiple cell actions sequentially. "
                "Each step receives the previous step's output as additional inputs. "
                "Payload: {steps: [{action_id, inputs}, ...], shared_inputs?: {}}."
            ),
            mode_availability=['portfolio', 'query', 'custom', 'lp'],
            column_compatibility=['object', 'array']
        )

        # Scenario Composition Workflow
        self.register_workflow(
            action_id="scenario.compose",
            name="Compose Scenario",
            service_name="matrix_scenario_service",
            required_inputs={"query": "string"},
            output_type=OutputType.OBJECT,
            description="Parse 'what if' scenario query and calculate matrix cell impacts",
            mode_availability=['portfolio', 'query', 'custom', 'lp'],
            column_compatibility=['number', 'currency', 'percentage', 'object']
        )
        
        self._initialized = True
        logger.info(f"Initialized {len(self._actions)} core cell actions")


# Global registry instance
_registry_instance: Optional[CellActionRegistry] = None


def get_registry() -> CellActionRegistry:
    """Get global registry instance"""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = CellActionRegistry()
        _registry_instance.initialize_core_services()
    return _registry_instance
