"""
FX Intelligence Service
Fetches daily FX rates and computes portfolio-level currency impact.
Designed to feed into the agent suggestion & memo systems.
"""

import logging
import time
from typing import Dict, Any, Optional, List
import aiohttp

logger = logging.getLogger(__name__)

# Free ECB reference rates (no key required, updated daily ~16:00 CET)
ECB_DAILY_URL = "https://data-api.ecb.europa.eu/service/data/EXR/D..EUR.SP00.A?lastNObservations=1&format=jsondata"
# Fallback: exchangerate.host (free tier)
EXCHANGERATE_URL = "https://api.exchangerate.host/latest?base=USD"

# Cache TTL: 1 hour
_CACHE_TTL = 3600


class FXIntelligenceService:
    """Provides FX rate intelligence for portfolio analysis."""

    def __init__(self):
        self._rate_cache: Dict[str, float] = {}
        self._cache_ts: float = 0
        self._session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))

    async def _fetch_rates(self) -> Dict[str, float]:
        """Fetch latest USD-based FX rates. Returns {EUR: 1.08, GBP: 1.27, ...}."""
        now = time.time()
        if self._rate_cache and (now - self._cache_ts) < _CACHE_TTL:
            return self._rate_cache

        await self._ensure_session()

        # Try exchangerate.host first (simpler JSON)
        try:
            async with self._session.get(EXCHANGERATE_URL) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    rates = data.get("rates", {})
                    if rates:
                        self._rate_cache = {k: float(v) for k, v in rates.items()}
                        self._cache_ts = now
                        logger.info(f"[FX] Refreshed rates: {len(self._rate_cache)} currencies")
                        return self._rate_cache
        except Exception as e:
            logger.warning(f"[FX] exchangerate.host failed: {e}")

        # Fallback: return stale cache or empty
        if self._rate_cache:
            logger.warning("[FX] Using stale rate cache")
            return self._rate_cache

        logger.error("[FX] No FX rates available")
        return {}

    async def get_rate(self, from_ccy: str, to_ccy: str = "USD") -> Optional[float]:
        """Get exchange rate from_ccy -> to_ccy. Returns None if unavailable."""
        rates = await self._fetch_rates()
        if not rates:
            return None

        from_ccy = from_ccy.upper()
        to_ccy = to_ccy.upper()

        if from_ccy == to_ccy:
            return 1.0

        # Rates are USD-based: rates[EUR] = how many EUR per 1 USD
        from_rate = rates.get(from_ccy, None) if from_ccy != "USD" else 1.0
        to_rate = rates.get(to_ccy, None) if to_ccy != "USD" else 1.0

        if from_rate is None or to_rate is None:
            return None

        return to_rate / from_rate

    async def get_fx_impact(
        self,
        company_currency_mix: Dict[str, float],
        base_currency: str = "USD",
        revenue_usd: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Compute FX impact for a company given its currency revenue mix.

        Args:
            company_currency_mix: e.g. {"USD": 0.6, "EUR": 0.3, "GBP": 0.1}
            base_currency: Fund's base currency
            revenue_usd: Total revenue in USD (for absolute impact calc)

        Returns:
            {
                "exposure_score": 0-100 (0 = all domestic, 100 = all foreign),
                "dominant_foreign_ccy": "EUR",
                "rates": {"EUR": 1.08, "GBP": 1.27},
                "impact_narrative": "40% non-USD exposure...",
                "absolute_impact_usd": 2_000_000  (if revenue provided)
            }
        """
        rates = await self._fetch_rates()

        foreign_pct = sum(
            v for k, v in company_currency_mix.items()
            if k.upper() != base_currency.upper()
        )
        exposure_score = min(100, int(foreign_pct * 100))

        # Find dominant foreign currency
        foreign_ccys = {
            k: v for k, v in company_currency_mix.items()
            if k.upper() != base_currency.upper()
        }
        dominant = max(foreign_ccys, key=foreign_ccys.get) if foreign_ccys else None

        relevant_rates = {}
        for ccy in company_currency_mix:
            if ccy.upper() != base_currency.upper() and ccy.upper() in rates:
                relevant_rates[ccy.upper()] = rates[ccy.upper()]

        narrative_parts = []
        if foreign_pct > 0.3:
            narrative_parts.append(f"{foreign_pct:.0%} non-{base_currency} revenue exposure")
        if dominant:
            narrative_parts.append(f"largest foreign exposure: {dominant} ({foreign_ccys[dominant]:.0%})")

        result = {
            "exposure_score": exposure_score,
            "dominant_foreign_ccy": dominant,
            "foreign_revenue_pct": round(foreign_pct, 3),
            "rates": relevant_rates,
            "impact_narrative": "; ".join(narrative_parts) if narrative_parts else "Minimal FX exposure",
        }

        if revenue_usd and foreign_pct > 0:
            # Rough impact: assume 5% adverse FX move on foreign portion
            adverse_move_pct = 0.05
            result["absolute_impact_usd"] = round(revenue_usd * foreign_pct * adverse_move_pct)
            result["impact_note"] = f"5% adverse FX move on foreign revenue = ${result['absolute_impact_usd']:,.0f} impact"

        return result

    async def get_portfolio_fx_summary(
        self,
        companies: List[Dict[str, Any]],
        base_currency: str = "USD",
    ) -> Dict[str, Any]:
        """
        Summarize FX exposure across a portfolio.

        Each company dict should have:
            - name: str
            - revenue_usd: float (optional)
            - currency_mix: Dict[str, float] (optional, e.g. {"USD": 0.7, "EUR": 0.3})
        """
        results = []
        total_foreign_exposure_usd = 0
        total_revenue = 0

        for co in companies:
            mix = co.get("currency_mix")
            if not mix:
                continue
            rev = co.get("revenue_usd") or co.get("arr") or 0
            impact = await self.get_fx_impact(mix, base_currency, rev)
            impact["company"] = co.get("name", "Unknown")
            results.append(impact)

            if rev:
                total_revenue += rev
                total_foreign_exposure_usd += rev * impact.get("foreign_revenue_pct", 0)

        portfolio_foreign_pct = (total_foreign_exposure_usd / total_revenue) if total_revenue else 0

        return {
            "companies": results,
            "portfolio_foreign_exposure_pct": round(portfolio_foreign_pct, 3),
            "total_foreign_revenue_usd": round(total_foreign_exposure_usd),
            "total_portfolio_revenue_usd": round(total_revenue),
            "adverse_5pct_impact_usd": round(total_foreign_exposure_usd * 0.05) if total_foreign_exposure_usd else 0,
        }

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


# Singleton
fx_intelligence_service = FXIntelligenceService()
