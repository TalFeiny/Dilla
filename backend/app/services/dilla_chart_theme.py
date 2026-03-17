"""
Dilla Chart Theme - Plotly template matching the Dilla design system.

Dark-mode, financial-grade, minimal chartjunk.
Matches the CSS variables and COLOR_SCHEMES from the frontend.
"""

import plotly.graph_objects as go
import plotly.io as pio

# ---------------------------------------------------------------------------
# Design tokens (from globals.css + TableauLevelCharts.tsx COLOR_SCHEMES)
# ---------------------------------------------------------------------------

BG_COLOR = "#0a0a0a"
PAPER_COLOR = "#1a1a24"
TEXT_COLOR = "#f1f5f9"
TEXT_SECONDARY = "#94a3b8"
GRID_COLOR = "#2d2d3d"
ACCENT_CYAN = "#22d3ee"

# Scenario colors
BULL_COLOR = "#10b981"
BASE_COLOR = "#4e79a7"
BEAR_COLOR = "#ef4444"

# Financial positive / negative
POSITIVE_COLOR = "#10b981"
NEGATIVE_COLOR = "#ef4444"
SUBTOTAL_COLOR = "#4e79a7"

# Tableau 10 (primary series palette)
TABLEAU10 = [
    "#4e79a7", "#f28e2c", "#e15759", "#76b7b2", "#59a14f",
    "#edc949", "#af7aa1", "#ff9da7", "#9c755f", "#bab0ab",
]

# Financial blue sequential
FINANCIAL_BLUE = [
    "#08519c", "#3182bd", "#6baed6", "#9ecae1", "#c6dbef",
    "#deebf7", "#f7fbff",
]

# Dark-theme heatmap colorscale (low → high)
HEATMAP_COLORSCALE = [
    [0.0, "#1a1a24"],
    [0.25, "#2d4a6e"],
    [0.5, "#4e79a7"],
    [0.75, "#76b7b2"],
    [1.0, "#22d3ee"],
]

# Diverging colorscale for variance / positive-negative
DIVERGING_COLORSCALE = [
    [0.0, "#ef4444"],
    [0.25, "#f59e0b"],
    [0.5, "#1a1a24"],
    [0.75, "#10b981"],
    [1.0, "#22d3ee"],
]

FONT_FAMILY = "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"


def build_dilla_template() -> go.layout.Template:
    """Build a reusable Plotly template encoding the Dilla design system."""
    template = go.layout.Template()

    template.layout = go.Layout(
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=PAPER_COLOR,
        font=dict(family=FONT_FAMILY, color=TEXT_COLOR, size=13),
        title=dict(
            font=dict(size=16, color=TEXT_COLOR, family=FONT_FAMILY),
            x=0.0,
            xanchor="left",
            pad=dict(l=10, t=10),
        ),
        colorway=TABLEAU10,
        margin=dict(l=60, r=30, t=50, b=50),
        legend=dict(
            font=dict(color=TEXT_SECONDARY, size=11),
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
        ),
        xaxis=dict(
            gridcolor=GRID_COLOR,
            zerolinecolor=GRID_COLOR,
            linecolor=GRID_COLOR,
            tickfont=dict(color=TEXT_SECONDARY, size=11),
            title_font=dict(color=TEXT_SECONDARY, size=12),
        ),
        yaxis=dict(
            gridcolor=GRID_COLOR,
            zerolinecolor=GRID_COLOR,
            linecolor=GRID_COLOR,
            tickfont=dict(color=TEXT_SECONDARY, size=11),
            title_font=dict(color=TEXT_SECONDARY, size=12),
        ),
        hoverlabel=dict(
            bgcolor=PAPER_COLOR,
            bordercolor=GRID_COLOR,
            font=dict(color=TEXT_COLOR, size=12),
        ),
    )

    return template


# Module-level singleton
_DILLA_TEMPLATE = build_dilla_template()


def apply_dilla_theme(fig: go.Figure) -> go.Figure:
    """Apply the Dilla theme to a figure in-place and return it."""
    fig.update_layout(template=_DILLA_TEMPLATE)
    return fig


def get_scenario_colors() -> dict:
    return {"bull": BULL_COLOR, "base": BASE_COLOR, "bear": BEAR_COLOR}


def hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """Convert #RRGGBB to rgba(r,g,b,a)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"
