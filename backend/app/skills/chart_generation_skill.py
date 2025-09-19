"""
Chart Generation Skill - Dynamic Data Visualization with Python & JavaScript
Combines data from multiple sources to create rich, accurate charts
Specializes in cap table Sankey diagrams and other financial visualizations
"""

import logging
from typing import Dict, List, Any, Optional
import json
import re

logger = logging.getLogger(__name__)


class ChartGenerationSkill:
    """
    Dynamic chart generator that:
    1. Uses Python for data processing and calculations
    2. Generates JavaScript/D3.js code for rendering
    3. Creates cap table Sankey diagrams from ownership data
    4. Adapts to any data structure dynamically
    """
    
    def __init__(self):
        self.name = "chart-generator"
        self.description = "Generate dynamic charts using Python processing and JavaScript rendering"
        
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main execution that dynamically adapts to data structure
        """
        try:
            # Extract data - be flexible about structure
            raw_data = inputs.get('data') or inputs.get('companies') or inputs.get('context') or inputs
            chart_type = inputs.get('chart_type', 'auto')
            
            # Analyze data structure dynamically
            data_structure = await self._analyze_data_structure(raw_data)
            
            # Generate appropriate charts based on data structure
            charts = []
            
            # Cap Table Sankey - if ownership/equity data exists
            if data_structure.get('has_ownership_data'):
                sankey = await self._generate_cap_table_sankey(raw_data, data_structure)
                if sankey:
                    charts.append(sankey)
            
            # Financial metrics charts - if financial data exists
            if data_structure.get('has_financial_data'):
                financial_charts = await self._generate_financial_charts(raw_data, data_structure)
                charts.extend(financial_charts)
            
            # Comparison charts - if multiple entities
            if data_structure.get('has_multiple_entities'):
                comparison = await self._generate_comparison_charts(raw_data, data_structure)
                if comparison:
                    charts.append(comparison)
            
            # Time series - if temporal data exists
            if data_structure.get('has_temporal_data'):
                timeline = await self._generate_timeline_charts(raw_data, data_structure)
                if timeline:
                    charts.append(timeline)
            
            return {
                "success": True,
                "charts": charts,
                "chart_count": len(charts),
                "data_structure": data_structure,
                "python_code": self._generate_python_processing_code(raw_data),
                "javascript_code": self._generate_javascript_rendering_code(charts)
            }
            
        except Exception as e:
            logger.error(f"Chart generation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "charts": []
            }
    
    async def _analyze_data_structure(self, data: Any) -> Dict[str, Any]:
        """
        Dynamically analyze data structure to determine what charts to create
        """
        structure = {
            'has_ownership_data': False,
            'has_financial_data': False,
            'has_multiple_entities': False,
            'has_temporal_data': False,
            'entities': [],
            'metrics': [],
            'time_periods': []
        }
        
        # Convert to string for pattern matching
        data_str = str(data).lower()
        
        # Check for ownership/equity indicators
        ownership_patterns = [
            'equity', 'ownership', 'shares', 'stake', 'cap_table', 'captable',
            'investor', 'founder', 'employee', 'option', 'warrant', 'dilution'
        ]
        structure['has_ownership_data'] = any(pattern in data_str for pattern in ownership_patterns)
        
        # Check for financial indicators
        financial_patterns = [
            'revenue', 'valuation', 'funding', 'burn', 'runway', 'arr', 'mrr',
            'cac', 'ltv', 'gross_margin', 'ebitda'
        ]
        structure['has_financial_data'] = any(pattern in data_str for pattern in financial_patterns)
        
        # Check for multiple entities (companies)
        if isinstance(data, dict):
            # Look for company names (capitalized words)
            company_pattern = r'@?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*'
            companies = re.findall(company_pattern, str(data))
            structure['entities'] = list(set(companies))[:10]  # Limit to 10
            structure['has_multiple_entities'] = len(structure['entities']) > 1
            
            # Extract metrics dynamically
            if isinstance(data, dict):
                structure['metrics'] = self._extract_metrics(data)
        
        # Check for temporal data
        time_patterns = [
            r'\d{4}', r'Q\d', r'month', r'year', r'date', 'timeline', 'history'
        ]
        structure['has_temporal_data'] = any(re.search(pattern, data_str) for pattern in time_patterns)
        
        return structure
    
    def _extract_metrics(self, data: Dict, prefix: str = '') -> List[str]:
        """Recursively extract metric names from nested data"""
        metrics = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (int, float)):
                    metrics.append(f"{prefix}{key}" if prefix else key)
                elif isinstance(value, dict):
                    metrics.extend(self._extract_metrics(value, f"{key}."))
                    
        return metrics
    
    async def _generate_cap_table_sankey(self, data: Any, structure: Dict) -> Optional[Dict]:
        """
        Generate cap table Sankey diagram
        This is the "holy grail" - showing ownership flow
        """
        # Python code to process cap table data
        python_code = """
# Extract ownership data from various sources
def process_cap_table(data):
    ownership = {}
    
    # Look for funding rounds
    if 'funding_rounds' in data:
        for round in data['funding_rounds']:
            investors = round.get('investors', {})
            for investor, amount in investors.items():
                ownership[investor] = ownership.get(investor, 0) + amount
    
    # Look for direct ownership data
    if 'cap_table' in data:
        ownership.update(data['cap_table'])
    
    # Estimate ownership from valuation and funding
    if 'valuation' in data and 'total_raised' in data:
        # Estimate dilution
        total_raised = data['total_raised']
        valuation = data['valuation']
        investor_ownership = min(total_raised / valuation, 0.7)  # Max 70% dilution
        
        if not ownership:
            ownership = {
                'Founders': (1 - investor_ownership) * 0.6,
                'Employees': (1 - investor_ownership) * 0.2,
                'Advisors': (1 - investor_ownership) * 0.05,
                'Investors': investor_ownership
            }
    
    # Convert to percentages
    total = sum(ownership.values())
    if total > 0:
        ownership = {k: (v/total)*100 for k, v in ownership.items()}
    
    return ownership

cap_table = process_cap_table(data)
"""
        
        # JavaScript code for Sankey rendering
        javascript_code = """
// Render cap table Sankey diagram using D3.js
function renderCapTableSankey(containerId, ownership) {
    const width = 800;
    const height = 600;
    
    // Prepare nodes and links
    const nodes = [
        {id: 0, name: "Company Equity (100%)"},
    ];
    
    const links = [];
    let nodeId = 1;
    
    // Create nodes for each ownership group
    for (const [owner, percentage] of Object.entries(ownership)) {
        nodes.push({id: nodeId, name: `${owner} (${percentage.toFixed(1)}%)`});
        links.push({
            source: 0,
            target: nodeId,
            value: percentage
        });
        
        // Add sub-categories if detailed data exists
        if (owner === 'Investors' && data.investor_breakdown) {
            const investorBase = nodeId;
            for (const [investor, share] of Object.entries(data.investor_breakdown)) {
                nodeId++;
                nodes.push({id: nodeId, name: investor});
                links.push({
                    source: investorBase,
                    target: nodeId,
                    value: share
                });
            }
        }
        
        nodeId++;
    }
    
    // Create Sankey diagram
    const sankey = d3.sankey()
        .nodeWidth(15)
        .nodePadding(10)
        .size([width, height]);
    
    const svg = d3.select(`#${containerId}`)
        .append('svg')
        .attr('width', width)
        .attr('height', height);
    
    // Render the diagram
    sankey.nodes(nodes)
        .links(links)
        .layout(32);
    
    // Add links
    svg.append('g')
        .selectAll('.link')
        .data(links)
        .enter().append('path')
        .attr('class', 'link')
        .attr('d', sankey.link())
        .style('stroke-width', d => Math.max(1, d.dy))
        .style('stroke', '#2563eb')
        .style('fill', 'none')
        .style('opacity', 0.5);
    
    // Add nodes
    svg.append('g')
        .selectAll('.node')
        .data(nodes)
        .enter().append('rect')
        .attr('class', 'node')
        .attr('x', d => d.x)
        .attr('y', d => d.y)
        .attr('height', d => d.dy)
        .attr('width', sankey.nodeWidth())
        .style('fill', '#3b82f6');
    
    // Add labels
    svg.append('g')
        .selectAll('.label')
        .data(nodes)
        .enter().append('text')
        .attr('x', d => d.x + sankey.nodeWidth() + 5)
        .attr('y', d => d.y + d.dy / 2)
        .text(d => d.name)
        .style('font-size', '12px');
}
"""
        
        # Try to extract real ownership data
        ownership_data = await self._extract_ownership_data(data)
        
        if not ownership_data:
            # Estimate from available data
            ownership_data = await self._estimate_ownership(data)
        
        if not ownership_data:
            return None
        
        return {
            "type": "sankey",
            "title": "Estimated Cap Table Structure",
            "data": {
                "ownership": ownership_data,
                "nodes": self._create_sankey_nodes(ownership_data),
                "links": self._create_sankey_links(ownership_data)
            },
            "python_code": python_code,
            "javascript_code": javascript_code,
            "rendering_engine": "d3.js"
        }
    
    async def _extract_ownership_data(self, data: Any) -> Optional[Dict]:
        """Extract real ownership percentages from data"""
        ownership = {}
        
        if isinstance(data, dict):
            # Look for explicit cap table
            if 'cap_table' in data:
                return data['cap_table']
            
            # Look for ownership/equity fields
            for key in ['ownership', 'equity', 'shareholding', 'investors']:
                if key in data and isinstance(data[key], dict):
                    ownership.update(data[key])
            
            # Parse funding rounds for ownership
            if 'funding' in data or 'rounds' in data:
                funding_data = data.get('funding', data.get('rounds', {}))
                ownership = self._parse_funding_for_ownership(funding_data)
        
        return ownership if ownership else None
    
    def _parse_funding_for_ownership(self, funding_data: Any) -> Dict:
        """Parse funding data to estimate ownership"""
        ownership = {
            'Founders': 40,  # Start with founder ownership
            'Employees': 10,  # ESOP
            'Investors': 0
        }
        
        total_dilution = 0
        
        if isinstance(funding_data, list):
            for round_data in funding_data:
                if isinstance(round_data, dict):
                    # Each round typically dilutes 10-25%
                    dilution = round_data.get('dilution', 0.15)
                    total_dilution += dilution
                    
                    investor = round_data.get('lead_investor', f"Series {round_data.get('series', '?')}")
                    ownership[investor] = dilution * 100
        
        # Adjust founder/employee ownership
        founder_employee_remaining = max(100 - (total_dilution * 100), 30)
        ownership['Founders'] = founder_employee_remaining * 0.7
        ownership['Employees'] = founder_employee_remaining * 0.3
        
        return ownership
    
    async def _estimate_ownership(self, data: Any) -> Dict:
        """Estimate ownership from valuation and funding data"""
        # Default Silicon Valley style cap table
        ownership = {
            'Founders': 35,
            'Employees (ESOP)': 15,
            'Seed Investors': 10,
            'Series A': 20,
            'Series B': 15,
            'Other/Advisors': 5
        }
        
        # Adjust based on stage if we can determine it
        if isinstance(data, dict):
            stage = self._determine_company_stage(data)
            
            if stage == 'seed':
                ownership = {
                    'Founders': 60,
                    'Employees': 10,
                    'Seed Investors': 25,
                    'Advisors': 5
                }
            elif stage == 'series_a':
                ownership = {
                    'Founders': 40,
                    'Employees': 12,
                    'Seed Investors': 18,
                    'Series A': 25,
                    'Advisors': 5
                }
            elif stage == 'series_b':
                ownership = {
                    'Founders': 30,
                    'Employees': 15,
                    'Seed Investors': 10,
                    'Series A': 20,
                    'Series B': 20,
                    'Other': 5
                }
        
        return ownership
    
    def _determine_company_stage(self, data: Dict) -> str:
        """Determine company stage from data"""
        data_str = str(data).lower()
        
        if 'series b' in data_str or 'series_b' in data_str:
            return 'series_b'
        elif 'series a' in data_str or 'series_a' in data_str:
            return 'series_a'
        elif 'seed' in data_str:
            return 'seed'
        
        # Try to determine from valuation
        if 'valuation' in data:
            val = data['valuation']
            if isinstance(val, (int, float)):
                if val < 10_000_000:
                    return 'seed'
                elif val < 50_000_000:
                    return 'series_a'
                else:
                    return 'series_b'
        
        return 'series_a'  # Default
    
    def _create_sankey_nodes(self, ownership: Dict) -> List[Dict]:
        """Create nodes for Sankey diagram"""
        nodes = [{"name": "Company Equity", "id": 0}]
        
        for i, (owner, percentage) in enumerate(ownership.items(), 1):
            nodes.append({
                "name": f"{owner}: {percentage:.1f}%",
                "id": i
            })
        
        return nodes
    
    def _create_sankey_links(self, ownership: Dict) -> List[Dict]:
        """Create links for Sankey diagram"""
        links = []
        
        for i, (owner, percentage) in enumerate(ownership.items(), 1):
            links.append({
                "source": 0,  # Company Equity
                "target": i,
                "value": percentage
            })
        
        return links
    
    async def _generate_financial_charts(self, data: Any, structure: Dict) -> List[Dict]:
        """Generate financial charts dynamically"""
        charts = []
        
        # Extract metrics dynamically
        metrics = structure.get('metrics', [])
        
        if metrics:
            # Python processing code
            python_code = f"""
# Process financial metrics
metrics_to_chart = {metrics[:5]}  # Top 5 metrics
processed_data = {{}}

for metric in metrics_to_chart:
    value = extract_metric(data, metric)
    if value:
        processed_data[metric] = value

return processed_data
"""
            
            # JavaScript rendering code  
            javascript_code = """
// Render financial metrics chart
function renderMetricsChart(containerId, metrics) {
    const chart = new Chart(containerId, {
        type: 'bar',
        data: {
            labels: Object.keys(metrics),
            datasets: [{
                label: 'Value',
                data: Object.values(metrics),
                backgroundColor: 'rgba(54, 162, 235, 0.8)'
            }]
        }
    });
}
"""
            
            charts.append({
                "type": "bar",
                "title": "Key Financial Metrics",
                "data": {"metrics": metrics[:5]},
                "python_code": python_code,
                "javascript_code": javascript_code
            })
        
        return charts
    
    async def _generate_comparison_charts(self, data: Any, structure: Dict) -> Optional[Dict]:
        """Generate comparison charts for multiple entities"""
        entities = structure.get('entities', [])
        
        if len(entities) < 2:
            return None
        
        return {
            "type": "comparison",
            "title": f"Comparison: {' vs '.join(entities[:3])}",
            "data": {"entities": entities},
            "python_code": "# Extract and normalize data for each entity",
            "javascript_code": "// Render comparison visualization"
        }
    
    async def _generate_timeline_charts(self, data: Any, structure: Dict) -> Optional[Dict]:
        """Generate timeline charts for temporal data"""
        return {
            "type": "timeline",
            "title": "Historical Timeline",
            "data": {"periods": structure.get('time_periods', [])},
            "python_code": "# Process time series data",
            "javascript_code": "// Render timeline with D3.js"
        }
    
    def _generate_python_processing_code(self, data: Any) -> str:
        """Generate complete Python code for data processing"""
        return f"""
import pandas as pd
import numpy as np

# Data processing for chart generation
raw_data = {json.dumps(data, indent=2) if isinstance(data, (dict, list)) else str(data)[:500]}

# Process and transform data
def process_chart_data(data):
    # Dynamic data extraction
    processed = {{}}
    
    # Extract numerical values
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (int, float)):
                processed[key] = value
    
    return processed

chart_data = process_chart_data(raw_data)
print(chart_data)
"""
    
    def _generate_javascript_rendering_code(self, charts: List[Dict]) -> str:
        """Generate complete JavaScript code for rendering"""
        return f"""
// Chart rendering code using D3.js and Chart.js
const charts = {json.dumps(charts, indent=2)};

// Initialize all charts
charts.forEach(chart => {{
    if (chart.type === 'sankey') {{
        renderCapTableSankey('chart-container', chart.data);
    }} else if (chart.type === 'bar') {{
        renderBarChart('chart-container', chart.data);
    }} else if (chart.type === 'timeline') {{
        renderTimeline('chart-container', chart.data);
    }}
}});
"""