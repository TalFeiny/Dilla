"""
Chart Renderer Service - Server-side rendering of complex charts via Plotly + Kaleido.

Drop-in replacement for the Playwright-based renderer. Same interface,
same cache, same base64 PNG output — but ~10x faster and ~8x smaller footprint.
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from app.services.dilla_chart_theme import (
    ACCENT_CYAN,
    BASE_COLOR,
    BEAR_COLOR,
    BULL_COLOR,
    GRID_COLOR,
    NEGATIVE_COLOR,
    PAPER_COLOR,
    POSITIVE_COLOR,
    SUBTOTAL_COLOR,
    TABLEAU10,
    TEXT_COLOR,
    TEXT_SECONDARY,
    apply_dilla_theme,
    hex_to_rgba,
)

logger = logging.getLogger(__name__)


class ChartRendererService:
    """Renders complex charts to PNG images server-side using Plotly + Kaleido."""

    def __init__(self):
        self.cache_dir = "/tmp/chart_cache"
        os.makedirs(self.cache_dir, exist_ok=True)
        self._kaleido_available = True
        self._kaleido_warning_sent = False

        # Chart types that support server-side rendering
        self.COMPLEX_CHART_TYPES = {
            # Original 8
            "sankey",
            "side_by_side_sankey",
            "sunburst",
            "waterfall",
            "heatmap",
            "bubble",
            "radialBar",
            "probability_cloud",
            # FP&A additions
            "sensitivity_tornado",
            "tornado",
            "treemap",
            "monte_carlo_histogram",
            "monte_carlo_fan",
            "stacked_bar",
            "fpa_stress_test",
            "bull_bear_base",
            "funnel",
            "cash_flow_waterfall",
            "revenue_forecast",
            "bar_comparison",
            "cap_table_evolution",
        }

        self._BUILDERS = {
            "sankey": self._build_sankey,
            "side_by_side_sankey": self._build_side_by_side_sankey,
            "sunburst": self._build_sunburst,
            "waterfall": self._build_waterfall,
            "heatmap": self._build_heatmap,
            "bubble": self._build_bubble,
            "radialBar": self._build_radial_bar,
            "probability_cloud": self._build_probability_cloud,
            "sensitivity_tornado": self._build_tornado,
            "tornado": self._build_tornado,
            "treemap": self._build_treemap,
            "monte_carlo_histogram": self._build_monte_carlo_histogram,
            "monte_carlo_fan": self._build_monte_carlo_fan,
            "stacked_bar": self._build_stacked_bar,
            "fpa_stress_test": self._build_fpa_stress_test,
            "bull_bear_base": self._build_bull_bear_base,
            "funnel": self._build_funnel,
            "cash_flow_waterfall": self._build_cash_flow_waterfall,
            "revenue_forecast": self._build_revenue_forecast,
            "bar_comparison": self._build_bar_comparison,
            "cap_table_evolution": self._build_cap_table_evolution,
        }

    # ------------------------------------------------------------------
    # Cache helpers (identical to previous implementation)
    # ------------------------------------------------------------------

    def _get_cache_key(self, chart_type: str, chart_data: Dict[str, Any]) -> str:
        data_str = json.dumps(chart_data, sort_keys=True, default=str)
        return hashlib.md5(f"{chart_type}:{data_str}".encode()).hexdigest()

    def _get_cached_image(self, cache_key: str) -> Optional[str]:
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.png")
        if os.path.exists(cache_file):
            with open(cache_file, "rb") as f:
                return base64.b64encode(f.read()).decode()
        return None

    def _cache_image(self, cache_key: str, img_data: bytes):
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.png")
        with open(cache_file, "wb") as f:
            f.write(img_data)

    # ------------------------------------------------------------------
    # Public API (same signatures as Playwright version)
    # ------------------------------------------------------------------

    async def render_tableau_chart(
        self,
        chart_type: str,
        chart_data: Dict[str, Any],
        width: int = 800,
        height: int = 400,
    ) -> Optional[str]:
        """Render a chart to base64-encoded PNG.

        Returns base64 string or None on failure.
        """
        if chart_type not in self.COMPLEX_CHART_TYPES:
            logger.warning(f"Chart type {chart_type} not in complex chart types, skipping pre-rendering")
            return None

        if not self._kaleido_available:
            if not self._kaleido_warning_sent:
                logger.warning("Kaleido unavailable. pip install kaleido to enable chart rendering.")
                self._kaleido_warning_sent = True
            return None

        cache_key = self._get_cache_key(chart_type, chart_data)
        cached = self._get_cached_image(cache_key)
        if cached:
            logger.info(f"Using cached chart for {chart_type}")
            return cached

        logger.info(f"Rendering {chart_type} chart via Plotly")

        try:
            data = self._extract_inner_data(chart_data)
            builder = self._BUILDERS.get(chart_type)
            if not builder:
                logger.warning(f"No builder for chart type: {chart_type}")
                return None

            fig = builder(data, width, height)
            fig = apply_dilla_theme(fig)

            # Apply title from outer chart_data envelope if present
            title = chart_data.get("title") if isinstance(chart_data, dict) else None
            if title:
                fig.update_layout(title_text=title)

            # Kaleido export is synchronous — run in thread to keep async
            img_bytes = await asyncio.to_thread(
                fig.to_image, format="png", width=width, height=height, scale=2
            )

            self._cache_image(cache_key, img_bytes)
            logger.info(f"Successfully rendered {chart_type} chart")
            return base64.b64encode(img_bytes).decode()

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error rendering {chart_type} chart: {error_msg}")
            kaleido_indicators = ["kaleido", "orca", "chromium"]
            if any(ind.lower() in error_msg.lower() for ind in kaleido_indicators):
                self._kaleido_available = False
                if not self._kaleido_warning_sent:
                    logger.warning("Kaleido export engine unavailable. pip install kaleido")
                    self._kaleido_warning_sent = True
            return None

    def should_prerender_chart(self, chart_type: str) -> bool:
        return chart_type in self.COMPLEX_CHART_TYPES

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_inner_data(chart_data: Dict[str, Any]) -> Any:
        """Unwrap {type, data, title, renderType} → inner data payload."""
        if isinstance(chart_data, dict) and "data" in chart_data:
            return chart_data["data"]
        return chart_data

    @staticmethod
    def _flatten_hierarchy(
        node: Dict[str, Any], parent_id: str = ""
    ) -> Tuple[List[str], List[str], List[str], List[float]]:
        """Recursive DFS to flatten a tree into Plotly sunburst/treemap arrays."""
        ids, labels, parents, values = [], [], [], []
        node_id = node.get("name", "root")
        if parent_id:
            node_id = f"{parent_id}/{node_id}"

        ids.append(node_id)
        labels.append(node.get("name", ""))
        parents.append(parent_id)
        values.append(node.get("value", 0))

        for child in node.get("children", []):
            c_ids, c_labels, c_parents, c_values = ChartRendererService._flatten_hierarchy(child, node_id)
            ids.extend(c_ids)
            labels.extend(c_labels)
            parents.extend(c_parents)
            values.extend(c_values)

        return ids, labels, parents, values

    @staticmethod
    def _format_value(value: float) -> str:
        """Format number for chart labels: $1.2M, $500K, etc."""
        abs_val = abs(value)
        sign = "-" if value < 0 else ""
        if abs_val >= 1_000_000_000:
            return f"{sign}${abs_val / 1_000_000_000:.1f}B"
        if abs_val >= 1_000_000:
            return f"{sign}${abs_val / 1_000_000:.1f}M"
        if abs_val >= 1_000:
            return f"{sign}${abs_val / 1_000:.0f}K"
        return f"{sign}${abs_val:,.0f}"

    @staticmethod
    def _resolve_sankey_indices(nodes: list, links: list) -> Tuple[list, list]:
        """Ensure links use integer indices. Handles string-name references."""
        name_to_idx = {}
        for i, n in enumerate(nodes):
            name_to_idx[n.get("name", n.get("id", i))] = i
            name_to_idx[i] = i
            if "id" in n:
                name_to_idx[n["id"]] = i

        resolved_links = []
        for link in links:
            src = link.get("source")
            tgt = link.get("target")
            src_idx = name_to_idx.get(src, src)
            tgt_idx = name_to_idx.get(tgt, tgt)
            if isinstance(src_idx, int) and isinstance(tgt_idx, int):
                resolved_links.append({**link, "source": src_idx, "target": tgt_idx})
        return nodes, resolved_links

    # ------------------------------------------------------------------
    # Chart builders — one per chart type
    # ------------------------------------------------------------------

    def _build_sankey(self, data: Any, width: int, height: int) -> go.Figure:
        nodes = data.get("nodes", []) if isinstance(data, dict) else []
        links = data.get("links", []) if isinstance(data, dict) else []
        nodes, links = self._resolve_sankey_indices(nodes, links)

        node_colors = [TABLEAU10[i % len(TABLEAU10)] for i in range(len(nodes))]
        link_colors = [
            hex_to_rgba(node_colors[l["source"]] if l["source"] < len(node_colors) else TABLEAU10[0], 0.4)
            for l in links
        ]

        fig = go.Figure(
            go.Sankey(
                node=dict(
                    pad=20,
                    thickness=20,
                    line=dict(color=GRID_COLOR, width=0.5),
                    label=[n.get("name", f"Node {i}") for i, n in enumerate(nodes)],
                    color=node_colors,
                ),
                link=dict(
                    source=[l["source"] for l in links],
                    target=[l["target"] for l in links],
                    value=[l.get("value", 0) for l in links],
                    color=link_colors,
                ),
            )
        )
        return fig

    def _build_side_by_side_sankey(self, data: Any, width: int, height: int) -> go.Figure:
        c1_name = data.get("company1_name", "Company 1") if isinstance(data, dict) else "Company 1"
        c2_name = data.get("company2_name", "Company 2") if isinstance(data, dict) else "Company 2"
        c1_data = data.get("company1_data", {}) if isinstance(data, dict) else {}
        c2_data = data.get("company2_data", {}) if isinstance(data, dict) else {}

        fig = make_subplots(
            rows=1,
            cols=2,
            subplot_titles=[c1_name, c2_name],
            specs=[[{"type": "sankey"}, {"type": "sankey"}]],
        )

        for col, sdata in enumerate([c1_data, c2_data], 1):
            nodes = sdata.get("nodes", [])
            links = sdata.get("links", [])
            nodes, links = self._resolve_sankey_indices(nodes, links)
            node_colors = [TABLEAU10[i % len(TABLEAU10)] for i in range(len(nodes))]

            fig.add_trace(
                go.Sankey(
                    node=dict(
                        pad=15,
                        thickness=18,
                        line=dict(color=GRID_COLOR, width=0.5),
                        label=[n.get("name", "") for n in nodes],
                        color=node_colors,
                    ),
                    link=dict(
                        source=[l["source"] for l in links],
                        target=[l["target"] for l in links],
                        value=[l.get("value", 0) for l in links],
                        color=[hex_to_rgba(node_colors[l["source"]] if l["source"] < len(node_colors) else TABLEAU10[0], 0.4) for l in links],
                    ),
                ),
                row=1,
                col=col,
            )
        return fig

    def _build_sunburst(self, data: Any, width: int, height: int) -> go.Figure:
        if not isinstance(data, dict) or "name" not in data:
            return go.Figure()
        ids, labels, parents, values = self._flatten_hierarchy(data)
        colors = [TABLEAU10[i % len(TABLEAU10)] for i in range(len(ids))]
        fig = go.Figure(
            go.Sunburst(
                ids=ids,
                labels=labels,
                parents=parents,
                values=values,
                branchvalues="total",
                marker=dict(colors=colors, line=dict(width=2, color=PAPER_COLOR)),
                insidetextorientation="radial",
            )
        )
        return fig

    def _build_waterfall(self, data: Any, width: int, height: int) -> go.Figure:
        items = data.get("items", data) if isinstance(data, dict) else data
        if not isinstance(items, list):
            items = []

        names = [it.get("name", f"Item {i}") for i, it in enumerate(items)]
        vals = [it.get("value", 0) for it in items]

        # First and last are totals, rest relative
        measures = []
        for i, it in enumerate(items):
            if it.get("isSubtotal") or i == 0 or i == len(items) - 1:
                measures.append("total")
            else:
                measures.append("relative")

        fig = go.Figure(
            go.Waterfall(
                x=names,
                y=vals,
                measure=measures,
                connector=dict(line=dict(color=GRID_COLOR, width=1)),
                increasing=dict(marker_color=POSITIVE_COLOR),
                decreasing=dict(marker_color=NEGATIVE_COLOR),
                totals=dict(marker_color=SUBTOTAL_COLOR),
                textposition="outside",
                text=[self._format_value(v) for v in vals],
                textfont=dict(size=10, color=TEXT_SECONDARY),
            )
        )
        fig.update_layout(showlegend=False, waterfallgap=0.3)
        return fig

    def _build_heatmap(self, data: Any, width: int, height: int) -> go.Figure:
        if isinstance(data, dict) and "dimensions" in data:
            # {dimensions, companies, scores} format
            dimensions = data.get("dimensions", [])
            companies = data.get("companies", [])
            scores = data.get("scores", [])
            fig = go.Figure(
                go.Heatmap(
                    z=scores,
                    x=dimensions,
                    y=companies,
                    colorscale=[
                        [0, "#1a1a24"],
                        [0.25, "#2d4a6e"],
                        [0.5, "#4e79a7"],
                        [0.75, "#76b7b2"],
                        [1.0, "#22d3ee"],
                    ],
                    text=scores,
                    texttemplate="%{text:.1f}",
                    textfont=dict(size=11),
                    hovertemplate="Company: %{y}<br>Dimension: %{x}<br>Score: %{z:.2f}<extra></extra>",
                    colorbar=dict(
                        tickfont=dict(color=TEXT_SECONDARY),
                        title=dict(font=dict(color=TEXT_SECONDARY)),
                    ),
                )
            )
        elif isinstance(data, list):
            # [{x, y, value}] array format
            xs = list(dict.fromkeys(d.get("x", "") for d in data))
            ys = list(dict.fromkeys(d.get("y", "") for d in data))
            z_matrix = [[0.0] * len(xs) for _ in range(len(ys))]
            x_idx = {x: i for i, x in enumerate(xs)}
            y_idx = {y: i for i, y in enumerate(ys)}
            for d in data:
                xi = x_idx.get(d.get("x", ""), None)
                yi = y_idx.get(d.get("y", ""), None)
                if xi is not None and yi is not None:
                    z_matrix[yi][xi] = d.get("value", 0)
            fig = go.Figure(
                go.Heatmap(
                    z=z_matrix,
                    x=xs,
                    y=ys,
                    colorscale=[
                        [0, "#1a1a24"],
                        [0.25, "#2d4a6e"],
                        [0.5, "#4e79a7"],
                        [0.75, "#76b7b2"],
                        [1.0, "#22d3ee"],
                    ],
                    text=z_matrix,
                    texttemplate="%{text:.1f}",
                    textfont=dict(size=11),
                    colorbar=dict(tickfont=dict(color=TEXT_SECONDARY)),
                )
            )
        else:
            fig = go.Figure()
        return fig

    def _build_bubble(self, data: Any, width: int, height: int) -> go.Figure:
        points = data if isinstance(data, list) else []
        if not points:
            return go.Figure()

        categories = list(dict.fromkeys(p.get("category", "Default") for p in points))
        max_z = max((abs(p.get("z", 1)) for p in points), default=1) or 1

        fig = go.Figure()
        for i, cat in enumerate(categories):
            cat_points = [p for p in points if p.get("category", "Default") == cat]
            fig.add_trace(
                go.Scatter(
                    x=[p.get("x", 0) for p in cat_points],
                    y=[p.get("y", 0) for p in cat_points],
                    mode="markers",
                    name=str(cat),
                    marker=dict(
                        size=[max(5, abs(p.get("z", 10))) for p in cat_points],
                        sizemode="area",
                        sizeref=2.0 * max_z / (40.0**2),
                        color=TABLEAU10[i % len(TABLEAU10)],
                        opacity=0.7,
                        line=dict(width=1, color=TABLEAU10[i % len(TABLEAU10)]),
                    ),
                    text=[p.get("name", p.get("label", "")) for p in cat_points],
                    hovertemplate="%{text}<br>x: %{x}<br>y: %{y}<extra></extra>",
                )
            )
        return fig

    def _build_radial_bar(self, data: Any, width: int, height: int) -> go.Figure:
        items = data if isinstance(data, list) else []
        if not items:
            return go.Figure()

        # Detect if gauge-style (few items, 0-100 range)
        max_val = max((it.get("value", 0) for it in items), default=100)
        if len(items) <= 4 and max_val <= 100:
            # Gauge indicators
            rows = 1 if len(items) <= 2 else 2
            cols = min(len(items), 2)
            fig = make_subplots(
                rows=rows,
                cols=cols,
                specs=[[{"type": "indicator"}] * cols for _ in range(rows)],
                subplot_titles=[it.get("name", f"KPI {i+1}") for i, it in enumerate(items)],
            )
            for i, it in enumerate(items):
                r = (i // cols) + 1
                c = (i % cols) + 1
                fig.add_trace(
                    go.Indicator(
                        mode="gauge+number",
                        value=it.get("value", 0),
                        gauge=dict(
                            axis=dict(range=[0, max_val], tickfont=dict(color=TEXT_SECONDARY)),
                            bar=dict(color=TABLEAU10[i % len(TABLEAU10)]),
                            bgcolor=PAPER_COLOR,
                            bordercolor=GRID_COLOR,
                        ),
                        number=dict(font=dict(color=TEXT_COLOR)),
                    ),
                    row=r,
                    col=c,
                )
            return fig

        # Polar bar for many items
        fig = go.Figure()
        for i, it in enumerate(items):
            fig.add_trace(
                go.Barpolar(
                    r=[it.get("value", 0)],
                    theta=[it.get("name", f"Item {i}")],
                    marker_color=TABLEAU10[i % len(TABLEAU10)],
                    opacity=0.85,
                    name=it.get("name", f"Item {i}"),
                )
            )
        fig.update_layout(
            polar=dict(
                bgcolor=PAPER_COLOR,
                radialaxis=dict(visible=True, range=[0, max_val * 1.1], gridcolor=GRID_COLOR, tickfont=dict(color=TEXT_SECONDARY)),
                angularaxis=dict(gridcolor=GRID_COLOR, tickfont=dict(color=TEXT_SECONDARY)),
            )
        )
        return fig

    def _build_probability_cloud(self, data: Any, width: int, height: int) -> go.Figure:
        if not isinstance(data, dict):
            return go.Figure()

        fig = go.Figure()

        # Decision zones as shaded vertical bands
        for zone in data.get("decision_zones", []):
            zone_range = zone.get("range", [])
            if len(zone_range) >= 2:
                fig.add_vrect(
                    x0=zone_range[0],
                    x1=zone_range[1],
                    fillcolor=zone.get("color", hex_to_rgba(ACCENT_CYAN, 0.05)),
                    line_width=0,
                    annotation_text=zone.get("label", ""),
                    annotation_font_color=TEXT_SECONDARY,
                    annotation_font_size=9,
                )

        # Breakpoint clouds as confidence bands
        for bp in data.get("breakpoint_clouds", []):
            color = bp.get("color", ACCENT_CYAN)
            p10_p90 = bp.get("p10_p90", [])
            p25_p75 = bp.get("p25_p75", [])
            median = bp.get("median")
            label = bp.get("label", bp.get("type", ""))

            if len(p10_p90) >= 2 and median:
                y_center = 0  # place at bottom of chart
                # Vertical span line for p10-p90
                fig.add_shape(
                    type="line",
                    x0=p10_p90[0],
                    x1=p10_p90[1],
                    y0=y_center,
                    y1=y_center,
                    line=dict(color=hex_to_rgba(color, 0.6), width=8),
                )
            if len(p25_p75) >= 2 and median:
                fig.add_shape(
                    type="line",
                    x0=p25_p75[0],
                    x1=p25_p75[1],
                    y0=y_center,
                    y1=y_center,
                    line=dict(color=hex_to_rgba(color, 0.9), width=14),
                )
            if median:
                fig.add_trace(
                    go.Scatter(
                        x=[median],
                        y=[y_center],
                        mode="markers",
                        marker=dict(size=10, color=color, symbol="diamond"),
                        name=label,
                        showlegend=bool(label),
                    )
                )

        # Scenario curves
        for i, scenario in enumerate(data.get("scenario_curves", [])):
            curve = scenario.get("return_curve", {})
            exit_vals = curve.get("exit_values", [])
            returns = curve.get("return_multiples", [])
            if not exit_vals or not returns:
                continue

            prob = scenario.get("probability", 0)
            name = scenario.get("name", scenario.get("scenario", f"Scenario {i + 1}"))
            color = scenario.get("color", TABLEAU10[i % len(TABLEAU10)])

            prob_str = f" ({prob:.0%})" if prob else ""
            fig.add_trace(
                go.Scatter(
                    x=exit_vals,
                    y=returns,
                    mode="lines",
                    line=dict(width=2.5, color=color),
                    name=f"{name}{prob_str}",
                    opacity=0.85,
                )
            )

        config = data.get("config", {})
        x_label = config.get("x_axis", {}).get("label", "Exit Value ($)")
        y_label = config.get("y_axis", {}).get("label", "Return Multiple (x)")
        x_type = config.get("x_axis", {}).get("type", "log")
        y_type = config.get("y_axis", {}).get("type", "linear")

        fig.update_xaxes(type=x_type, title_text=x_label)
        fig.update_yaxes(type=y_type, title_text=y_label)
        fig.update_layout(legend=dict(x=1.02, y=1, xanchor="left"))
        return fig

    # ------------------------------------------------------------------
    # FP&A chart builders
    # ------------------------------------------------------------------

    def _build_tornado(self, data: Any, width: int, height: int) -> go.Figure:
        items = data.get("items", data) if isinstance(data, dict) else data
        if not isinstance(items, list) or not items:
            return go.Figure()

        # Sort by total impact (biggest swing at top)
        items = sorted(items, key=lambda x: abs(x.get("high", 0) - x.get("low", 0)), reverse=True)
        base_value = items[0].get("base", 0)

        names = [it.get("name", it.get("variable", f"Var {i}")) for i, it in enumerate(items)]
        low_deltas = [it.get("low", 0) - base_value for it in items]
        high_deltas = [it.get("high", 0) - base_value for it in items]

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                y=names,
                x=low_deltas,
                orientation="h",
                marker_color=NEGATIVE_COLOR,
                name="Downside",
                text=[self._format_value(d) for d in low_deltas],
                textposition="outside",
                textfont=dict(size=10),
            )
        )
        fig.add_trace(
            go.Bar(
                y=names,
                x=high_deltas,
                orientation="h",
                marker_color=POSITIVE_COLOR,
                name="Upside",
                text=[self._format_value(d) for d in high_deltas],
                textposition="outside",
                textfont=dict(size=10),
            )
        )
        fig.update_layout(barmode="overlay")
        fig.add_vline(x=0, line_width=2, line_color=TEXT_COLOR)
        fig.update_xaxes(title_text=f"Impact vs Base ({self._format_value(base_value)})")
        return fig

    def _build_treemap(self, data: Any, width: int, height: int) -> go.Figure:
        if not isinstance(data, dict) or "name" not in data:
            return go.Figure()
        ids, labels, parents, values = self._flatten_hierarchy(data)
        colors = [TABLEAU10[i % len(TABLEAU10)] for i in range(len(ids))]
        fig = go.Figure(
            go.Treemap(
                ids=ids,
                labels=labels,
                parents=parents,
                values=values,
                branchvalues="total",
                marker=dict(colors=colors, line=dict(width=2, color=PAPER_COLOR)),
                textinfo="label+value+percent parent",
                textfont=dict(size=12),
            )
        )
        fig.update_layout(margin=dict(l=10, r=10, t=40, b=10))
        return fig

    def _build_monte_carlo_histogram(self, data: Any, width: int, height: int) -> go.Figure:
        labels, datasets = self._extract_labels_datasets(data)
        fig = go.Figure()
        for i, ds in enumerate(datasets):
            fig.add_trace(
                go.Bar(
                    x=labels,
                    y=ds.get("data", []),
                    name=ds.get("label", f"Series {i + 1}"),
                    marker_color=hex_to_rgba(TABLEAU10[i % len(TABLEAU10)], 0.8),
                    opacity=0.85,
                )
            )
        fig.update_layout(barmode="overlay")
        fig.update_xaxes(title_text="Outcome")
        fig.update_yaxes(title_text="Frequency")
        return fig

    def _build_monte_carlo_fan(self, data: Any, width: int, height: int) -> go.Figure:
        if not isinstance(data, dict):
            return go.Figure()

        metric = data.get("metric", "cash_balance")
        pcts = data.get("trajectory_percentiles", data.get("percentiles", {}))
        metric_pcts = pcts.get(metric, pcts)  # fallback to top-level if metric key missing

        periods = data.get("periods", [])
        # Auto-generate period labels if missing
        p50 = metric_pcts.get("p50", [])
        if not periods and p50:
            periods = [f"M{i + 1}" for i in range(len(p50))]

        fig = go.Figure()

        # p5-p95 band (lightest)
        p95 = metric_pcts.get("p95", metric_pcts.get("p90", []))
        p5 = metric_pcts.get("p5", metric_pcts.get("p10", []))
        if p95 and p5:
            fig.add_trace(
                go.Scatter(
                    x=periods, y=p95, mode="lines", line=dict(width=0),
                    showlegend=False, name="p95", hoverinfo="skip",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=periods, y=p5, mode="lines",
                    fill="tonexty", fillcolor=hex_to_rgba(ACCENT_CYAN, 0.08),
                    line=dict(width=0), name="p5–p95",
                )
            )

        # p25-p75 band (darker)
        p75 = metric_pcts.get("p75", [])
        p25 = metric_pcts.get("p25", [])
        if p75 and p25:
            fig.add_trace(
                go.Scatter(
                    x=periods, y=p75, mode="lines", line=dict(width=0),
                    showlegend=False, name="p75", hoverinfo="skip",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=periods, y=p25, mode="lines",
                    fill="tonexty", fillcolor=hex_to_rgba(ACCENT_CYAN, 0.22),
                    line=dict(width=0), name="p25–p75",
                )
            )

        # Median line
        if p50:
            fig.add_trace(
                go.Scatter(
                    x=periods, y=p50, mode="lines",
                    line=dict(width=2.5, color=ACCENT_CYAN),
                    name="Median (p50)",
                )
            )

        fig.update_yaxes(title_text=metric.replace("_", " ").title())
        return fig

    def _build_stacked_bar(self, data: Any, width: int, height: int) -> go.Figure:
        # Normalize FPA format (x_axis/series) to Chart.js format (labels/datasets)
        if isinstance(data, dict) and "x_axis" in data and "series" in data:
            data = {
                "labels": data["x_axis"],
                "datasets": [
                    {
                        "label": s.get("name", f"Series {i}"),
                        "data": s.get("data", []),
                        "backgroundColor": s.get("color", "#666"),
                    }
                    for i, s in enumerate(data.get("series", []))
                ],
            }
        labels, datasets = self._extract_labels_datasets(data)
        fig = go.Figure()
        for i, ds in enumerate(datasets):
            fig.add_trace(
                go.Bar(
                    x=labels,
                    y=ds.get("data", []),
                    name=ds.get("label", f"Series {i + 1}"),
                    marker_color=ds.get("backgroundColor", TABLEAU10[i % len(TABLEAU10)]),
                )
            )
        fig.update_layout(barmode="stack")
        return fig

    def _build_fpa_stress_test(self, data: Any, width: int, height: int) -> go.Figure:
        labels, datasets = self._extract_labels_datasets(data)
        scenario_colors = [BULL_COLOR, BASE_COLOR, BEAR_COLOR] + TABLEAU10
        fig = go.Figure()
        for i, ds in enumerate(datasets):
            fig.add_trace(
                go.Scatter(
                    x=labels,
                    y=ds.get("data", []),
                    mode="lines+markers",
                    line=dict(width=2, color=scenario_colors[i % len(scenario_colors)]),
                    marker=dict(size=6),
                    name=ds.get("label", f"Scenario {i + 1}"),
                )
            )
        return fig

    def _build_bull_bear_base(self, data: Any, width: int, height: int) -> go.Figure:
        labels, datasets = self._extract_labels_datasets(data)
        scenario_colors = {"Bull": BULL_COLOR, "Base": BASE_COLOR, "Bear": BEAR_COLOR}
        fig = go.Figure()
        for i, ds in enumerate(datasets):
            ds_label = ds.get("label", f"Series {i + 1}")
            color = scenario_colors.get(ds_label, TABLEAU10[i % len(TABLEAU10)])
            fig.add_trace(
                go.Bar(
                    x=labels,
                    y=ds.get("data", []),
                    name=ds_label,
                    marker_color=color,
                )
            )
        fig.update_layout(barmode="group")
        return fig

    def _build_funnel(self, data: Any, width: int, height: int) -> go.Figure:
        items = data if isinstance(data, list) else data.get("items", data.get("stages", []))
        if not isinstance(items, list):
            items = []

        fig = go.Figure(
            go.Funnel(
                y=[it.get("name", f"Stage {i}") for i, it in enumerate(items)],
                x=[it.get("value", 0) for it in items],
                textposition="inside",
                textinfo="value+percent initial",
                marker=dict(
                    color=[TABLEAU10[i % len(TABLEAU10)] for i in range(len(items))],
                    line=dict(color=PAPER_COLOR, width=2),
                ),
                connector=dict(line=dict(color=GRID_COLOR)),
            )
        )
        return fig

    def _build_cash_flow_waterfall(self, data: Any, width: int, height: int) -> go.Figure:
        items = data if isinstance(data, list) else data.get("items", [])
        if not isinstance(items, list):
            items = []

        names = [it.get("name", f"Item {i}") for i, it in enumerate(items)]
        vals = [it.get("value", 0) for it in items]
        measures = ["total" if it.get("isSubtotal") else "relative" for it in items]
        # First item is usually "Opening Balance"
        if measures and measures[0] == "relative":
            measures[0] = "total"

        fig = go.Figure(
            go.Waterfall(
                x=names,
                y=vals,
                measure=measures,
                connector=dict(line=dict(color=GRID_COLOR, dash="dot", width=1)),
                increasing=dict(marker_color=POSITIVE_COLOR),
                decreasing=dict(marker_color=NEGATIVE_COLOR),
                totals=dict(marker_color=SUBTOTAL_COLOR),
                textposition="outside",
                text=[self._format_value(v) for v in vals],
                textfont=dict(size=10, color=TEXT_SECONDARY),
            )
        )
        fig.update_layout(showlegend=False, waterfallgap=0.3)
        return fig

    def _build_revenue_forecast(self, data: Any, width: int, height: int) -> go.Figure:
        labels, datasets = self._extract_labels_datasets(data)
        fig = go.Figure()
        for i, ds in enumerate(datasets):
            is_primary = i == 0
            fig.add_trace(
                go.Scatter(
                    x=labels,
                    y=ds.get("data", []),
                    mode="lines+markers" if is_primary else "lines",
                    line=dict(
                        width=2.5 if is_primary else 1.5,
                        dash="solid" if is_primary else "dash",
                        color=ds.get("borderColor", TABLEAU10[i % len(TABLEAU10)]),
                    ),
                    marker=dict(size=6 if is_primary else 0),
                    name=ds.get("label", f"Series {i + 1}"),
                )
            )
        return fig

    def _build_bar_comparison(self, data: Any, width: int, height: int) -> go.Figure:
        labels, datasets = self._extract_labels_datasets(data)
        fig = go.Figure()
        for i, ds in enumerate(datasets):
            fig.add_trace(
                go.Bar(
                    x=labels,
                    y=ds.get("data", []),
                    name=ds.get("label", f"Series {i + 1}"),
                    marker_color=ds.get("backgroundColor", TABLEAU10[i % len(TABLEAU10)]),
                )
            )
        fig.update_layout(barmode="group")
        return fig

    def _build_cap_table_evolution(self, data: Any, width: int, height: int) -> go.Figure:
        rounds = data if isinstance(data, list) else data.get("rounds", [])
        if not isinstance(rounds, list) or not rounds:
            return go.Figure()

        # Detect stakeholder keys (everything except round/name/label identifiers)
        skip_keys = {"round", "name", "label", "round_name"}
        stakeholders = [k for k in rounds[0].keys() if k not in skip_keys]
        round_labels = [r.get("round", r.get("name", f"R{i}")) for i, r in enumerate(rounds)]

        stakeholder_colors = {
            "founders": TABLEAU10[0],
            "founders_pct": TABLEAU10[0],
            "esop": TABLEAU10[1],
            "esop_pct": TABLEAU10[1],
            "our_fund": TABLEAU10[4],
            "our_ownership": TABLEAU10[4],
            "our_ownership_pct": TABLEAU10[4],
            "others": TABLEAU10[2],
            "other_investors": TABLEAU10[2],
            "other_investors_pct": TABLEAU10[2],
        }

        fig = go.Figure()
        for i, s in enumerate(stakeholders):
            values = [r.get(s, 0) for r in rounds]
            color = stakeholder_colors.get(s, TABLEAU10[i % len(TABLEAU10)])
            fig.add_trace(
                go.Scatter(
                    x=round_labels,
                    y=values,
                    stackgroup="one",
                    groupnorm="percent",
                    name=s.replace("_", " ").replace(" pct", "").title(),
                    fillcolor=hex_to_rgba(color, 0.7),
                    line=dict(width=0.5, color=color),
                )
            )
        fig.update_yaxes(ticksuffix="%", range=[0, 100], title_text="Ownership %")
        fig.update_xaxes(title_text="Round")
        return fig

    # ------------------------------------------------------------------
    # Shared helpers for labels+datasets pattern
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_labels_datasets(data: Any) -> Tuple[list, list]:
        """Extract (labels, datasets) from the common Chart.js-like format."""
        if isinstance(data, dict):
            return data.get("labels", []), data.get("datasets", [])
        return [], []


# Global instance
chart_renderer = ChartRendererService()
