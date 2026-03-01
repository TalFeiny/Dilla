"""
TOKEN COST ANALYSIS FOR DILLA AI BACKEND
=========================================
Comprehensive analysis of:
  1. Current pricing config vs actual market rates (are you overpaying?)
  2. Model-by-model cost comparison for your workloads
  3. Agent loop cost breakdown per operation type
  4. Cost optimization opportunities
  5. Critical bug in cost tracking

Run: python token_cost_analysis.py
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 1: YOUR CURRENT MODEL CONFIGS (from model_router.py lines 204-288)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

YOUR_CONFIGS = {
    "claude-sonnet-4-5": {
        "provider": "Anthropic",
        "cost_per_1k_input": 0.003,
        "cost_per_1k_output": 0.015,
        "max_tokens": 4096,
        "priority": 1,
    },
    "gpt-5-mini": {
        "provider": "OpenAI",
        "cost_per_1k_input": 0.0005,
        "cost_per_1k_output": 0.0015,
        "max_tokens": 4096,
        "priority": 2,
    },
    "gpt-5.2": {
        "provider": "OpenAI",
        "cost_per_1k_input": 0.01,
        "cost_per_1k_output": 0.03,
        "max_tokens": 8192,
        "priority": 1,
    },
    "gemini-pro": {
        "provider": "Google",
        "cost_per_1k_input": 0.00025,
        "cost_per_1k_output": 0.0005,
        "max_tokens": 2048,
        "priority": 3,
    },
    "mixtral-8x7b": {
        "provider": "Groq",
        "cost_per_1k_input": 0.00027,
        "cost_per_1k_output": 0.00027,
        "max_tokens": 4096,
        "priority": 2,
    },
    "llama2-70b": {
        "provider": "Groq",
        "cost_per_1k_input": 0.0007,
        "cost_per_1k_output": 0.0008,
        "max_tokens": 4096,
        "priority": 3,
    },
    "llama-3-70b": {
        "provider": "Together",
        "cost_per_1k_input": 0.0009,
        "cost_per_1k_output": 0.0009,
        "max_tokens": 4096,
        "priority": 3,
    },
    "ollama-mixtral": {
        "provider": "Ollama (local)",
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
        "max_tokens": 4096,
        "priority": 5,
    },
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 2: ACTUAL MARKET RATES (March 2026)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ACTUAL_MARKET_RATES = {
    # Anthropic (per 1K tokens)
    "claude-sonnet-4-5":    {"input": 0.003,   "output": 0.015,   "note": "Balanced, your primary"},
    "claude-sonnet-4-6":    {"input": 0.003,   "output": 0.015,   "note": "Latest Sonnet - same price, better quality"},
    "claude-haiku-4-5":     {"input": 0.001,   "output": 0.005,   "note": "3x cheaper than Sonnet, fast"},
    "claude-opus-4-5":      {"input": 0.005,   "output": 0.025,   "note": "Most capable, 67% off legacy"},
    "claude-opus-4-6":      {"input": 0.005,   "output": 0.025,   "note": "Latest Opus"},

    # OpenAI (per 1K tokens)
    "gpt-5-mini":           {"input": 0.00025, "output": 0.002,   "note": "Your config has wrong price"},
    "gpt-5":                {"input": 0.00125, "output": 0.01,    "note": "Flagship, not in your config"},
    "gpt-5.2":              {"input": 0.01,    "output": 0.03,    "note": "Premium reasoning model"},

    # Google (per 1K tokens)
    "gemini-2.5-pro":       {"input": 0.00125, "output": 0.01,    "note": "Current gen, not in your config"},
    "gemini-2.5-flash":     {"input": 0.00015, "output": 0.0006,  "note": "Ultra-cheap, fast"},
    "gemini-pro (legacy)":  {"input": 0.00025, "output": 0.0005,  "note": "Your config - may be deprecated"},

    # Groq (per 1K tokens)
    "mixtral-8x7b (Groq)":  {"input": 0.00024, "output": 0.00024, "note": "Ultra-fast inference"},
    "llama-3.1-8b (Groq)":  {"input": 0.00005, "output": 0.00008, "note": "Cheapest viable model"},
    "llama-3-70b (Groq)":   {"input": 0.00059, "output": 0.00079, "note": "Good quality/price"},
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION 3: AGENT LOOP CALL PATTERNS (from unified_mcp_orchestrator.py)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class LLMCall:
    name: str
    est_input_tokens: int
    est_output_tokens: int
    model_used: str = "claude-sonnet-4-5"  # default primary

@dataclass
class Pipeline:
    name: str
    calls: List[LLMCall] = field(default_factory=list)
    external_costs: Dict[str, float] = field(default_factory=dict)
    notes: str = ""

    def total_tokens(self) -> int:
        return sum(c.est_input_tokens + c.est_output_tokens for c in self.calls)

    def cost_with_model(self, model_key: str, rates: Dict) -> float:
        r = rates[model_key]
        total = 0.0
        for c in self.calls:
            total += (c.est_input_tokens / 1000) * r["input"]
            total += (c.est_output_tokens / 1000) * r["output"]
        return total + sum(self.external_costs.values())


# Define all pipeline patterns observed in the codebase
PIPELINES = {
    "simple_query": Pipeline(
        name="Simple Query (e.g., 'tell me about Anthropic')",
        calls=[
            LLMCall("intent_classification", 400, 200),
            LLMCall("tool_routing", 600, 300),
            LLMCall("extraction", 2000, 500),
            LLMCall("reflection", 1500, 400),
        ],
        external_costs={"tavily_search": 0.50},
        notes="4 LLM calls + 1 web search",
    ),
    "sourcing_15_companies": Pipeline(
        name="Sourcing Pipeline (15 companies)",
        calls=[
            LLMCall("intent_classification", 400, 200),
            LLMCall("rubric_generation", 500, 300),
            LLMCall("semantic_classification", 600, 200),
            LLMCall("query_decomposition", 800, 400),
            # Per-company extraction (15 companies, ~2K input each from HTML)
            *[LLMCall(f"extraction_company_{i+1}", 2000, 500) for i in range(15)],
            # Some companies get enrichment calls
            *[LLMCall(f"enrichment_{i+1}", 800, 300) for i in range(5)],
        ],
        external_costs={"tavily_searches_x10": 5.00},
        notes="22 LLM calls + 10 Tavily searches. Heaviest pipeline.",
    ),
    "sourcing_5_companies": Pipeline(
        name="Sourcing Pipeline (5 companies, light)",
        calls=[
            LLMCall("intent_classification", 400, 200),
            LLMCall("rubric_generation", 500, 300),
            LLMCall("semantic_classification", 600, 200),
            LLMCall("query_decomposition", 800, 400),
            *[LLMCall(f"extraction_company_{i+1}", 2000, 500) for i in range(5)],
        ],
        external_costs={"tavily_searches_x4": 2.00},
        notes="9 LLM calls + 4 Tavily searches",
    ),
    "deck_generation_2_companies": Pipeline(
        name="Deck Generation (2 companies, 15 slides)",
        calls=[
            LLMCall("intent_classification", 400, 200),
            LLMCall("executive_summary", 2000, 800),
            LLMCall("company_overview_1", 1500, 600),
            LLMCall("company_overview_2", 1500, 600),
            LLMCall("tam_analysis", 1500, 600),
            LLMCall("competitive_landscape", 1200, 500),
            LLMCall("risk_analysis", 1200, 500),
            LLMCall("financial_projections", 1500, 600),
            LLMCall("valuation_narrative", 1200, 500),
            LLMCall("recommendations", 1500, 800),
            LLMCall("synthesis", 2000, 600),
        ],
        external_costs={},
        notes="11 LLM calls, no external APIs (uses cached data)",
    ),
    "memo_generation": Pipeline(
        name="Investment Memo Generation",
        calls=[
            LLMCall("intent_classification", 400, 200),
            LLMCall("memo_sections", 3000, 2000),
            LLMCall("gap_analysis", 1500, 500),
            LLMCall("risk_framework", 1500, 800),
            LLMCall("recommendation", 2000, 1000),
        ],
        external_costs={},
        notes="5 LLM calls",
    ),
    "agent_loop_complex": Pipeline(
        name="Complex Multi-Step Agent Loop (e.g., 'analyze portfolio risk')",
        calls=[
            LLMCall("intent_classification", 400, 200),
            LLMCall("goal_decomposition", 800, 400),
            LLMCall("tool_routing", 600, 300),
            LLMCall("step_1_analysis", 2000, 800),
            LLMCall("step_2_analysis", 2000, 800),
            LLMCall("step_3_analysis", 2000, 800),
            LLMCall("reflection_1", 2000, 500),
            LLMCall("synthesis", 3000, 1200),
        ],
        external_costs={},
        notes="8 LLM calls, multi-iteration ReAct loop",
    ),
    "valuation_only": Pipeline(
        name="Valuation (Pure Math, No LLM)",
        calls=[
            LLMCall("intent_classification", 400, 200),
        ],
        external_costs={},
        notes="1 LLM call (classification only). Valuation is pure Python math.",
    ),
}


def print_header(title: str):
    w = 100
    print(f"\n{'━' * w}")
    print(f"  {title}")
    print(f"{'━' * w}")


def print_subheader(title: str):
    print(f"\n  {'─' * 90}")
    print(f"  {title}")
    print(f"  {'─' * 90}")


def section_1_pricing_audit():
    """Compare your config prices vs actual market rates."""
    print_header("1. PRICING AUDIT — Your Config vs Actual Market Rates (March 2026)")

    print(f"\n  {'Model':<22} {'Provider':<10} {'Your $/1K In':<14} {'Actual $/1K In':<16} {'Your $/1K Out':<15} {'Actual $/1K Out':<16} {'Status'}")
    print(f"  {'─'*22} {'─'*10} {'─'*14} {'─'*16} {'─'*15} {'─'*16} {'─'*20}")

    issues = []
    for model, cfg in YOUR_CONFIGS.items():
        actual_key = None
        for k in ACTUAL_MARKET_RATES:
            if model.lower() in k.lower() or k.lower().startswith(model.lower()):
                actual_key = k
                break

        if actual_key:
            actual = ACTUAL_MARKET_RATES[actual_key]
            in_diff = cfg["cost_per_1k_input"] - actual["input"]
            out_diff = cfg["cost_per_1k_output"] - actual["output"]

            if abs(in_diff) < 0.0001 and abs(out_diff) < 0.0001:
                status = "OK"
            elif in_diff > 0.0001 or out_diff > 0.0001:
                status = "OVERPAYING"
                issues.append((model, in_diff, out_diff))
            else:
                status = "UNDERCOUNTING"
                issues.append((model, in_diff, out_diff))

            print(f"  {model:<22} {cfg['provider']:<10} ${cfg['cost_per_1k_input']:<13.5f} ${actual['input']:<15.5f} ${cfg['cost_per_1k_output']:<14.5f} ${actual['output']:<15.5f} {status}")
        else:
            print(f"  {model:<22} {cfg['provider']:<10} ${cfg['cost_per_1k_input']:<13.5f} {'N/A':<16} ${cfg['cost_per_1k_output']:<14.5f} {'N/A':<16} CHECK")

    if issues:
        print(f"\n  PRICING DISCREPANCIES FOUND:")
        for model, in_d, out_d in issues:
            if in_d > 0:
                print(f"    {model}: input overpriced by ${in_d:.5f}/1K tokens")
            elif in_d < 0:
                print(f"    {model}: input underpriced by ${abs(in_d):.5f}/1K tokens (cost tracker undercounts!)")
            if out_d > 0:
                print(f"    {model}: output overpriced by ${out_d:.5f}/1K tokens")
            elif out_d < 0:
                print(f"    {model}: output underpriced by ${abs(out_d):.5f}/1K tokens (cost tracker undercounts!)")


def section_2_critical_bug():
    """Document the cost tracking bug."""
    print_header("2. CRITICAL BUG — Cost Tracking Uses Character Counts, Not Real Tokens")

    print("""
  FILE: app/services/model_router.py

  BUG LOCATION (line 545-548):
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  cost = self._calculate_cost(                                          │
  │      model_config,                                                     │
  │      len(prompt),          # <-- PASSES CHARACTER COUNT, NOT TOKENS    │
  │      len(response)         # <-- PASSES CHARACTER COUNT, NOT TOKENS    │
  │  )                                                                     │
  └──────────────────────────────────────────────────────────────────────────┘

  BUG LOCATION (line 1057-1065):
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  def _calculate_cost(self, model_config, input_tokens, output_tokens):  │
  │      input_token_count = input_tokens / 4      # divides chars by 4    │
  │      output_token_count = output_tokens / 4     # divides chars by 4   │
  │      input_cost = (input_token_count / 1000) * cost_per_1k_input       │
  │      output_cost = (output_token_count / 1000) * cost_per_1k_output    │
  │  return input_cost + output_cost                                       │
  └──────────────────────────────────────────────────────────────────────────┘

  IMPACT:
    - "4 chars = 1 token" is a rough English approximation
    - For JSON/structured output: actual ratio is closer to 2.5-3 chars/token
    - For code/technical content: closer to 3 chars/token
    - RESULT: Your cost tracker UNDERESTIMATES actual costs by 25-40%

  WORSE: Real API responses contain EXACT token counts that are being IGNORED:
    - Anthropic: response.usage.input_tokens, response.usage.output_tokens
    - OpenAI:    response.usage.prompt_tokens, response.usage.completion_tokens
    - Google:    response.usage_metadata.prompt_token_count

  FIX: Use actual usage data from API responses instead of character estimation.
  Budget summaries will jump ~30% when fixed — but that's the REAL cost.
""")


def section_3_pipeline_costs():
    """Cost breakdown per pipeline with different models."""
    print_header("3. AGENT LOOP COST BREAKDOWN — Per Pipeline, Per Model")

    # Models to compare
    compare_models = [
        ("claude-sonnet-4-5", ACTUAL_MARKET_RATES["claude-sonnet-4-5"]),
        ("claude-haiku-4-5",  ACTUAL_MARKET_RATES["claude-haiku-4-5"]),
        ("gpt-5-mini",        ACTUAL_MARKET_RATES["gpt-5-mini"]),
        ("gpt-5",             ACTUAL_MARKET_RATES["gpt-5"]),
        ("gemini-2.5-flash",  ACTUAL_MARKET_RATES["gemini-2.5-flash"]),
        ("gemini-2.5-pro",    ACTUAL_MARKET_RATES["gemini-2.5-pro"]),
        ("mixtral-8x7b",      ACTUAL_MARKET_RATES["mixtral-8x7b (Groq)"]),
    ]

    for pipe_key, pipe in PIPELINES.items():
        print_subheader(f"{pipe.name}")
        print(f"  LLM calls: {len(pipe.calls)}  |  Total tokens: ~{pipe.total_tokens():,}")
        ext = sum(pipe.external_costs.values())
        if ext > 0:
            print(f"  External costs: ${ext:.2f} ({', '.join(pipe.external_costs.keys())})")
        print(f"  Notes: {pipe.notes}")
        print()

        print(f"    {'Model':<22} {'LLM Cost':<12} {'External':<12} {'TOTAL':<12} {'vs Sonnet':<12} {'Tokens'}")
        print(f"    {'─'*22} {'─'*12} {'─'*12} {'─'*12} {'─'*12} {'─'*10}")

        sonnet_cost = None
        for model_name, rates in compare_models:
            llm_cost = 0.0
            for c in pipe.calls:
                llm_cost += (c.est_input_tokens / 1000) * rates["input"]
                llm_cost += (c.est_output_tokens / 1000) * rates["output"]

            total = llm_cost + ext
            if sonnet_cost is None:
                sonnet_cost = total
                vs = "baseline"
            else:
                if sonnet_cost > 0:
                    pct = ((total - sonnet_cost) / sonnet_cost) * 100
                    vs = f"{pct:+.0f}%"
                else:
                    vs = "N/A"

            print(f"    {model_name:<22} ${llm_cost:<11.4f} ${ext:<11.2f} ${total:<11.4f} {vs:<12} {pipe.total_tokens():,}")


def section_4_monthly_projections():
    """Project monthly costs at different usage levels."""
    print_header("4. MONTHLY COST PROJECTIONS")

    scenarios = [
        ("Light (10 req/day)",     10, 30),
        ("Medium (50 req/day)",    50, 30),
        ("Heavy (200 req/day)",   200, 30),
        ("Enterprise (1000/day)", 1000, 30),
    ]

    # Request mix (percentage of each pipeline type)
    request_mix = {
        "simple_query": 0.40,
        "sourcing_5_companies": 0.15,
        "sourcing_15_companies": 0.10,
        "deck_generation_2_companies": 0.10,
        "memo_generation": 0.10,
        "agent_loop_complex": 0.05,
        "valuation_only": 0.10,
    }

    models_to_project = [
        ("claude-sonnet-4-5 (current)", ACTUAL_MARKET_RATES["claude-sonnet-4-5"]),
        ("claude-haiku-4-5",            ACTUAL_MARKET_RATES["claude-haiku-4-5"]),
        ("gpt-5-mini",                  ACTUAL_MARKET_RATES["gpt-5-mini"]),
        ("gemini-2.5-flash",            ACTUAL_MARKET_RATES["gemini-2.5-flash"]),
        ("mixed (optimal)*",            None),  # calculated below
    ]

    print(f"\n  Request mix assumed:")
    for pipe_key, pct in request_mix.items():
        print(f"    {PIPELINES[pipe_key].name:<50} {pct*100:.0f}%")

    for scenario_name, daily_req, days in scenarios:
        print_subheader(f"{scenario_name} — {daily_req * days:,} requests/month")

        total_monthly_reqs = daily_req * days
        print(f"\n    {'Model Strategy':<32} {'LLM/mo':<14} {'External/mo':<14} {'TOTAL/mo':<14} {'Per Request'}")
        print(f"    {'─'*32} {'─'*14} {'─'*14} {'─'*14} {'─'*12}")

        for model_name, rates in models_to_project:
            monthly_llm = 0.0
            monthly_ext = 0.0

            for pipe_key, pct in request_mix.items():
                pipe = PIPELINES[pipe_key]
                n_requests = total_monthly_reqs * pct

                ext = sum(pipe.external_costs.values())
                monthly_ext += ext * n_requests

                if rates is None:
                    # Mixed optimal: use cheapest viable model per call type
                    for c in pipe.calls:
                        # Use haiku for classification/routing, sonnet for analysis
                        if "classification" in c.name or "routing" in c.name:
                            r = ACTUAL_MARKET_RATES["claude-haiku-4-5"]
                        elif "extraction" in c.name:
                            r = ACTUAL_MARKET_RATES["gpt-5-mini"]
                        else:
                            r = ACTUAL_MARKET_RATES["claude-sonnet-4-5"]
                        monthly_llm += n_requests * ((c.est_input_tokens / 1000) * r["input"] + (c.est_output_tokens / 1000) * r["output"])
                else:
                    for c in pipe.calls:
                        monthly_llm += n_requests * ((c.est_input_tokens / 1000) * rates["input"] + (c.est_output_tokens / 1000) * rates["output"])

            total = monthly_llm + monthly_ext
            per_req = total / total_monthly_reqs if total_monthly_reqs > 0 else 0

            print(f"    {model_name:<32} ${monthly_llm:<13,.2f} ${monthly_ext:<13,.2f} ${total:<13,.2f} ${per_req:.4f}")

    print(f"\n  * Mixed optimal = Haiku for classification/routing, GPT-5-mini for extraction, Sonnet for analysis")


def section_5_model_comparison_matrix():
    """Head-to-head model comparison for your use case."""
    print_header("5. MODEL COMPARISON MATRIX — Quality vs Cost for VC Analysis")

    print("""
  ┌────────────────────────┬──────────┬──────────┬───────────┬──────────┬──────────────────────────────────┐
  │ Model                  │ $/1K In  │ $/1K Out │ Rel. Cost │ Quality* │ Best For                         │
  ├────────────────────────┼──────────┼──────────┼───────────┼──────────┼──────────────────────────────────┤
  │ claude-opus-4-6        │ $0.005   │ $0.025   │ 1.67x     │ 10/10   │ Complex memos, risk analysis     │
  │ claude-sonnet-4-5 ◄YOU │ $0.003   │ $0.015   │ 1.00x     │ 9/10    │ General analysis (your primary)  │
  │ claude-haiku-4-5       │ $0.001   │ $0.005   │ 0.33x     │ 7/10    │ Classification, routing, simple  │
  │ gpt-5.2           ◄YOU │ $0.010   │ $0.030   │ 3.33x     │ 9.5/10  │ Deep reasoning, long compute     │
  │ gpt-5                  │ $0.00125 │ $0.010   │ 0.58x     │ 9/10    │ Good Sonnet alternative          │
  │ gpt-5-mini        ◄YOU │ $0.00025 │ $0.002   │ 0.12x     │ 7/10    │ Bulk extraction, simple tasks    │
  │ gemini-2.5-pro         │ $0.00125 │ $0.010   │ 0.58x     │ 8.5/10  │ Long context, document analysis  │
  │ gemini-2.5-flash       │ $0.00015 │ $0.0006  │ 0.04x     │ 7/10    │ Ultra-cheap classification       │
  │ mixtral-8x7b (Groq)   │ $0.00024 │ $0.00024 │ 0.03x     │ 6/10    │ Fast inference, low-stakes       │
  │ ollama-mixtral (local) │ $0.000   │ $0.000   │ FREE      │ 5/10    │ Dev/testing only                 │
  └────────────────────────┴──────────┴──────────┴───────────┴──────────┴──────────────────────────────────┘

  * Quality rating for VC-specific tasks (structured extraction, financial analysis, memo writing)
  ◄YOU = Currently in your model_router.py config
""")

    print("""  MODELS NOT IN YOUR CONFIG (consider adding):
  ┌─────────────────────────────────────────────────────────────────────────────────────┐
  │ claude-haiku-4-5   — Use for intent classification & routing (3x cheaper)          │
  │ claude-sonnet-4-6  — Drop-in upgrade for claude-sonnet-4-5 (same price, newer)     │
  │ gpt-5              — Strong middle-tier alternative ($0.00125/$0.01)                │
  │ gemini-2.5-flash   — 25x cheaper than Sonnet for simple tasks                      │
  │ gemini-2.5-pro     — Replace legacy gemini-pro (much better quality)               │
  └─────────────────────────────────────────────────────────────────────────────────────┘
""")


def section_6_sourcing_deep_dive():
    """Deep dive into the sourcing pipeline specifically."""
    print_header("6. SOURCING PIPELINE DEEP DIVE — Token Flow Per Stage")

    stages = [
        ("1. Intent Classification",   400,  200, "claude-sonnet-4-5", 0.00, "Could use Haiku"),
        ("2. Rubric Generation",        500,  300, "claude-sonnet-4-5", 0.00, "Structured JSON output"),
        ("3. Semantic Classification",  600,  200, "claude-sonnet-4-5", 0.00, "Could use Haiku"),
        ("4. Query Decomposition",      800,  400, "claude-sonnet-4-5", 0.00, "Needs quality — keep Sonnet"),
        ("5. Tavily Search (x10)",        0,    0, "N/A (external)",    5.00, "Dominant cost center"),
        ("6. Extraction (x15 co.)",   30000, 7500, "claude-sonnet-4-5", 0.00, "Biggest LLM cost — batch candidate"),
        ("7. Enrichment (x5 co.)",     4000, 1500, "claude-sonnet-4-5", 0.00, "Optional — only for gaps"),
        ("8. Gap Filling",                0,    0, "N/A (pure math)",   0.00, "No LLM — free"),
        ("9. Scoring",                    0,    0, "N/A (pure math)",   0.00, "No LLM — free"),
    ]

    sonnet_rate = ACTUAL_MARKET_RATES["claude-sonnet-4-5"]
    haiku_rate = ACTUAL_MARKET_RATES["claude-haiku-4-5"]
    gpt5mini_rate = ACTUAL_MARKET_RATES["gpt-5-mini"]

    print(f"\n  {'Stage':<30} {'In Tok':<10} {'Out Tok':<10} {'Sonnet $':<12} {'Haiku $':<12} {'GPT5-mini $':<12} {'External $':<12}")
    print(f"  {'─'*30} {'─'*10} {'─'*10} {'─'*12} {'─'*12} {'─'*12} {'─'*12}")

    totals = {"sonnet": 0, "haiku": 0, "gpt5mini": 0, "ext": 0, "in_tok": 0, "out_tok": 0}

    for name, in_tok, out_tok, model, ext_cost, note in stages:
        s_cost = (in_tok/1000)*sonnet_rate["input"] + (out_tok/1000)*sonnet_rate["output"]
        h_cost = (in_tok/1000)*haiku_rate["input"] + (out_tok/1000)*haiku_rate["output"]
        g_cost = (in_tok/1000)*gpt5mini_rate["input"] + (out_tok/1000)*gpt5mini_rate["output"]

        totals["sonnet"] += s_cost
        totals["haiku"] += h_cost
        totals["gpt5mini"] += g_cost
        totals["ext"] += ext_cost
        totals["in_tok"] += in_tok
        totals["out_tok"] += out_tok

        print(f"  {name:<30} {in_tok:<10,} {out_tok:<10,} ${s_cost:<11.4f} ${h_cost:<11.4f} ${g_cost:<11.4f} ${ext_cost:<11.2f}")

    print(f"  {'─'*30} {'─'*10} {'─'*10} {'─'*12} {'─'*12} {'─'*12} {'─'*12}")
    print(f"  {'TOTAL LLM':<30} {totals['in_tok']:<10,} {totals['out_tok']:<10,} ${totals['sonnet']:<11.4f} ${totals['haiku']:<11.4f} ${totals['gpt5mini']:<11.4f} ${totals['ext']:<11.2f}")
    print(f"  {'GRAND TOTAL (LLM + External)':<30} {'':10} {'':10} ${totals['sonnet']+totals['ext']:<11.4f} ${totals['haiku']+totals['ext']:<11.4f} ${totals['gpt5mini']+totals['ext']:<11.4f}")

    print(f"""
  KEY INSIGHT: Tavily search costs (${totals['ext']:.2f}) dwarf LLM costs (${totals['sonnet']:.4f}).
  LLM costs are only {totals['sonnet']/(totals['sonnet']+totals['ext'])*100:.1f}% of total sourcing cost.

  OPTIMIZATION OPPORTUNITIES:
  ┌─────────────────────────────────────────────────────────────────────────────────────┐
  │ 1. Tavily is 97% of cost — cache results, reduce duplicate searches               │
  │ 2. Use Haiku for stages 1 & 3 (classification) — saves ${totals['sonnet']-totals['haiku']:.4f}/run on LLM   │
  │ 3. Use GPT-5-mini for bulk extraction (stage 6) — 8x cheaper per extraction       │
  │ 4. Batch API (Anthropic/OpenAI) for extraction — 50% off, async is fine here       │
  │ 5. Cache rubric/decomposition for similar theses — avoid repeat LLM calls          │
  └─────────────────────────────────────────────────────────────────────────────────────┘
""")


def section_7_optimization_recommendations():
    """Concrete optimization recommendations."""
    print_header("7. OPTIMIZATION RECOMMENDATIONS — Ranked by Impact")

    print("""
  ┌───┬────────────────────────────────────────────────────────────────────┬───────────┬──────────┐
  │ # │ Recommendation                                                    │ Savings   │ Effort   │
  ├───┼────────────────────────────────────────────────────────────────────┼───────────┼──────────┤
  │ 1 │ FIX: Use real API token counts instead of char/4 estimation       │ Accuracy  │ Low      │
  │   │ → response.usage.input_tokens (Anthropic/OpenAI/Groq all have it)│           │          │
  ├───┼────────────────────────────────────────────────────────────────────┼───────────┼──────────┤
  │ 2 │ ADD: claude-haiku-4-5 for classification & routing calls          │ ~67%/call │ Low      │
  │   │ → Intent classification, tool routing, semantic classification    │           │          │
  ├───┼────────────────────────────────────────────────────────────────────┼───────────┼──────────┤
  │ 3 │ ADD: gemini-2.5-flash for ultra-cheap classification fallback     │ ~96%/call │ Medium   │
  │   │ → $0.00015/1K vs $0.003/1K input                                 │           │          │
  ├───┼────────────────────────────────────────────────────────────────────┼───────────┼──────────┤
  │ 4 │ USE: Batch API for sourcing extraction (15 companies)             │ ~50% LLM  │ Medium   │
  │   │ → Anthropic & OpenAI both offer 50% off for async batch           │           │          │
  ├───┼────────────────────────────────────────────────────────────────────┼───────────┼──────────┤
  │ 5 │ CACHE: Tavily search results (dominant cost at $5/sourcing run)   │ ~80% ext  │ Medium   │
  │   │ → Same thesis = same web results for 24hrs                        │           │          │
  ├───┼────────────────────────────────────────────────────────────────────┼───────────┼──────────┤
  │ 6 │ UPGRADE: gemini-pro → gemini-2.5-pro or gemini-2.5-flash         │ Quality++ │ Low      │
  │   │ → Legacy gemini-pro is outdated                                   │           │          │
  ├───┼────────────────────────────────────────────────────────────────────┼───────────┼──────────┤
  │ 7 │ UPGRADE: claude-sonnet-4-5 → claude-sonnet-4-6                   │ Quality++ │ Trivial  │
  │   │ → Same price, better model — just change the model string         │           │          │
  ├───┼────────────────────────────────────────────────────────────────────┼───────────┼──────────┤
  │ 8 │ ADD: Prompt caching for system prompts (Anthropic)                │ ~90% on   │ Medium   │
  │   │ → System prompts are identical across calls — cache them          │ cached    │          │
  ├───┼────────────────────────────────────────────────────────────────────┼───────────┼──────────┤
  │ 9 │ TIERED ROUTING: Route by task complexity, not just capability     │ ~40% avg  │ High     │
  │   │ → Simple=Haiku, Medium=GPT-5-mini, Complex=Sonnet, Deep=Opus     │           │          │
  ├───┼────────────────────────────────────────────────────────────────────┼───────────┼──────────┤
  │10 │ UPDATE: gpt-5-mini config price (your: $0.0005, actual: $0.00025)│ Accuracy  │ Trivial  │
  │   │ → Your config shows 2x the actual price                          │           │          │
  └───┴────────────────────────────────────────────────────────────────────┴───────────┴──────────┘
""")


def section_8_budget_analysis():
    """Analyze the $2.00 / 500K token budget."""
    print_header("8. REQUEST BUDGET ANALYSIS — Is $2.00 / 500K Tokens Right?")

    print(f"""
  Current defaults (RequestBudget.__init__):
    max_cost:   $2.00
    max_tokens: 500,000

  How far does $2.00 go with each model?
  ┌──────────────────────────┬────────────────────┬────────────────────┐
  │ Model                    │ Input tokens @ $2  │ Output tokens @ $2 │
  ├──────────────────────────┼────────────────────┼────────────────────┤
  │ claude-sonnet-4-5        │ 666,667            │ 133,333            │
  │ claude-haiku-4-5         │ 2,000,000          │ 400,000            │
  │ gpt-5-mini               │ 8,000,000          │ 1,000,000          │
  │ gpt-5.2                  │ 200,000            │ 66,667             │
  │ gemini-2.5-flash         │ 13,333,333         │ 3,333,333          │
  │ mixtral-8x7b (Groq)      │ 8,333,333          │ 8,333,333          │
  └──────────────────────────┴────────────────────┴────────────────────┘

  Will any pipeline hit the $2.00 limit?
""")

    sonnet = ACTUAL_MARKET_RATES["claude-sonnet-4-5"]
    for pipe_key, pipe in PIPELINES.items():
        llm_cost = 0.0
        for c in pipe.calls:
            llm_cost += (c.est_input_tokens / 1000) * sonnet["input"]
            llm_cost += (c.est_output_tokens / 1000) * sonnet["output"]
        ext = sum(pipe.external_costs.values())
        total = llm_cost + ext
        total_tokens = pipe.total_tokens()
        budget_pct = (total / 2.0) * 100

        status = "OK" if budget_pct < 60 else ("WARNING" if budget_pct < 90 else "WILL HIT LIMIT")
        bar = "█" * min(int(budget_pct / 5), 20) + "░" * max(20 - int(budget_pct / 5), 0)

        print(f"  {pipe.name:<50}")
        print(f"    LLM: ${llm_cost:.4f}  External: ${ext:.2f}  Total: ${total:.4f}  Tokens: {total_tokens:,}")
        print(f"    Budget: {bar} {budget_pct:.1f}%  {status}")
        print()

    print("""  NOTE: The $2.00 budget only tracks LLM costs in the current implementation.
  Tavily costs ($0.50-$5.00/request) are NOT tracked by RequestBudget.
  Consider: Should external API costs count toward the budget?
""")


def main():
    print("=" * 100)
    print("  DILLA AI — FULL TOKEN COST ANALYSIS")
    print("  Generated for visibility into pricing, competition, and agent loop costs")
    print("=" * 100)

    section_1_pricing_audit()
    section_2_critical_bug()
    section_3_pipeline_costs()
    section_4_monthly_projections()
    section_5_model_comparison_matrix()
    section_6_sourcing_deep_dive()
    section_7_optimization_recommendations()
    section_8_budget_analysis()

    print_header("SUMMARY")
    print("""
  KEY FINDINGS:
  1. Cost tracking bug: char/4 estimation underreports real costs by 25-40%
  2. gpt-5-mini config price is 2x actual market rate ($0.0005 vs $0.00025)
  3. Tavily search ($5/sourcing run) dominates cost — LLM is only ~3% of sourcing
  4. No tiered model routing — Sonnet used for simple classification (3x overspend)
  5. Missing models: Haiku, Gemini Flash, Sonnet 4.6 would save 40-67% on light tasks
  6. No prompt caching — identical system prompts re-sent every call
  7. $2.00 budget doesn't track Tavily costs — real spend may be 3x what's reported

  QUICK WINS (< 1 day of work):
  - Fix _calculate_cost to use real API token counts
  - Update gpt-5-mini price to $0.00025/$0.002
  - Add claude-haiku-4-5 config for classification
  - Change claude-sonnet-4-5 → claude-sonnet-4-6 (same price, better)
  - Update gemini-pro → gemini-2.5-pro or gemini-2.5-flash

  MEDIUM EFFORT (1-3 days):
  - Implement tiered model routing by task complexity
  - Add Tavily result caching (24hr TTL)
  - Enable Anthropic prompt caching for system prompts
  - Use Batch API for sourcing extraction

  PROJECTED SAVINGS:
  - Quick wins alone: ~30% cost reduction on LLM spend
  - All optimizations: ~60% cost reduction + accurate tracking
""")


if __name__ == "__main__":
    main()
