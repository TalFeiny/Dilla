"""
Chart Renderer Service - Server-side rendering of complex charts
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import tempfile
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright
import httpx

logger = logging.getLogger(__name__)

class ChartRendererService:
    """Renders TableauLevelCharts to PNG images server-side using Playwright"""
    
    def __init__(self):
        self.cache_dir = "/tmp/chart_cache"
        os.makedirs(self.cache_dir, exist_ok=True)
        self._playwright_available = True
        self._playwright_warning_sent = False
        
        # Chart types that need server-side rendering
        self.COMPLEX_CHART_TYPES = {
            'sankey',
            'side_by_side_sankey', 
            'sunburst',
            'waterfall',
            'heatmap',
            'bubble',
            'radialBar',
            'probability_cloud'
        }
    
    def _get_cache_key(self, chart_type: str, chart_data: Dict[str, Any]) -> str:
        """Generate cache key based on chart type and data"""
        data_str = json.dumps(chart_data, sort_keys=True)
        return hashlib.md5(f"{chart_type}:{data_str}".encode()).hexdigest()
    
    def _get_cached_image(self, cache_key: str) -> Optional[str]:
        """Check if chart is already cached"""
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.png")
        if os.path.exists(cache_file):
            with open(cache_file, 'rb') as f:
                img_data = f.read()
                return base64.b64encode(img_data).decode()
        return None
    
    def _cache_image(self, cache_key: str, img_data: bytes):
        """Cache rendered image"""
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.png")
        with open(cache_file, 'wb') as f:
            f.write(img_data)
    
    def _create_chart_html(self, chart_type: str, chart_data: Dict[str, Any], width: int = 800, height: int = 400) -> str:
        """Create standalone HTML page with TableauLevelCharts component"""
        
        # Escape chart data for JavaScript
        chart_data_json = json.dumps(chart_data).replace('</script>', '<\\/script>')
        
        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chart Renderer</title>
    <style>
        body {{
            margin: 0;
            padding: 20px;
            background: white;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }}
        .chart-container {{
            width: {width}px;
            height: {height}px;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            overflow: hidden;
        }}
        #chart-root {{
            width: 100%;
            height: 100%;
        }}
    </style>
</head>
<body>
    <div class="chart-container">
        <div id="chart-root"></div>
    </div>
    
    <!-- React and dependencies -->
    <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    
    <!-- D3 for complex charts -->
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <script src="https://unpkg.com/d3-sankey@0.12.3/dist/d3-sankey.min.js"></script>
    
    <!-- Recharts for some chart types -->
    <script src="https://unpkg.com/recharts@2.8.0/umd/Recharts.js"></script>
    
    <script>
        // Chart data
        const chartType = '{chart_type}';
        const chartData = {chart_data_json};
        
        // TableauLevelCharts component implementation
        const TableauLevelCharts = React.createElement('div', {{
            id: 'tableau-chart',
            style: {{
                width: '100%',
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
            }}
        }}, React.createElement('div', {{
            style: {{
                padding: '20px',
                textAlign: 'center',
                color: '#666'
            }}
        }}, `Rendering ${{chartType}} chart...`));
        
        // Render chart
        ReactDOM.render(TableauLevelCharts, document.getElementById('chart-root'));
        
        // Custom chart rendering based on type
        function renderChart() {{
            const container = document.getElementById('chart-root');
            
            switch(chartType) {{
                case 'sankey':
                    renderSankeyChart(container, chartData);
                    break;
                case 'side_by_side_sankey':
                    renderSideBySideSankey(container, chartData);
                    break;
                case 'sunburst':
                    renderSunburstChart(container, chartData);
                    break;
                case 'waterfall':
                    renderWaterfallChart(container, chartData);
                    break;
                case 'heatmap':
                    renderHeatmapChart(container, chartData);
                    break;
                case 'bubble':
                    renderBubbleChart(container, chartData);
                    break;
                case 'radialBar':
                    renderRadialBarChart(container, chartData);
                    break;
                case 'probability_cloud':
                    renderProbabilityCloudChart(container, chartData);
                    break;
                default:
                    container.innerHTML = `<div style="padding: 20px; text-align: center; color: #666;">Unsupported chart type: ${{chartType}}</div>`;
            }}
        }}
        
        // Sankey chart renderer
        function renderSankeyChart(container, data) {{
            const width = {width};
            const height = {height};
            
            const svg = d3.select(container)
                .append('svg')
                .attr('width', width)
                .attr('height', height)
                .attr('viewBox', `0 0 ${{width}} ${{height}}`);
            
            const sankey = d3.sankey()
                .nodeWidth(15)
                .nodePadding(10)
                .extent([[1, 1], [width - 1, height - 6]]);
            
            const {{nodes, links}} = sankey({{
                nodes: data.nodes || data.data?.nodes || [],
                links: data.links || data.data?.links || []
            }});
            
            const color = d3.scaleOrdinal(d3.schemeCategory10);
            
            // Links
            svg.append('g')
                .selectAll('path')
                .data(links)
                .join('path')
                .attr('d', d3.sankeyLinkHorizontal())
                .attr('fill', 'none')
                .attr('stroke', d => color(d.source.name))
                .attr('stroke-width', d => Math.max(1, d.width))
                .attr('opacity', 0.6);
            
            // Nodes
            svg.append('g')
                .selectAll('rect')
                .data(nodes)
                .join('rect')
                .attr('x', d => d.x0)
                .attr('y', d => d.y0)
                .attr('width', d => d.x1 - d.x0)
                .attr('height', d => d.y1 - d.y0)
                .attr('fill', d => color(d.name))
                .attr('opacity', 0.8)
                .attr('stroke', '#fff')
                .attr('stroke-width', 1);
            
            // Node labels
            svg.append('g')
                .selectAll('text')
                .data(nodes)
                .join('text')
                .attr('x', d => (d.x0 + d.x1) / 2)
                .attr('y', d => (d.y0 + d.y1) / 2)
                .attr('dy', '0.35em')
                .attr('text-anchor', 'middle')
                .attr('font-size', '12px')
                .attr('fill', '#fff')
                .attr('font-weight', '600')
                .text(d => d.name);
        }}
        
        // Side-by-side Sankey renderer
        function renderSideBySideSankey(container, data) {{
            const width = {width};
            const height = {height};
            
            container.innerHTML = `
                <div style="display: flex; width: 100%; height: 100%; gap: 20px;">
                    <div style="flex: 1;">
                        <h4 style="text-align: center; margin-bottom: 10px;">${{data.company1_name || 'Company 1'}}</h4>
                        <div id="sankey1" style="width: 100%; height: calc(100% - 30px);"></div>
                    </div>
                    <div style="flex: 1;">
                        <h4 style="text-align: center; margin-bottom: 10px;">${{data.company2_name || 'Company 2'}}</h4>
                        <div id="sankey2" style="width: 100%; height: calc(100% - 30px);"></div>
                    </div>
                </div>
            `;
            
            if (data.company1_data) {{
                renderSankeyChart(document.getElementById('sankey1'), data.company1_data);
            }}
            if (data.company2_data) {{
                renderSankeyChart(document.getElementById('sankey2'), data.company2_data);
            }}
        }}
        
        // Sunburst chart renderer
        function renderSunburstChart(container, data) {{
            const width = {width};
            const height = {height};
            const radius = Math.min(width, height) / 2;
            
            const svg = d3.select(container)
                .append('svg')
                .attr('width', width)
                .attr('height', height)
                .attr('viewBox', `-${{radius}} -${{radius}} ${{width}} ${{height}}`);
            
            const partition = d3.partition().size([2 * Math.PI, radius]);
            const root = d3.hierarchy(data).sum(d => d.value).sort((a, b) => b.value - a.value);
            partition(root);
            
            const color = d3.scaleOrdinal(d3.schemeCategory10);
            const arc = d3.arc()
                .startAngle(d => d.x0)
                .endAngle(d => d.x1)
                .innerRadius(d => d.y0)
                .outerRadius(d => d.y1);
            
            svg.append('g')
                .selectAll('path')
                .data(root.descendants())
                .join('path')
                .attr('d', arc)
                .attr('fill', d => color(d.depth))
                .attr('opacity', 0.8)
                .attr('stroke', '#fff')
                .attr('stroke-width', 2);
            
            svg.append('g')
                .selectAll('text')
                .data(root.descendants().filter(d => d.depth === 1))
                .join('text')
                .attr('transform', d => `translate(${{arc.centroid(d)}})`)
                .attr('text-anchor', 'middle')
                .attr('font-size', '10px')
                .attr('fill', 'white')
                .attr('font-weight', 'bold')
                .text(d => d.data.name);
        }}
        
        // Waterfall chart renderer
        function renderWaterfallChart(container, data) {{
            const width = {width};
            const height = {height};
            const margin = {{top: 20, right: 30, bottom: 40, left: 40}};
            
            const svg = d3.select(container)
                .append('svg')
                .attr('width', width)
                .attr('height', height);
            
            const chartWidth = width - margin.left - margin.right;
            const chartHeight = height - margin.top - margin.bottom;
            
            const g = svg.append('g')
                .attr('transform', `translate(${{margin.left}},${{margin.top}})`);
            
            const xScale = d3.scaleBand()
                .domain(data.map(d => d.name))
                .range([0, chartWidth])
                .padding(0.1);
            
            const yScale = d3.scaleLinear()
                .domain([0, d3.max(data, d => d.value)])
                .range([chartHeight, 0]);
            
            // Bars
            g.selectAll('rect')
                .data(data)
                .join('rect')
                .attr('x', d => xScale(d.name))
                .attr('y', d => yScale(Math.abs(d.value)))
                .attr('width', xScale.bandwidth())
                .attr('height', d => chartHeight - yScale(Math.abs(d.value)))
                .attr('fill', d => d.value >= 0 ? '#10b981' : '#ef4444')
                .attr('opacity', 0.8);
            
            // X axis
            g.append('g')
                .attr('transform', `translate(0,${{chartHeight}})`)
                .call(d3.axisBottom(xScale))
                .selectAll('text')
                .attr('transform', 'rotate(-45)')
                .style('text-anchor', 'end');
            
            // Y axis
            g.append('g')
                .call(d3.axisLeft(yScale));
        }}
        
        // Heatmap chart renderer
        function renderHeatmapChart(container, data) {{
            const width = {width};
            const height = {height};
            const margin = {{top: 20, right: 20, bottom: 20, left: 20}};
            
            const svg = d3.select(container)
                .append('svg')
                .attr('width', width)
                .attr('height', height);
            
            const chartWidth = width - margin.left - margin.right;
            const chartHeight = height - margin.top - margin.bottom;
            
            const g = svg.append('g')
                .attr('transform', `translate(${{margin.left}},${{margin.top}})`);
            
            const xLabels = [...new Set(data.map(d => d.x))];
            const yLabels = [...new Set(data.map(d => d.y))];
            const maxValue = d3.max(data, d => d.value);
            
            const xScale = d3.scaleBand()
                .domain(xLabels)
                .range([0, chartWidth])
                .padding(0.05);
            
            const yScale = d3.scaleBand()
                .domain(yLabels)
                .range([0, chartHeight])
                .padding(0.05);
            
            const colorScale = d3.scaleSequential()
                .interpolator(d3.interpolateRdYlBu)
                .domain([maxValue, 0]);
            
            g.selectAll('rect')
                .data(data)
                .join('rect')
                .attr('x', d => xScale(d.x))
                .attr('y', d => yScale(d.y))
                .attr('width', xScale.bandwidth())
                .attr('height', yScale.bandwidth())
                .attr('fill', d => colorScale(d.value))
                .attr('stroke', '#fff')
                .attr('stroke-width', 1);
            
            // X axis labels
            g.append('g')
                .attr('transform', `translate(0,${{chartHeight}})`)
                .call(d3.axisBottom(xScale));
            
            // Y axis labels
            g.append('g')
                .call(d3.axisLeft(yScale));
        }}
        
        // Bubble chart renderer
        function renderBubbleChart(container, data) {{
            const width = {width};
            const height = {height};
            const margin = {{top: 20, right: 20, bottom: 40, left: 40}};
            
            const svg = d3.select(container)
                .append('svg')
                .attr('width', width)
                .attr('height', height);
            
            const chartWidth = width - margin.left - margin.right;
            const chartHeight = height - margin.top - margin.bottom;
            
            const g = svg.append('g')
                .attr('transform', `translate(${{margin.left}},${{margin.top}})`);
            
            const xScale = d3.scaleLinear()
                .domain(d3.extent(data, d => d.x))
                .range([0, chartWidth]);
            
            const yScale = d3.scaleLinear()
                .domain(d3.extent(data, d => d.y))
                .range([chartHeight, 0]);
            
            const rScale = d3.scaleSqrt()
                .domain(d3.extent(data, d => d.z))
                .range([5, 30]);
            
            const color = d3.scaleOrdinal(d3.schemeCategory10);
            
            g.selectAll('circle')
                .data(data)
                .join('circle')
                .attr('cx', d => xScale(d.x))
                .attr('cy', d => yScale(d.y))
                .attr('r', d => rScale(d.z))
                .attr('fill', d => color(d.category || 0))
                .attr('opacity', 0.6)
                .attr('stroke', d => color(d.category || 0))
                .attr('stroke-width', 2);
            
            // X axis
            g.append('g')
                .attr('transform', `translate(0,${{chartHeight}})`)
                .call(d3.axisBottom(xScale));
            
            // Y axis
            g.append('g')
                .call(d3.axisLeft(yScale));
        }}
        
        // Radial bar chart renderer
        function renderRadialBarChart(container, data) {{
            const width = {width};
            const height = {height};
            const radius = Math.min(width, height) / 2 - 20;
            
            const svg = d3.select(container)
                .append('svg')
                .attr('width', width)
                .attr('height', height)
                .attr('viewBox', `-${{width/2}} -${{height/2}} ${{width}} ${{height}}`);
            
            const g = svg.append('g');
            
            const color = d3.scaleOrdinal(d3.schemeCategory10);
            const pie = d3.pie()
                .value(d => d.value)
                .sort(null);
            
            const arc = d3.arc()
                .innerRadius(radius * 0.3)
                .outerRadius(radius);
            
            g.selectAll('path')
                .data(pie(data))
                .join('path')
                .attr('d', arc)
                .attr('fill', (d, i) => color(i))
                .attr('opacity', 0.8)
                .attr('stroke', '#fff')
                .attr('stroke-width', 2);
            
            g.selectAll('text')
                .data(pie(data))
                .join('text')
                .attr('transform', d => `translate(${{arc.centroid(d)}})`)
                .attr('text-anchor', 'middle')
                .attr('font-size', '12px')
                .attr('fill', 'white')
                .attr('font-weight', 'bold')
                .text(d => d.data.name);
        }}
        
        // Probability cloud chart renderer
        function renderProbabilityCloudChart(container, data) {{
            const width = {width};
            const height = {height};
            const margin = {{top: 40, right: 120, bottom: 60, left: 80}};
            const chartWidth = width - margin.left - margin.right;
            const chartHeight = height - margin.top - margin.bottom;
            
            const svg = d3.select(container)
                .append('svg')
                .attr('width', width)
                .attr('height', height);
            
            const g = svg.append('g')
                .attr('transform', `translate(${{margin.left}},${{margin.top}})`);
            
            const xScale = d3.scaleLog()
                .domain([10000000, 10000000000])
                .range([0, chartWidth]);
            
            const yScale = d3.scaleLinear()
                .domain([0, 50])
                .range([chartHeight, 0]);
            
            // Grid lines
            g.append('g')
                .attr('class', 'grid')
                .attr('transform', `translate(0,${{chartHeight}})`)
                .call(d3.axisBottom(xScale).tickSize(-chartHeight).tickFormat(''));
            
            g.append('g')
                .attr('class', 'grid')
                .call(d3.axisLeft(yScale).tickSize(-chartWidth).tickFormat(''));
            
            // Scenario curves
            if (data.scenario_curves) {{
                data.scenario_curves.forEach((scenario, i) => {{
                    if (scenario.return_curve?.exit_values) {{
                        const lineData = scenario.return_curve.exit_values.map((exitVal, j) => ({{
                            x: exitVal,
                            y: scenario.return_curve.return_multiples[j]
                        }}));
                        
                        const line = d3.line()
                            .x(d => xScale(d.x))
                            .y(d => yScale(d.y))
                            .curve(d3.curveMonotoneX);
                        
                        g.append('path')
                            .datum(lineData)
                            .attr('d', line)
                            .attr('fill', 'none')
                            .attr('stroke', scenario.color || d3.schemeCategory10[i])
                            .attr('stroke-width', 2)
                            .attr('opacity', 0.7);
                    }}
                }});
            }}
            
            // Axes
            g.append('g')
                .attr('transform', `translate(0,${{chartHeight}})`)
                .call(d3.axisBottom(xScale));
            
            g.append('g')
                .call(d3.axisLeft(yScale));
        }}
        
        // Start rendering after a short delay to ensure DOM is ready
        setTimeout(renderChart, 100);
    </script>
</body>
</html>
        """
        
        return html_template
    
    async def render_tableau_chart(self, chart_type: str, chart_data: Dict[str, Any], width: int = 800, height: int = 400) -> str:
        """
        Render a TableauLevelChart to PNG image
        
        Args:
            chart_type: Type of chart (sankey, waterfall, etc.)
            chart_data: Chart data
            width: Image width
            height: Image height
            
        Returns:
            Base64-encoded PNG image
        """
        
        if chart_type not in self.COMPLEX_CHART_TYPES:
            logger.warning(f"Chart type {chart_type} not in complex chart types, skipping pre-rendering")
            return None
        
        if not self._playwright_available:
            if not self._playwright_warning_sent:
                logger.warning(
                    "Playwright browsers missing. Skipping complex chart rendering until `playwright install` is run."
                )
                self._playwright_warning_sent = True
            return None
        
        # Check cache first
        cache_key = self._get_cache_key(chart_type, chart_data)
        cached_image = self._get_cached_image(cache_key)
        if cached_image:
            logger.info(f"Using cached chart for {chart_type}")
            return cached_image
        
        logger.info(f"Rendering {chart_type} chart server-side")
        
        try:
            # Create HTML content
            html_content = self._create_chart_html(chart_type, chart_data, width, height)
            
            # Write to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
                f.write(html_content)
                temp_html_path = f.name
            
            # Use Playwright to render
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # Set viewport for high-DPI rendering (2x resolution)
                await page.set_viewport_size({"width": (width + 40) * 2, "height": (height + 40) * 2})
                
                # Load HTML file
                await page.goto(f"file://{temp_html_path}")
                
                # Wait for chart to render
                await page.wait_for_timeout(2000)  # Wait for D3 rendering
                
                # Take screenshot of chart container
                chart_element = await page.query_selector('.chart-container')
                if chart_element:
                    screenshot_bytes = await chart_element.screenshot(type='png')
                    
                    # Cache the image
                    self._cache_image(cache_key, screenshot_bytes)
                    
                    # Convert to base64
                    base64_image = base64.b64encode(screenshot_bytes).decode()
                    
                    await browser.close()
                    
                    # Clean up temp file
                    os.unlink(temp_html_path)
                    
                    logger.info(f"Successfully rendered {chart_type} chart")
                    return base64_image
                else:
                    logger.error(f"Could not find chart container for {chart_type}")
                    await browser.close()
                    os.unlink(temp_html_path)
                    return None
                    
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error rendering {chart_type} chart: {error_msg}")
            missing_browser_indicators = [
                "Executable doesn't exist",
                "playwright install",
                "browserType.launch: Failed to launch"
            ]
            if any(indicator.lower() in error_msg.lower() for indicator in missing_browser_indicators):
                self._playwright_available = False
                if not self._playwright_warning_sent:
                    logger.warning(
                        "Playwright chromium browser binary is missing. Run `playwright install` to enable chart prerendering."
                    )
                    self._playwright_warning_sent = True
            return None
    
    def should_prerender_chart(self, chart_type: str) -> bool:
        """Check if chart type should be pre-rendered"""
        return chart_type in self.COMPLEX_CHART_TYPES

# Global instance
chart_renderer = ChartRendererService()
