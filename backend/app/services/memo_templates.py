"""Lightweight memo templates — Python dicts, ~20 lines each.

Each template defines:
- title_pattern: f-string with {companies}, {fund_name}, {quarter}, {year}
- sections: ordered list of section blueprints
- required_data: keys that MUST exist in shared_data for the memo to be useful
- optional_data: keys that enrich the memo if present

Section blueprints have:
- key: unique ID for the section
- heading: display heading
- type: "narrative" (LLM-generated), "metrics" (data-driven), "chart" (visualization)
- data_keys: which shared_data keys feed this section
- prompt_hint: guidance for LLM narrative generation
"""

from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Section blueprint type aliases
# ---------------------------------------------------------------------------

def _section(key: str, heading: str, type: str = "narrative",
             data_keys: List[str] | None = None,
             prompt_hint: str = "",
             chart_type: str | None = None) -> Dict[str, Any]:
    return {
        "key": key,
        "heading": heading,
        "type": type,
        "data_keys": data_keys or [],
        "prompt_hint": prompt_hint,
        "chart_type": chart_type,
    }


# ---------------------------------------------------------------------------
# IC Memo — Investment Committee presentation
# ---------------------------------------------------------------------------
IC_MEMO = {
    "id": "ic_memo",
    "title_pattern": "Investment Committee Memo — {companies}",
    "required_data": ["companies"],
    "optional_data": ["fund_context", "cap_table_history", "scenario_analysis", "revenue_projections"],
    "sections": [
        _section("thesis", "Investment Thesis",
                 prompt_hint="Why invest? 3-4 sentences on the opportunity, market timing, and team."),
        _section("market", "Market Analysis", data_keys=["companies"],
                 prompt_hint="TAM/SAM/SOM with citations. Competitive landscape. Growth drivers."),
        _section("financials", "Financial Overview", type="metrics",
                 data_keys=["companies"],
                 prompt_hint="Revenue, growth, margins, burn, runway. Use actual numbers."),
        _section("business_model", "Business Model & Unit Economics",
                 data_keys=["companies"],
                 prompt_hint=(
                     "Markdown table: ACV, LTV/CAC, payback period, GPU cost per transaction, gross margin breakdown. "
                     "For AI companies: GPU passthrough ratio and workflow ownership score. "
                     "For SaaS: net dollar retention, logo churn, expansion revenue."
                 )),
        _section("comparables", "Comparable Companies & Revenue Multiples",
                 data_keys=["companies"],
                 prompt_hint=(
                     "Markdown table of 5-8 public and late-stage comps: Company | Revenue | Growth | EV/Revenue | Gross Margin | Stage. "
                     "Include median and where target sits vs comps. "
                     "Use actual comp data from provided sources, not invented numbers."
                 )),
        _section("revenue_forecast", "Revenue Projections", type="chart",
                 data_keys=["companies", "revenue_projections"], chart_type="revenue_forecast"),
        _section("growth_decay", "Growth Trajectory", type="chart",
                 data_keys=["companies"], chart_type="growth_decay"),
        _section("cap_table", "Cap Table & Ownership", type="chart",
                 data_keys=["cap_table_history"], chart_type="pie"),
        _section("round_dynamics", "Round Dynamics & Dilution Path",
                 data_keys=["companies", "cap_table_history"],
                 prompt_hint=(
                     "Round-by-round dilution table: Round | Pre-$ | Post-$ | Our % Before | Our % After | ESOP Pool. "
                     "Show ownership path from entry to projected exit. "
                     "Include follow-on assumptions and pro-rata rights."
                 )),
        _section("scenarios", "Exit Scenarios", type="chart",
                 data_keys=["scenario_analysis"], chart_type="probability_cloud"),
        _section("comparison_table", "Company Comparison Matrix",
                 data_keys=["companies"],
                 prompt_hint=(
                     "Side-by-side markdown table when 2+ companies: "
                     "Metric | Company A | Company B | ... for revenue, growth, valuation, multiple, team, TAM, moat score. "
                     "Skip this section if only 1 company."
                 )),
        _section("risks", "Key Risks",
                 prompt_hint="Bulleted list of top 5 risks: execution, market, competition, funding, regulatory. One sentence each with severity rating."),
        _section("recommendation", "Recommendation",
                 data_keys=["companies", "fund_context"],
                 prompt_hint="Clear invest/pass/waitlist with check size, ownership target, and conditions."),
    ],
}


# ---------------------------------------------------------------------------
# Follow-On Memo — pro-rata / extend-or-sell decision
# ---------------------------------------------------------------------------
FOLLOWON_MEMO = {
    "id": "followon",
    "title_pattern": "Follow-On Investment Analysis — {companies}",
    "required_data": ["companies"],
    "optional_data": ["followon_strategy", "cap_table_history", "fund_context", "scenario_analysis"],
    "sections": [
        _section("position", "Current Position", type="metrics",
                 data_keys=["companies", "followon_strategy"],
                 prompt_hint="Our investment to date, entry round, current ownership, MOIC."),
        _section("performance", "Performance Since Investment", data_keys=["companies"],
                 prompt_hint="Revenue trajectory, key milestones achieved, team growth."),
        _section("comparables", "Current Comparables & Revenue Multiples",
                 data_keys=["companies"],
                 prompt_hint=(
                     "Markdown table: Company | Revenue | Growth | EV/Revenue | Stage. "
                     "Show where portfolio company sits vs public/late-stage comps now vs at entry."
                 )),
        _section("prorata", "Pro-Rata Analysis", type="metrics",
                 data_keys=["followon_strategy"],
                 prompt_hint="Pro-rata amount, ownership with/without, dilution impact."),
        _section("dilution_walkthrough", "Dilution Walkthrough",
                 data_keys=["followon_strategy", "cap_table_history"],
                 prompt_hint=(
                     "Round-by-round markdown table: Round | Pre-$ | Post-$ | Our % Before | Our % After. "
                     "Show historical rounds and projected next round with/without follow-on. "
                     "Include ESOP expansion assumptions."
                 )),
        _section("ownership_chart", "Ownership Scenarios", type="chart",
                 data_keys=["followon_strategy"], chart_type="bar"),
        _section("exit_impact", "Exit Impact", type="metrics",
                 data_keys=["followon_strategy", "scenario_analysis"],
                 prompt_hint="Proceeds at various exit multiples, with and without follow-on."),
        _section("return_matrix", "Return Sensitivity Matrix",
                 data_keys=["followon_strategy", "scenario_analysis"],
                 prompt_hint=(
                     "Markdown table: rows = follow-on scenarios (no follow-on, pro-rata, super pro-rata), "
                     "columns = exit multiples (3x, 5x, 10x, 20x revenue). "
                     "Each cell = MOIC + gross proceeds in $M. "
                     "Use actual ownership percentages from data."
                 )),
        _section("recommendation", "Recommendation",
                 data_keys=["followon_strategy", "fund_context"],
                 prompt_hint="Follow-on or not? Amount, conditions, key risks."),
    ],
}


# ---------------------------------------------------------------------------
# LP Quarterly Report
# ---------------------------------------------------------------------------
LP_REPORT = {
    "id": "lp_report",
    "title_pattern": "LP Quarterly Report — {fund_name} — Q{quarter} {year}",
    "required_data": ["fund_context"],
    "optional_data": ["fund_metrics", "portfolio_health", "companies", "reserve_forecast"],
    "sections": [
        _section("fund_summary", "Fund Summary", type="metrics",
                 data_keys=["fund_metrics", "fund_context"],
                 prompt_hint="Fund size, deployed, remaining, TVPI, DPI, IRR. One paragraph."),
        _section("nav_waterfall", "NAV Contribution", type="chart",
                 data_keys=["fund_metrics"], chart_type="waterfall"),
        _section("portfolio_updates", "Portfolio Company Updates",
                 data_keys=["companies", "portfolio_health"],
                 prompt_hint="Per-company: ARR, growth, runway, key events. 2-3 sentences each."),
        _section("moic_chart", "Portfolio MOIC", type="chart",
                 data_keys=["portfolio_health"], chart_type="bar"),
        _section("deployment", "Deployment & Reserves",
                 data_keys=["fund_context", "reserve_forecast"],
                 prompt_hint="Pacing vs plan, reserve adequacy, upcoming follow-ons."),
        _section("outlook", "Outlook",
                 prompt_hint="Market conditions, pipeline, expected activity next quarter."),
    ],
}


# ---------------------------------------------------------------------------
# GP Strategy Update — internal strategy
# ---------------------------------------------------------------------------
GP_UPDATE = {
    "id": "gp_strategy",
    "title_pattern": "GP Strategy & Portfolio Update",
    "required_data": ["fund_context"],
    "optional_data": ["fund_metrics", "portfolio_health", "companies", "fund_scenarios"],
    "sections": [
        _section("deployment", "Deployment Pacing", type="metrics",
                 data_keys=["fund_context", "fund_metrics"],
                 prompt_hint="Deployed vs plan, pace adjustment needed, vintage analysis."),
        _section("portfolio_health", "Portfolio Health", type="metrics",
                 data_keys=["portfolio_health"],
                 prompt_hint="Winners, watchlist, write-down candidates. Growth vs burn matrix."),
        _section("pipeline", "Pipeline & Sourcing",
                 prompt_hint="Active deals, sectors of interest, co-investor dynamics."),
        _section("followon_plan", "Follow-On Strategy",
                 data_keys=["reserve_forecast", "followon_strategy"],
                 prompt_hint="Which companies need follow-on, reserve adequacy, priority stack."),
        _section("scenarios", "Scenario Planning", type="chart",
                 data_keys=["fund_scenarios"], chart_type="bar"),
        _section("actions", "Action Items",
                 prompt_hint="Top 5 action items with owners and deadlines."),
    ],
}


# ---------------------------------------------------------------------------
# Comparison Report — side-by-side investment comparison
# ---------------------------------------------------------------------------
COMPARISON_REPORT = {
    "id": "comparison",
    "title_pattern": "Investment Comparison — {companies}",
    "required_data": ["companies"],
    "optional_data": ["scenario_analysis", "cap_table_history", "fund_context", "revenue_projections"],
    "sections": [
        _section("overview", "Company Overview", type="metrics",
                 data_keys=["companies"],
                 prompt_hint="Side-by-side: stage, revenue, growth, valuation, team, market."),
        _section("market_position", "Market Position",
                 data_keys=["companies"],
                 prompt_hint="Compare TAM, competitive position, moat strength, GTM."),
        _section("financials_comparison", "Financial Comparison", type="metrics",
                 data_keys=["companies"],
                 prompt_hint="Revenue multiples, capital efficiency, burn, runway."),
        _section("revenue_forecast", "Revenue Projections", type="chart",
                 data_keys=["companies", "revenue_projections"], chart_type="revenue_forecast"),
        _section("scenarios", "Exit Scenario Comparison", type="chart",
                 data_keys=["scenario_analysis"], chart_type="probability_cloud"),
        _section("risks", "Risk Comparison",
                 data_keys=["companies"],
                 prompt_hint="Key risk differences: execution, market, competition, team."),
        _section("recommendation", "Recommendation",
                 data_keys=["companies", "fund_context"],
                 prompt_hint="Which to invest in, or both? Relative conviction and sizing."),
    ],
}


# ---------------------------------------------------------------------------
# Bespoke LP Response — answer arbitrary LP questions with data
# ---------------------------------------------------------------------------
BESPOKE_LP_RESPONSE = {
    "id": "bespoke_lp",
    "title_pattern": "LP Response — {query_summary}",
    "required_data": [],
    "optional_data": ["companies", "fund_metrics", "portfolio_health", "fund_context",
                      "scenario_analysis", "exit_modeling"],
    "sections": [
        _section("answer", "Summary", data_keys=["companies", "fund_metrics"],
                 prompt_hint="Direct answer to the LP's question with supporting data."),
        _section("supporting_data", "Supporting Analysis", type="metrics",
                 data_keys=["companies", "fund_metrics", "portfolio_health"],
                 prompt_hint="Relevant metrics, charts, and portfolio data that support the answer."),
        _section("context", "Context & Methodology",
                 prompt_hint="How the analysis was conducted, data sources, assumptions."),
    ],
}


# ---------------------------------------------------------------------------
# Fund Analysis — waterfall, LP/GP split, carry
# ---------------------------------------------------------------------------
FUND_ANALYSIS = {
    "id": "fund_analysis",
    "title_pattern": "Fund Analysis — {fund_name}",
    "required_data": ["fund_context"],
    "optional_data": ["fund_metrics", "fund_scenarios", "exit_modeling"],
    "sections": [
        _section("fund_overview", "Fund Overview", type="metrics",
                 data_keys=["fund_context", "fund_metrics"],
                 prompt_hint="Fund size, vintage, strategy, current status."),
        _section("waterfall", "Distribution Waterfall", type="chart",
                 data_keys=["fund_scenarios", "exit_modeling"], chart_type="waterfall"),
        _section("lp_gp_split", "LP/GP Economics", type="metrics",
                 data_keys=["fund_metrics"],
                 prompt_hint="Management fees, carry, hurdle rate, clawback provisions."),
        _section("scenario_returns", "Scenario Returns", type="chart",
                 data_keys=["fund_scenarios"], chart_type="bar"),
        _section("recommendation", "Assessment",
                 prompt_hint="Fund health, pacing, expected returns, key decisions."),
    ],
}


# ---------------------------------------------------------------------------
# Ownership Analysis — cap table evolution → dilution → exit ownership
# ---------------------------------------------------------------------------
OWNERSHIP_ANALYSIS = {
    "id": "ownership_analysis",
    "title_pattern": "Ownership Projection — {companies}",
    "required_data": ["companies"],
    "optional_data": ["cap_table_history", "scenario_analysis", "followon_strategy"],
    "sections": [
        _section("current_ownership", "Current Ownership", type="metrics",
                 data_keys=["companies", "cap_table_history"],
                 prompt_hint="Current ownership breakdown by investor class."),
        _section("cap_table_evolution", "Cap Table Evolution", type="chart",
                 data_keys=["cap_table_history"], chart_type="pie"),
        _section("dilution_modeling", "Dilution Projections", type="metrics",
                 data_keys=["companies", "followon_strategy"],
                 prompt_hint="Projected dilution through future rounds, ESOP expansion."),
        _section("exit_ownership", "Exit Ownership & Proceeds", type="metrics",
                 data_keys=["scenario_analysis"],
                 prompt_hint="Ownership at exit under different scenarios, proceeds per investor."),
        _section("probability_cloud", "Return Distribution", type="chart",
                 data_keys=["scenario_analysis"], chart_type="probability_cloud"),
    ],
}


# ---------------------------------------------------------------------------
# Plan Memo — session plan that doubles as resumable context for next session
# ---------------------------------------------------------------------------
PLAN_MEMO = {
    "id": "plan_memo",
    "title_pattern": "Execution Plan — {query_summary}",
    "required_data": [],
    "optional_data": ["companies", "fund_context", "fund_metrics", "portfolio_health"],
    "sections": [
        _section("objective", "Objective",
                 prompt_hint="What the user wants to accomplish. One clear sentence."),
        _section("findings", "Research Findings", type="metrics",
                 data_keys=["companies", "fund_metrics", "portfolio_health"],
                 prompt_hint="Key data points discovered during research phase."),
        _section("steps", "Execution Steps",
                 prompt_hint="Ordered list of steps to execute, with tool names and expected outputs."),
        _section("decisions", "Open Decisions",
                 prompt_hint="Choices that need user input before proceeding."),
        _section("context_snapshot", "Context Snapshot", type="context",
                 data_keys=["companies", "fund_context", "fund_metrics",
                            "portfolio_health", "cap_table_history",
                            "scenario_analysis", "followon_strategy"],
                 prompt_hint="Machine-readable snapshot of all accumulated data for session resumption."),
    ],
    "is_resumable": True,
}


# ---------------------------------------------------------------------------
# Diligence Memo — lightweight initial assessment (no keyword triggers)
# ---------------------------------------------------------------------------
DILIGENCE_MEMO = {
    "id": "diligence_memo",
    "title_pattern": "Initial Diligence — {companies}",
    "required_data": ["companies"],
    "optional_data": ["fund_context", "portfolio_health"],
    "sections": [
        _section("overview", "Company Overview",
                 data_keys=["companies"],
                 prompt_hint="What the company does (factual, no buzzwords), founding year, HQ, team size."),
        _section("financials", "Key Financials", type="metrics",
                 data_keys=["companies"],
                 prompt_hint="Stage, last round, revenue estimate, valuation, burn, runway. Flag what's inferred vs confirmed."),
        _section("recent_activity", "Recent Activity",
                 data_keys=["companies"],
                 prompt_hint="Latest funding, key hires, product launches, partnerships, press in last 6 months."),
        _section("assessment", "Initial Assessment",
                 data_keys=["companies", "fund_context"],
                 prompt_hint="Fit with fund thesis, sector overlap with portfolio, key risks, whether deeper diligence is warranted."),
    ],
}


# ---------------------------------------------------------------------------
# Team Comparison — founding team head-to-head across companies
# ---------------------------------------------------------------------------
TEAM_COMPARISON = {
    "id": "team_comparison",
    "title_pattern": "Team Comparison — {companies}",
    "required_data": ["companies"],
    "optional_data": ["fund_context"],
    "sections": [
        _section("overview", "Team Overview", type="metrics",
                 data_keys=["companies"],
                 prompt_hint="Per company: founder names, backgrounds, previous exits, domain expertise. Table format."),
        _section("scoring", "Team Scoring", type="chart",
                 data_keys=["companies"], chart_type="radar_comparison",
                 prompt_hint="Score each team 1-10 on: technical depth, domain expertise, execution track record, fundraising ability, leadership."),
        _section("technical_depth", "Technical Founder Assessment",
                 data_keys=["companies"],
                 prompt_hint="CTO/technical founder background, patents, open-source contributions, engineering team quality."),
        _section("execution_signals", "Execution Signals",
                 data_keys=["companies"],
                 prompt_hint="Hiring velocity, product shipping cadence, customer wins, milestone achievement rate."),
        _section("gaps_risks", "Team Gaps & Risks",
                 data_keys=["companies"],
                 prompt_hint="Key hires needed, single-person dependencies, retention risks, cultural concerns."),
        _section("verdict", "Verdict",
                 prompt_hint="Which team is better positioned to execute? Key differentiators."),
    ],
}


# ---------------------------------------------------------------------------
# Market Dynamics — deep competitive landscape + market timing
# ---------------------------------------------------------------------------
MARKET_DYNAMICS = {
    "id": "market_dynamics",
    "title_pattern": "Market Dynamics Analysis — {companies}",
    "required_data": ["companies"],
    "optional_data": ["fund_context", "scenario_analysis"],
    "sections": [
        _section("market_overview", "Market Overview", type="metrics",
                 data_keys=["companies"],
                 prompt_hint="TAM/SAM/SOM with BLS or industry citations. Market maturity stage. Growth rate and drivers."),
        _section("competitive_map", "Competitive Landscape", type="chart",
                 data_keys=["companies"], chart_type="scatter_multiples",
                 prompt_hint="Map competitors on revenue multiple vs growth rate. Identify white space."),
        _section("timing", "Market Timing",
                 data_keys=["companies"],
                 prompt_hint="Why now? Regulatory tailwinds, technology inflection, buyer behavior shifts."),
        _section("entry_barriers", "Entry Barriers & Moat",
                 data_keys=["companies"],
                 prompt_hint="Network effects, switching costs, data advantages, regulatory moats. Score 0-10 per dimension."),
        _section("gtm", "Go-To-Market Strategy",
                 data_keys=["companies"],
                 prompt_hint="GTM motion: PLG, enterprise sales, channel, marketplace. CAC/LTV if available."),
        _section("risks", "Market Risks",
                 prompt_hint="Platform risk, regulatory, macro, competition from incumbents."),
    ],
}


# ---------------------------------------------------------------------------
# Portfolio Construction — concentration, allocation, vintage analysis
# ---------------------------------------------------------------------------
PORTFOLIO_CONSTRUCTION = {
    "id": "portfolio_construction",
    "title_pattern": "Portfolio Construction Analysis — {fund_name}",
    "required_data": ["fund_context"],
    "optional_data": ["companies", "fund_metrics", "portfolio_health", "reserve_forecast"],
    "sections": [
        _section("allocation", "Current Allocation", type="chart",
                 data_keys=["companies", "fund_metrics"], chart_type="treemap",
                 prompt_hint="Sector allocation, stage allocation, check size distribution."),
        _section("concentration", "Concentration Risk", type="metrics",
                 data_keys=["companies", "fund_metrics"],
                 prompt_hint="Top 3 positions as % of fund, HHI, sector concentration, vintage concentration."),
        _section("reserves", "Reserve Analysis", type="metrics",
                 data_keys=["reserve_forecast", "fund_context"],
                 prompt_hint="Total reserves, reserved per company, reserve ratio, follow-on capacity."),
        _section("construction_fitness", "Portfolio Fitness",
                 data_keys=["companies", "portfolio_health"],
                 prompt_hint="Power law distribution check, expected winners, zombie companies, graduation rates."),
        _section("optimization", "Optimization Opportunities",
                 data_keys=["companies", "fund_context"],
                 prompt_hint="Under-allocated sectors, missing check sizes, portfolio gaps, rebalancing options."),
    ],
}


# ---------------------------------------------------------------------------
# Pipeline Review — deal flow funnel and velocity
# ---------------------------------------------------------------------------
PIPELINE_REVIEW = {
    "id": "pipeline_review",
    "title_pattern": "Pipeline Review — {fund_name} — Q{quarter} {year}",
    "required_data": ["fund_context"],
    "optional_data": ["companies", "portfolio_health"],
    "sections": [
        _section("funnel", "Deal Flow Funnel", type="chart",
                 data_keys=["companies"], chart_type="funnel_pipeline",
                 prompt_hint="Sourced → First Meeting → Diligence → Term Sheet → Closed. Count and $ at each stage."),
        _section("velocity", "Pipeline Velocity", type="metrics",
                 data_keys=["companies"],
                 prompt_hint="Average days per stage, conversion rates, time-to-close."),
        _section("active_deals", "Active Deals",
                 data_keys=["companies"],
                 prompt_hint="Companies currently in diligence or term sheet. Stage, expected close, check size."),
        _section("sourcing", "Sourcing Analysis",
                 data_keys=["companies"],
                 prompt_hint="Sourcing channels: inbound %, referral %, outbound %. Quality by channel."),
        _section("pass_analysis", "Pass Analysis",
                 data_keys=["companies"],
                 prompt_hint="Why we passed on recent deals. Pattern analysis. Anti-portfolio tracking."),
    ],
}


# ---------------------------------------------------------------------------
# Competitive Landscape — company positioning vs competitors
# ---------------------------------------------------------------------------
COMPETITIVE_LANDSCAPE = {
    "id": "competitive_landscape",
    "title_pattern": "Competitive Landscape — {companies}",
    "required_data": ["companies"],
    "optional_data": ["fund_context", "scenario_analysis"],
    "sections": [
        _section("positioning", "Market Positioning", type="chart",
                 data_keys=["companies"], chart_type="scatter_multiples",
                 prompt_hint="Plot company vs competitors on revenue/growth axes. Identify quadrant positioning."),
        _section("competitor_profiles", "Key Competitors",
                 data_keys=["companies"],
                 prompt_hint="Top 3-5 competitors: revenue, funding, team size, key differentiators."),
        _section("feature_comparison", "Product Comparison", type="metrics",
                 data_keys=["companies"],
                 prompt_hint="Feature matrix: key capabilities scored across players."),
        _section("moat_scoring", "Moat & Defensibility", type="chart",
                 data_keys=["companies"], chart_type="radar_comparison",
                 prompt_hint="Score 0-10: network effects, switching costs, data moat, brand, regulatory, economies of scale."),
        _section("win_loss", "Win/Loss Analysis",
                 data_keys=["companies"],
                 prompt_hint="Where company wins deals vs loses. Key decision factors for buyers."),
        _section("outlook", "Competitive Outlook",
                 prompt_hint="Expected competitive dynamics: consolidation, new entrants, platform shifts."),
    ],
}


# ---------------------------------------------------------------------------
# Follow-On Deep Dive — extended follow-on with cap table evolution
# ---------------------------------------------------------------------------
FOLLOW_ON_DEEP_DIVE = {
    "id": "followon_deep_dive",
    "title_pattern": "Follow-On Deep Dive — {companies}",
    "required_data": ["companies"],
    "optional_data": ["cap_table_history", "followon_strategy", "scenario_analysis", "fund_context"],
    "sections": [
        _section("investment_history", "Investment History", type="metrics",
                 data_keys=["companies", "cap_table_history"],
                 prompt_hint="Our investment history: entry round, check size, ownership at each round, current marks."),
        _section("cap_table_evolution", "Cap Table Evolution", type="chart",
                 data_keys=["cap_table_history"], chart_type="cap_table_evolution",
                 prompt_hint="Ownership % over funding rounds as stacked area chart. Show founder, ESOP, our fund, others."),
        _section("performance_kpis", "Performance Since Entry", type="metrics",
                 data_keys=["companies"],
                 prompt_hint="Revenue trajectory, customer growth, team scaling, key milestones. Chart preferred."),
        _section("dilution_scenarios", "Dilution Scenarios", type="chart",
                 data_keys=["followon_strategy", "cap_table_history"], chart_type="bar",
                 prompt_hint="3 scenarios: no follow-on, pro-rata, super pro-rata. Ownership at exit for each."),
        _section("exit_modeling", "Exit Scenarios", type="chart",
                 data_keys=["scenario_analysis"], chart_type="breakpoint_chart",
                 prompt_hint="Breakpoint analysis: liquidation preferences, participation caps, value per share class."),
        _section("return_analysis", "Return Analysis", type="metrics",
                 data_keys=["followon_strategy", "scenario_analysis"],
                 prompt_hint="MOIC and IRR under each follow-on scenario × each exit scenario matrix."),
        _section("recommendation", "Recommendation",
                 data_keys=["followon_strategy", "fund_context"],
                 prompt_hint="Follow-on amount, rationale, conditions. Include fund-level reserve impact."),
    ],
}


# ---------------------------------------------------------------------------
# LP Quarterly Enhanced — premium quarterly with better charts
# ---------------------------------------------------------------------------
LP_QUARTERLY_ENHANCED = {
    "id": "lp_quarterly_enhanced",
    "title_pattern": "LP Quarterly Report — {fund_name} — Q{quarter} {year}",
    "required_data": ["fund_context"],
    "optional_data": ["fund_metrics", "portfolio_health", "companies",
                      "reserve_forecast", "exit_modeling", "cap_table_history"],
    "sections": [
        _section("executive_summary", "Executive Summary",
                 data_keys=["fund_metrics", "fund_context"],
                 prompt_hint="Fund performance in 4 bullets: TVPI, DPI, IRR, deployed. Key events this quarter."),
        _section("nav_waterfall", "NAV Waterfall", type="chart",
                 data_keys=["fund_metrics"], chart_type="waterfall",
                 prompt_hint="NAV contribution by company — who drove value up/down this quarter."),
        _section("dpi_sankey", "Distribution Flow", type="chart",
                 data_keys=["fund_metrics", "exit_modeling"], chart_type="dpi_sankey",
                 prompt_hint="Fund → Companies → Exits → LP Distributions. Show realized vs unrealized."),
        _section("portfolio_moic", "Portfolio MOIC", type="chart",
                 data_keys=["portfolio_health"], chart_type="bar",
                 prompt_hint="MOIC by company, sorted descending. Color by quartile."),
        _section("company_updates", "Portfolio Updates",
                 data_keys=["companies", "portfolio_health"],
                 prompt_hint="Per company: ARR, growth %, burn, runway, key milestone. 2-3 sentences each."),
        _section("deployment_pacing", "Deployment Pacing", type="metrics",
                 data_keys=["fund_context", "fund_metrics"],
                 prompt_hint="Deployed vs plan by quarter. Remaining capacity. Expected deployment next 2Q."),
        _section("reserves", "Reserve Status", type="metrics",
                 data_keys=["reserve_forecast"],
                 prompt_hint="Reserves by company, reserve ratio, follow-on priorities."),
        _section("outlook", "Market Outlook",
                 prompt_hint="Macro conditions, sector trends, exit environment, fundraising market."),
    ],
}


# ---------------------------------------------------------------------------
# Market Map — sector landscape with categorized companies
# ---------------------------------------------------------------------------
MARKET_MAP = {
    "id": "market_map",
    "title_pattern": "Market Map — {query_summary}",
    "required_data": [],
    "optional_data": ["companies", "fund_context"],
    "sections": [
        _section("landscape_overview", "Landscape Overview",
                 prompt_hint="What sector/vertical is this? Total market size, growth rate, key trends."),
        _section("category_breakdown", "Market Categories", type="metrics",
                 data_keys=["companies"],
                 prompt_hint="Break the market into 3-6 categories. For each: name, description, key players, estimated size."),
        _section("market_positioning", "Company Positioning", type="chart",
                 data_keys=["companies"], chart_type="scatter_multiples",
                 prompt_hint="Plot companies by revenue/growth with stage coloring. Identify white space."),
        _section("company_profiles", "Key Companies", type="metrics",
                 data_keys=["companies"],
                 prompt_hint="Per company: what they do (factual), stage, revenue, funding, team size, differentiation."),
        _section("funding_landscape", "Funding Activity",
                 data_keys=["companies"],
                 prompt_hint="Recent rounds, total capital deployed, active investors, round sizes by stage."),
        _section("emerging_trends", "Emerging Trends & Opportunities",
                 prompt_hint="What is changing? New entrants, tech shifts, regulatory, buyer behavior."),
        _section("investment_implications", "Investment Implications",
                 data_keys=["companies", "fund_context"],
                 prompt_hint="Opportunities for our fund: underserved segments, timing, entry points."),
    ],
}


# ---------------------------------------------------------------------------
# Citation Report — data provenance and confidence tracking
# ---------------------------------------------------------------------------
CITATION_REPORT = {
    "id": "citation_report",
    "title_pattern": "Data Sources & Citations — {companies}",
    "required_data": ["companies"],
    "optional_data": ["fund_context"],
    "sections": [
        _section("data_summary", "Data Quality Summary", type="metrics",
                 data_keys=["companies"],
                 prompt_hint="Per company: % fields confirmed vs inferred, data confidence, last update date."),
        _section("source_breakdown", "Sources by Company", type="metrics",
                 data_keys=["companies"],
                 prompt_hint="Per company: each data point with source (search, document, manual, inferred), date, confidence."),
        _section("search_sources", "Web Search Sources",
                 data_keys=["companies"],
                 prompt_hint="All URLs, articles, press releases used. Group by company with dates."),
        _section("document_sources", "Document Sources",
                 data_keys=["companies"],
                 prompt_hint="Uploaded documents: name, date, what was extracted, extraction confidence."),
        _section("inferred_data", "Inferred & Estimated Data", type="metrics",
                 data_keys=["companies"],
                 prompt_hint="All inferred values with methodology: stage benchmarks, growth assumptions, confidence."),
        _section("data_gaps", "Remaining Data Gaps",
                 data_keys=["companies"],
                 prompt_hint="What is still missing? Priority gaps, suggested search queries, next steps."),
    ],
}


# ---------------------------------------------------------------------------
# Company List Builder — curated deal flow with enrichment
# ---------------------------------------------------------------------------
COMPANY_LIST = {
    "id": "company_list",
    "title_pattern": "Company List — {query_summary}",
    "required_data": [],
    "optional_data": ["companies", "fund_context"],
    "sections": [
        _section("thesis", "Search Thesis",
                 prompt_hint="What we searched for and why. Sector, stage, geography, key criteria."),
        _section("company_table", "Companies Found", type="metrics",
                 data_keys=["companies"],
                 prompt_hint="Table: company, description, stage, revenue, funding, valuation, team, location."),
        _section("tier_ranking", "Tier Ranking",
                 data_keys=["companies"],
                 prompt_hint="Tier 1 (strong fit), Tier 2 (interesting), Tier 3 (watch). Rationale for each."),
        _section("enrichment_status", "Enrichment Status", type="metrics",
                 data_keys=["companies"],
                 prompt_hint="Per company: data completeness %, fields filled, fields missing, confidence."),
        _section("next_steps", "Next Steps",
                 data_keys=["companies", "fund_context"],
                 prompt_hint="Which to reach out to first, what diligence to run, what data to gather."),
    ],
}


# ---------------------------------------------------------------------------
# Comparable Analysis — comp set with multiples benchmarking
# ---------------------------------------------------------------------------
COMPARABLE_ANALYSIS = {
    "id": "comparable_analysis",
    "title_pattern": "Comparable Analysis — {companies}",
    "required_data": ["companies"],
    "optional_data": ["fund_context", "scenario_analysis"],
    "sections": [
        _section("target_overview", "Target Company", type="metrics",
                 data_keys=["companies"],
                 prompt_hint="Target overview: what they do, stage, revenue, growth, valuation."),
        _section("comp_selection", "Comparable Selection",
                 data_keys=["companies"],
                 prompt_hint="Why these comps: similar business model, stage, sector, GTM, customer profile."),
        _section("multiples_table", "Multiples Comparison", type="metrics",
                 data_keys=["companies"],
                 prompt_hint="Table: company, EV/Revenue, EV/ARR, growth, gross margin, stage. Include median."),
        _section("scatter_positioning", "Market Positioning", type="chart",
                 data_keys=["companies"], chart_type="scatter_multiples",
                 prompt_hint="Plot comps on growth vs multiple. Where does target sit?"),
        _section("implied_valuation", "Implied Valuation", type="metrics",
                 data_keys=["companies"],
                 prompt_hint="Apply comp multiples to target: median, 25th, 75th percentile valuations."),
        _section("key_differences", "Key Differences",
                 data_keys=["companies"],
                 prompt_hint="Where target differs: premium/discount justified by moat, growth, margin."),
    ],
}


# ---------------------------------------------------------------------------
# Portfolio Review — fund-level health check across all active companies
# ---------------------------------------------------------------------------
PORTFOLIO_REVIEW = {
    "id": "portfolio_review",
    "title_pattern": "Portfolio Review — {fund_name} Q{quarter} {year}",
    "required_data": ["companies"],
    "optional_data": [
        "fund_context", "portfolio_analysis", "scenario_analysis",
        "cap_table_history", "revenue_projections", "followon_strategy",
    ],
    "sections": [
        _section("executive_summary", "Executive Summary",
                 data_keys=["companies", "portfolio_analysis", "fund_context"],
                 prompt_hint=(
                     "3-4 bullets: total NAV, MOIC to date, number of companies by stage, "
                     "capital deployed vs remaining. Lead with the headline number."
                 )),
        _section("portfolio_snapshot", "Portfolio Snapshot", type="chart",
                 data_keys=["companies", "portfolio_analysis"],
                 chart_type="portfolio_scatter",
                 prompt_hint="Revenue vs valuation scatter; bubble size = our ownership %."),
        _section("cohort_analysis", "Cohort Analysis",
                 data_keys=["companies", "portfolio_analysis"],
                 prompt_hint=(
                     "Group companies by entry stage (Seed, Series A, B, C). "
                     "For each cohort: count, median MOIC, median revenue growth, "
                     "capital deployed. Which cohort is outperforming?"
                 )),
        _section("cohort_revenue_curves", "Revenue Trajectories", type="chart",
                 data_keys=["companies", "revenue_projections"],
                 chart_type="cohort_revenue_chart",
                 prompt_hint="ARR over time by stage cohort."),
        _section("at_risk", "At-Risk Companies",
                 data_keys=["companies", "portfolio_analysis"],
                 prompt_hint=(
                     "Companies with <6 months runway, declining growth, or down-round risk. "
                     "For each: problem, board action, timeline."
                 )),
        _section("exit_pipeline", "Exit Pipeline",
                 data_keys=["companies", "scenario_analysis", "portfolio_analysis"],
                 prompt_hint=(
                     "Companies likely to exit in next 18 months via IPO or M&A. "
                     "For each: expected exit value, our ownership at exit, proceeds to fund."
                 )),
        _section("fund_return_waterfall", "Fund Return Waterfall", type="chart",
                 data_keys=["companies", "portfolio_analysis", "scenario_analysis"],
                 chart_type="fund_return_waterfall_chart",
                 prompt_hint="Proceeds by company across base exit scenario."),
        _section("fund_scenarios", "Fund-Level Scenarios",
                 data_keys=["portfolio_analysis", "scenario_analysis", "fund_context"],
                 prompt_hint=(
                     "Bear / Base / Bull for the whole fund: total proceeds, MOIC, DPI. "
                     "Key sensitivities: top-2 companies drive X% of returns."
                 )),
        _section("followon_priority", "Follow-On Priority",
                 data_keys=["companies", "followon_strategy", "portfolio_analysis"],
                 prompt_hint=(
                     "Rank active companies by IRR impact of exercising pro-rata. "
                     "Show: company, round size, our pro-rata, ownership delta, expected IRR lift. "
                     "Blended against remaining capital."
                 )),
    ],
}


# ---------------------------------------------------------------------------
# Registry — lookup by ID
# ---------------------------------------------------------------------------
MEMO_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "ic_memo": IC_MEMO,
    "investment": IC_MEMO,                    # alias
    "followon": FOLLOWON_MEMO,
    "follow_on": FOLLOWON_MEMO,               # alias
    "lp_report": LP_REPORT,
    "lp_quarterly": LP_REPORT,                # alias
    "gp_strategy": GP_UPDATE,
    "gp_update": GP_UPDATE,                   # alias
    "comparison": COMPARISON_REPORT,
    "bespoke_lp": BESPOKE_LP_RESPONSE,
    "fund_analysis": FUND_ANALYSIS,
    "ownership_analysis": OWNERSHIP_ANALYSIS,
    "plan_memo": PLAN_MEMO,
    "plan": PLAN_MEMO,                        # alias
    "diligence_memo": DILIGENCE_MEMO,
    "diligence": DILIGENCE_MEMO,              # alias
    # --- New templates ---
    "team_comparison": TEAM_COMPARISON,
    "team": TEAM_COMPARISON,                   # alias
    "market_dynamics": MARKET_DYNAMICS,
    "market": MARKET_DYNAMICS,                 # alias
    "portfolio_construction": PORTFOLIO_CONSTRUCTION,
    "construction": PORTFOLIO_CONSTRUCTION,    # alias
    "pipeline_review": PIPELINE_REVIEW,
    "pipeline": PIPELINE_REVIEW,               # alias
    "competitive_landscape": COMPETITIVE_LANDSCAPE,
    "competitive": COMPETITIVE_LANDSCAPE,      # alias
    "followon_deep_dive": FOLLOW_ON_DEEP_DIVE,
    "followon_deep": FOLLOW_ON_DEEP_DIVE,      # alias
    "lp_quarterly_enhanced": LP_QUARTERLY_ENHANCED,
    "lp_enhanced": LP_QUARTERLY_ENHANCED,      # alias
    # --- Phase 7 templates ---
    "market_map": MARKET_MAP,
    "market_landscape": MARKET_MAP,             # alias
    "citation_report": CITATION_REPORT,
    "citations": CITATION_REPORT,               # alias
    "data_sources": CITATION_REPORT,            # alias
    "company_list": COMPANY_LIST,
    "deal_flow": COMPANY_LIST,                  # alias
    "comparable_analysis": COMPARABLE_ANALYSIS,
    "comp_analysis": COMPARABLE_ANALYSIS,       # alias
    "portfolio_review": PORTFOLIO_REVIEW,
    "portfolio": PORTFOLIO_REVIEW,              # alias
    "fund_review": PORTFOLIO_REVIEW,            # alias
}

# Intent keyword → template ID mapping for auto-detection
INTENT_TO_TEMPLATE: Dict[str, str] = {
    "ic memo": "ic_memo",
    "investment memo": "ic_memo",
    "investment committee": "ic_memo",
    "follow-on": "followon",
    "follow on": "followon",
    "followon": "followon",
    "pro-rata": "followon",
    "pro rata": "followon",
    "lp report": "lp_report",
    "lp quarterly": "lp_report",
    "quarterly report": "lp_report",
    "gp strategy": "gp_strategy",
    "gp update": "gp_strategy",
    "gp deck": "gp_strategy",
    "strategy update": "gp_strategy",
    "compare": "comparison",
    "comparison": "comparison",
    "side-by-side": "comparison",
    "side by side": "comparison",
    "vs": "comparison",
    "fund analysis": "fund_analysis",
    "fund waterfall": "fund_analysis",
    "fund returns": "fund_analysis",
    "lp/gp": "fund_analysis",
    "ownership": "ownership_analysis",
    "cap table evolution": "ownership_analysis",
    "dilution": "ownership_analysis",
    "ownership projection": "ownership_analysis",
    "plan": "plan_memo",
    "execution plan": "plan_memo",
    "do this plan": "plan_memo",
    "our exposure": "bespoke_lp",
    "lp question": "bespoke_lp",
    "why did we": "bespoke_lp",
    "why didn't we": "bespoke_lp",
    "why did we pass": "bespoke_lp",
    "what is our": "bespoke_lp",
    # --- New template intents ---
    "team comparison": "team_comparison",
    "compare teams": "team_comparison",
    "founding team": "team_comparison",
    "team analysis": "team_comparison",
    "market dynamics": "market_dynamics",
    "market analysis": "market_dynamics",
    "competitive landscape": "competitive_landscape",
    "competitors": "competitive_landscape",
    "competitive analysis": "competitive_landscape",
    "who competes": "competitive_landscape",
    "portfolio construction": "portfolio_construction",
    "concentration": "portfolio_construction",
    "allocation": "portfolio_construction",
    "portfolio fitness": "portfolio_construction",
    "pipeline": "pipeline_review",
    "deal flow": "pipeline_review",
    "pipeline review": "pipeline_review",
    "sourcing": "pipeline_review",
    "follow-on deep dive": "followon_deep_dive",
    "followon deep dive": "followon_deep_dive",
    "deep follow-on": "followon_deep_dive",
    "follow-on analysis": "followon_deep_dive",
    "cap table evolution": "followon_deep_dive",
    "breakpoint analysis": "followon_deep_dive",
    "enhanced quarterly": "lp_quarterly_enhanced",
    "lp quarterly enhanced": "lp_quarterly_enhanced",
    "premium quarterly": "lp_quarterly_enhanced",
    "quarterly with charts": "lp_quarterly_enhanced",
    "dpi": "lp_quarterly_enhanced",
    "what's our dpi": "lp_quarterly_enhanced",
    # --- Phase 7 intent mappings ---
    "market map": "market_map",
    "sector map": "market_map",
    "landscape map": "market_map",
    "market landscape": "market_map",
    "sector landscape": "market_map",
    "citations": "citation_report",
    "data sources": "citation_report",
    "where did we get": "citation_report",
    "data quality": "citation_report",
    "citation report": "citation_report",
    "company list": "company_list",
    "build list": "company_list",
    "deal flow list": "company_list",
    "sourcing list": "company_list",
    "comparable analysis": "comparable_analysis",
    "comp analysis": "comparable_analysis",
    "comparables": "comparable_analysis",
    "comp set": "comparable_analysis",
    "portfolio review": "portfolio_review",
    "fund review": "portfolio_review",
    "portfolio health": "portfolio_review",
    "at risk": "portfolio_review",
    "exit pipeline": "portfolio_review",
    "portfolio update": "portfolio_review",
    "how is our portfolio": "portfolio_review",
    "how is the portfolio": "portfolio_review",
}
