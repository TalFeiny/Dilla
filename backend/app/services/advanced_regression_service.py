"""
Advanced Regression Service
Full toolkit of curve-fitting methods for CFO-grade revenue/metric forecasting.

Models:
  polynomial      — Quadratic/cubic fits for acceleration/deceleration patterns
  exponential_growth — y = a * e^(b*t) for compounding growth
  logistic         — S-curve: y = L / (1 + e^(-k*(t-t0))) for TAM-bounded growth
  power_law        — y = a * t^b for early-stage hypergrowth
  piecewise_linear — Auto-detects breakpoints where growth rate changed
  weighted_linear  — Recent data weighted exponentially higher than old data
  gompertz         — y = a * e^(-b * e^(-c*t)) asymmetric S-curve (slower ramp-up)

Auto-selection: fits all models, compares adjusted R², picks best fit with
qualitative reasoning about WHY that model fits — the agent needs to understand
the shape of the business, not just the math.

All implementations use scipy.optimize.curve_fit + numpy (already installed).
No new dependencies required.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import curve_fit
from scipy import stats

logger = logging.getLogger(__name__)


# ======================================================================
# Result dataclass
# ======================================================================

@dataclass
class RegressionResult:
    """Result from fitting a single regression model."""
    model_name: str
    r_squared: float
    adjusted_r_squared: float
    equation: str
    params: Dict[str, float]
    predictions: List[float]
    residuals: List[float]
    n_params: int
    qualitative_assessment: str  # CFO-readable explanation of what this shape means
    confidence: str  # "high", "medium", "low"
    business_interpretation: str  # what this growth pattern implies for the business
    extrapolation_risk: str  # "low", "medium", "high" — how dangerous it is to project forward

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "r_squared": round(self.r_squared, 4),
            "adjusted_r_squared": round(self.adjusted_r_squared, 4),
            "equation": self.equation,
            "params": {k: round(v, 6) for k, v in self.params.items()},
            "n_params": self.n_params,
            "qualitative_assessment": self.qualitative_assessment,
            "confidence": self.confidence,
            "business_interpretation": self.business_interpretation,
            "extrapolation_risk": self.extrapolation_risk,
        }


@dataclass
class AutoSelectionResult:
    """Result from auto-selecting the best regression model."""
    best_model: RegressionResult
    all_models: List[RegressionResult]
    selection_reasoning: str  # why this model was chosen
    data_characteristics: Dict[str, Any]  # trend direction, volatility, etc.
    forecast: List[float]  # projected values for requested periods
    forecast_confidence_intervals: List[Dict[str, float]]  # upper/lower bounds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "best_model": self.best_model.to_dict(),
            "all_models_ranked": [m.to_dict() for m in self.all_models],
            "selection_reasoning": self.selection_reasoning,
            "data_characteristics": self.data_characteristics,
            "forecast": [round(v, 2) for v in self.forecast],
            "forecast_confidence_intervals": self.forecast_confidence_intervals,
        }


# ======================================================================
# Model functions (scipy curve_fit compatible)
# ======================================================================

def _linear(x, a, b):
    return a * x + b


def _quadratic(x, a, b, c):
    return a * x**2 + b * x + c


def _cubic(x, a, b, c, d):
    return a * x**3 + b * x**2 + c * x + d


def _exponential_growth(x, a, b):
    """y = a * e^(b*x) — unbounded exponential growth."""
    return a * np.exp(np.clip(b * x, -50, 50))


def _logistic(x, L, k, x0):
    """S-curve: y = L / (1 + e^(-k*(x-x0)))"""
    return L / (1 + np.exp(np.clip(-k * (x - x0), -50, 50)))


def _power_law(x, a, b):
    """y = a * x^b — only for x > 0."""
    return a * np.power(np.maximum(x, 1e-10), b)


def _gompertz(x, a, b, c):
    """Gompertz: y = a * e^(-b * e^(-c*x)) — asymmetric S-curve."""
    return a * np.exp(-b * np.exp(np.clip(-c * x, -50, 50)))


# ======================================================================
# Core service
# ======================================================================

class AdvancedRegressionService:
    """Full regression toolkit for CFO-grade forecasting."""

    # ------------------------------------------------------------------
    # Individual model fits
    # ------------------------------------------------------------------

    def fit_linear(self, x: np.ndarray, y: np.ndarray) -> Optional[RegressionResult]:
        """Standard linear regression."""
        try:
            popt, _ = curve_fit(_linear, x, y)
            a, b = popt
            y_pred = _linear(x, *popt)
            r2, adj_r2 = self._r_squared(y, y_pred, n_params=2)

            trend = "increasing" if a > 0 else "decreasing"
            monthly_rate = abs(a) / max(abs(np.mean(y)), 1) * 100

            return RegressionResult(
                model_name="linear",
                r_squared=r2,
                adjusted_r_squared=adj_r2,
                equation=f"y = {a:.2f}x + {b:.2f}",
                params={"slope": float(a), "intercept": float(b)},
                predictions=y_pred.tolist(),
                residuals=(y - y_pred).tolist(),
                n_params=2,
                qualitative_assessment=(
                    f"Linear {trend} trend at ~{monthly_rate:.1f}% per period. "
                    f"Constant rate of change — no acceleration or deceleration."
                ),
                confidence=self._confidence_label(adj_r2),
                business_interpretation=(
                    f"{'Growing' if a > 0 else 'Declining'} at a constant rate. "
                    f"This implies no network effects, no compounding, no saturation. "
                    f"Common in early-stage companies with consistent sales execution."
                ),
                extrapolation_risk="medium",
            )
        except Exception as e:
            logger.debug(f"Linear fit failed: {e}")
            return None

    def fit_polynomial(self, x: np.ndarray, y: np.ndarray, degree: int = 2) -> Optional[RegressionResult]:
        """Polynomial regression (quadratic or cubic)."""
        try:
            func = _quadratic if degree == 2 else _cubic
            n_params = degree + 1

            if degree == 2:
                p0 = [0.0, float(np.mean(np.diff(y))), float(y[0])]
                popt, _ = curve_fit(func, x, y, p0=p0, maxfev=10000)
                a, b, c = popt
                eq = f"y = {a:.4f}x² + {b:.2f}x + {c:.2f}"
                params = {"a": float(a), "b": float(b), "c": float(c)}
            else:
                p0 = [0.0, 0.0, float(np.mean(np.diff(y))), float(y[0])]
                popt, _ = curve_fit(func, x, y, p0=p0, maxfev=10000)
                a, b, c, d = popt
                eq = f"y = {a:.6f}x³ + {b:.4f}x² + {c:.2f}x + {d:.2f}"
                params = {"a": float(a), "b": float(b), "c": float(c), "d": float(d)}

            y_pred = func(x, *popt)
            r2, adj_r2 = self._r_squared(y, y_pred, n_params=n_params)

            # Qualitative: is the curve accelerating or decelerating?
            if degree == 2:
                curvature = "accelerating" if a > 0 else "decelerating"
                assessment = (
                    f"{'Quadratic' if degree == 2 else 'Cubic'} fit shows {curvature} growth. "
                    f"The curve {'bends upward' if a > 0 else 'flattens over time'}."
                )
                biz_interp = (
                    f"Revenue is {'accelerating — possible network effects, viral growth, or expanding TAM capture' if a > 0 else 'decelerating — market saturation, competitive pressure, or scaling friction'}. "
                    f"This is {'sustainable short-term but will hit limits' if a > 0 else 'expected as companies scale'}."
                )
            else:
                assessment = (
                    f"Cubic fit captures inflection points — the growth rate itself is changing direction. "
                    f"This can indicate a J-curve recovery or an S-curve transition."
                )
                biz_interp = (
                    "Complex growth pattern with at least one inflection point. "
                    "Could indicate a pivot, market shift, or transition between growth phases."
                )

            return RegressionResult(
                model_name=f"polynomial_deg{degree}",
                r_squared=r2,
                adjusted_r_squared=adj_r2,
                equation=eq,
                params=params,
                predictions=y_pred.tolist(),
                residuals=(y - y_pred).tolist(),
                n_params=n_params,
                qualitative_assessment=assessment,
                confidence=self._confidence_label(adj_r2),
                business_interpretation=biz_interp,
                extrapolation_risk="high" if degree >= 3 else "medium",
            )
        except Exception as e:
            logger.debug(f"Polynomial deg{degree} fit failed: {e}")
            return None

    def fit_exponential_growth(self, x: np.ndarray, y: np.ndarray) -> Optional[RegressionResult]:
        """Exponential growth: y = a * e^(b*x)."""
        try:
            if np.any(y <= 0):
                return None  # Can't fit exp growth to negative values

            a_init = float(y[0]) if y[0] > 0 else 1.0
            # Estimate b from log-linear slope
            log_y = np.log(np.maximum(y, 1e-10))
            b_init = float(np.polyfit(x, log_y, 1)[0])
            b_init = np.clip(b_init, -2, 2)

            popt, _ = curve_fit(
                _exponential_growth, x, y,
                p0=[a_init, b_init], maxfev=10000,
                bounds=([0, -5], [np.inf, 5]),
            )
            a, b = popt
            y_pred = _exponential_growth(x, *popt)
            r2, adj_r2 = self._r_squared(y, y_pred, n_params=2)

            monthly_growth_pct = (np.exp(b) - 1) * 100
            doubling_time = np.log(2) / b if b > 0 else float("inf")

            return RegressionResult(
                model_name="exponential_growth",
                r_squared=r2,
                adjusted_r_squared=adj_r2,
                equation=f"y = {a:.2f} × e^({b:.4f}x)",
                params={"initial_value": float(a), "growth_constant": float(b),
                        "monthly_growth_pct": float(monthly_growth_pct),
                        "doubling_time_periods": float(doubling_time)},
                predictions=y_pred.tolist(),
                residuals=(y - y_pred).tolist(),
                n_params=2,
                qualitative_assessment=(
                    f"Exponential growth at {monthly_growth_pct:.1f}% per period. "
                    f"{'Doubling every ' + f'{doubling_time:.1f} periods.' if doubling_time < 100 else 'Very slow exponential.'} "
                    f"This is compound growth — each period builds on the last."
                ),
                confidence=self._confidence_label(adj_r2),
                business_interpretation=(
                    f"Compound growth pattern — typical of SaaS with strong net retention, "
                    f"viral products, or businesses with expanding revenue per customer. "
                    f"{'Sustainable at current rate for 12-18 months before decay sets in.' if monthly_growth_pct < 15 else 'This growth rate is unsustainable long-term — expect deceleration.'}"
                ),
                extrapolation_risk="high" if monthly_growth_pct > 10 else "medium",
            )
        except Exception as e:
            logger.debug(f"Exponential growth fit failed: {e}")
            return None

    def fit_logistic(self, x: np.ndarray, y: np.ndarray) -> Optional[RegressionResult]:
        """Logistic S-curve: y = L / (1 + e^(-k*(x-x0)))."""
        try:
            if np.any(y <= 0):
                return None

            # Initial guesses
            L_init = float(np.max(y) * 1.5)  # Carrying capacity above current max
            k_init = 0.1  # Growth rate
            x0_init = float(np.median(x))  # Inflection point at midpoint

            popt, _ = curve_fit(
                _logistic, x, y,
                p0=[L_init, k_init, x0_init],
                maxfev=10000,
                bounds=([float(np.max(y)) * 0.8, 0.001, -100], [float(np.max(y)) * 10, 10, 200]),
            )
            L, k, x0 = popt
            y_pred = _logistic(x, *popt)
            r2, adj_r2 = self._r_squared(y, y_pred, n_params=3)

            current_penetration = float(y[-1] / L * 100)
            inflection_reached = x0 < x[-1]

            return RegressionResult(
                model_name="logistic",
                r_squared=r2,
                adjusted_r_squared=adj_r2,
                equation=f"y = {L:.0f} / (1 + e^(-{k:.4f}(x - {x0:.1f})))",
                params={"carrying_capacity": float(L), "growth_rate": float(k),
                        "inflection_point": float(x0),
                        "current_penetration_pct": current_penetration},
                predictions=y_pred.tolist(),
                residuals=(y - y_pred).tolist(),
                n_params=3,
                qualitative_assessment=(
                    f"S-curve growth approaching ceiling of ${L:,.0f}. "
                    f"Currently at {current_penetration:.0f}% of carrying capacity. "
                    f"{'Past the inflection point — growth rate is now declining.' if inflection_reached else 'Still in acceleration phase — growth rate increasing.'}"
                ),
                confidence=self._confidence_label(adj_r2),
                business_interpretation=(
                    f"Natural TAM-bounded growth. The market can support ~${L:,.0f} in revenue. "
                    f"{'Growth will continue to decelerate as you approach saturation.' if inflection_reached else 'Growth is still accelerating — significant runway remains.'} "
                    f"This is the healthiest growth pattern for SaaS approaching market maturity."
                ),
                extrapolation_risk="low",
            )
        except Exception as e:
            logger.debug(f"Logistic fit failed: {e}")
            return None

    def fit_power_law(self, x: np.ndarray, y: np.ndarray) -> Optional[RegressionResult]:
        """Power law: y = a * x^b."""
        try:
            if np.any(y <= 0) or np.any(x <= 0):
                return None

            # Log-log regression for initial guess
            log_x = np.log(x)
            log_y = np.log(y)
            b_init, log_a_init = np.polyfit(log_x, log_y, 1)
            a_init = np.exp(log_a_init)

            popt, _ = curve_fit(
                _power_law, x, y,
                p0=[a_init, b_init], maxfev=10000,
                bounds=([0, -10], [np.inf, 10]),
            )
            a, b = popt
            y_pred = _power_law(x, *popt)
            r2, adj_r2 = self._r_squared(y, y_pred, n_params=2)

            return RegressionResult(
                model_name="power_law",
                r_squared=r2,
                adjusted_r_squared=adj_r2,
                equation=f"y = {a:.2f} × x^{b:.3f}",
                params={"coefficient": float(a), "exponent": float(b)},
                predictions=y_pred.tolist(),
                residuals=(y - y_pred).tolist(),
                n_params=2,
                qualitative_assessment=(
                    f"Power law with exponent {b:.2f}. "
                    f"{'Super-linear growth (each period adds more than the last)' if b > 1 else 'Sub-linear growth (diminishing returns per period)' if b < 1 else 'Linear growth'}. "
                    f"{'Exponent > 2 suggests explosive early-stage growth.' if b > 2 else ''}"
                ),
                confidence=self._confidence_label(adj_r2),
                business_interpretation=(
                    f"{'Hypergrowth pattern — common in early-stage companies with strong product-market fit. ' if b > 1.5 else ''}"
                    f"{'Scaling with diminishing marginal returns — each new dollar is harder to earn. ' if b < 1 else ''}"
                    f"Power law growth is typical of {'viral/network-effect businesses' if b > 1 else 'mature scaling businesses'}."
                ),
                extrapolation_risk="high" if b > 1.5 else "medium",
            )
        except Exception as e:
            logger.debug(f"Power law fit failed: {e}")
            return None

    def fit_gompertz(self, x: np.ndarray, y: np.ndarray) -> Optional[RegressionResult]:
        """Gompertz curve: y = a * e^(-b * e^(-c*x)) — asymmetric S-curve."""
        try:
            if np.any(y <= 0):
                return None

            a_init = float(np.max(y) * 2)
            b_init = 5.0
            c_init = 0.1

            popt, _ = curve_fit(
                _gompertz, x, y,
                p0=[a_init, b_init, c_init],
                maxfev=10000,
                bounds=([float(np.max(y)) * 0.5, 0.01, 0.001], [float(np.max(y)) * 20, 100, 10]),
            )
            a, b, c = popt
            y_pred = _gompertz(x, *popt)
            r2, adj_r2 = self._r_squared(y, y_pred, n_params=3)

            current_pct = float(y[-1] / a * 100)

            return RegressionResult(
                model_name="gompertz",
                r_squared=r2,
                adjusted_r_squared=adj_r2,
                equation=f"y = {a:.0f} × e^(-{b:.2f} × e^(-{c:.4f}x))",
                params={"asymptote": float(a), "displacement": float(b),
                        "growth_rate": float(c), "current_pct_of_ceiling": current_pct},
                predictions=y_pred.tolist(),
                residuals=(y - y_pred).tolist(),
                n_params=3,
                qualitative_assessment=(
                    f"Gompertz curve with ceiling ${a:,.0f}. "
                    f"Currently at {current_pct:.0f}% of asymptote. "
                    f"Slower initial ramp than logistic — models businesses where early adoption is slow."
                ),
                confidence=self._confidence_label(adj_r2),
                business_interpretation=(
                    "Asymmetric S-curve — slow initial adoption then rapid acceleration before tapering. "
                    "Common in enterprise SaaS, regulated industries, or businesses requiring behavior change. "
                    f"Ceiling: ${a:,.0f}."
                ),
                extrapolation_risk="low",
            )
        except Exception as e:
            logger.debug(f"Gompertz fit failed: {e}")
            return None

    def fit_piecewise_linear(self, x: np.ndarray, y: np.ndarray) -> Optional[RegressionResult]:
        """Piecewise linear — auto-detect one breakpoint."""
        try:
            if len(x) < 6:
                return None

            best_r2 = -np.inf
            best_bp = None
            best_params = None
            best_pred = None

            # Try each interior point as a breakpoint
            for bp_idx in range(2, len(x) - 2):
                bp = x[bp_idx]
                x1, y1 = x[:bp_idx + 1], y[:bp_idx + 1]
                x2, y2 = x[bp_idx:], y[bp_idx:]

                s1, i1 = np.polyfit(x1, y1, 1)
                s2, i2 = np.polyfit(x2, y2, 1)

                pred = np.concatenate([
                    np.polyval([s1, i1], x1),
                    np.polyval([s2, i2], x2[1:]),
                ])
                r2 = 1 - np.sum((y - pred) ** 2) / np.sum((y - np.mean(y)) ** 2)

                if r2 > best_r2:
                    best_r2 = r2
                    best_bp = bp
                    best_params = {"slope1": float(s1), "intercept1": float(i1),
                                   "slope2": float(s2), "intercept2": float(i2),
                                   "breakpoint": float(bp)}
                    best_pred = pred

            if best_pred is None:
                return None

            _, adj_r2 = self._r_squared(y, best_pred, n_params=4)
            s1 = best_params["slope1"]
            s2 = best_params["slope2"]

            # Characterize the regime change
            if s1 > 0 and s2 > s1:
                regime_change = "Growth acceleration — rate increased at the breakpoint"
            elif s1 > 0 and 0 < s2 < s1:
                regime_change = "Growth deceleration — rate slowed at the breakpoint"
            elif s1 > 0 and s2 < 0:
                regime_change = "Peak and decline — growth reversed direction"
            elif s1 < 0 and s2 > 0:
                regime_change = "Recovery — decline reversed into growth (J-curve)"
            elif s1 < 0 and s2 < s1:
                regime_change = "Accelerating decline"
            else:
                regime_change = "Regime shift detected"

            return RegressionResult(
                model_name="piecewise_linear",
                r_squared=best_r2,
                adjusted_r_squared=adj_r2,
                equation=f"y = {s1:.2f}x + {best_params['intercept1']:.0f} (x ≤ {best_bp:.0f}), "
                         f"{s2:.2f}x + {best_params['intercept2']:.0f} (x > {best_bp:.0f})",
                params=best_params,
                predictions=best_pred.tolist(),
                residuals=(y - best_pred).tolist(),
                n_params=4,
                qualitative_assessment=(
                    f"Breakpoint detected at period {best_bp:.0f}. {regime_change}. "
                    f"Pre-break slope: {s1:.2f}/period, post-break: {s2:.2f}/period."
                ),
                confidence=self._confidence_label(adj_r2),
                business_interpretation=(
                    f"{regime_change}. "
                    f"This could indicate a product launch, market shift, pricing change, "
                    f"new competitor, or operational change. "
                    f"The forecast should use the post-breakpoint trend."
                ),
                extrapolation_risk="medium",
            )
        except Exception as e:
            logger.debug(f"Piecewise fit failed: {e}")
            return None

    def fit_weighted_linear(self, x: np.ndarray, y: np.ndarray, decay: float = 0.9) -> Optional[RegressionResult]:
        """Weighted linear regression — recent data weighted exponentially higher."""
        try:
            n = len(x)
            weights = np.array([decay ** (n - 1 - i) for i in range(n)])
            weights /= weights.sum()

            # Weighted least squares
            W = np.diag(weights)
            X = np.column_stack([x, np.ones(n)])
            XtW = X.T @ W
            popt = np.linalg.solve(XtW @ X, XtW @ y)
            slope, intercept = popt

            y_pred = slope * x + intercept
            r2, adj_r2 = self._r_squared(y, y_pred, n_params=2, weights=weights)

            # Compare weighted vs unweighted slope
            unwt_slope = np.polyfit(x, y, 1)[0]
            trend_shift = "accelerating" if slope > unwt_slope else "decelerating"

            return RegressionResult(
                model_name="weighted_linear",
                r_squared=r2,
                adjusted_r_squared=adj_r2,
                equation=f"y = {slope:.2f}x + {intercept:.2f} (weight decay={decay})",
                params={"slope": float(slope), "intercept": float(intercept),
                        "weight_decay": decay,
                        "unweighted_slope": float(unwt_slope)},
                predictions=y_pred.tolist(),
                residuals=(y - y_pred).tolist(),
                n_params=2,
                qualitative_assessment=(
                    f"Weighted linear trend (recent data 10x weight of oldest). "
                    f"Weighted slope: {slope:.2f} vs unweighted: {unwt_slope:.2f}. "
                    f"Recent trend is {trend_shift} relative to historical."
                ),
                confidence=self._confidence_label(adj_r2),
                business_interpretation=(
                    f"Recent trajectory {'stronger' if slope > unwt_slope else 'weaker'} "
                    f"than historical average. "
                    f"{'This suggests improving execution or market tailwinds.' if slope > unwt_slope else 'This suggests headwinds — the business may be encountering scaling friction.'} "
                    f"Weighted regression is the most relevant for near-term forecasting."
                ),
                extrapolation_risk="low",
            )
        except Exception as e:
            logger.debug(f"Weighted linear fit failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Auto-selection: fit all, pick best, explain why
    # ------------------------------------------------------------------

    def auto_select_best_model(
        self,
        x: List[float],
        y: List[float],
        forecast_periods: int = 12,
        metric_name: str = "revenue",
    ) -> AutoSelectionResult:
        """Fit all models, rank by adjusted R², select best with qualitative reasoning.

        This is the main entry point for the PnL agent to get the best forecast.

        Args:
            x: Time indices (0, 1, 2, ..., N-1) or actual period numbers
            y: Observed values
            forecast_periods: How many periods to project forward
            metric_name: What we're forecasting (for business context)

        Returns:
            AutoSelectionResult with best model, all models ranked, and forecast
        """
        x_arr = np.array(x, dtype=float)
        y_arr = np.array(y, dtype=float)
        n = len(x_arr)

        if n < 3:
            raise ValueError(f"Need at least 3 data points for regression, got {n}")

        # Analyze data characteristics
        data_chars = self._analyze_data(x_arr, y_arr, metric_name)

        # Fit all models
        models: List[RegressionResult] = []

        fits = [
            self.fit_linear(x_arr, y_arr),
            self.fit_polynomial(x_arr, y_arr, degree=2),
            self.fit_exponential_growth(x_arr, y_arr),
            self.fit_logistic(x_arr, y_arr),
            self.fit_weighted_linear(x_arr, y_arr, decay=0.9),
        ]

        # Models that need more data
        if n >= 5:
            fits.append(self.fit_power_law(x_arr, y_arr))
            fits.append(self.fit_gompertz(x_arr, y_arr))

        if n >= 6:
            fits.append(self.fit_polynomial(x_arr, y_arr, degree=3))
            fits.append(self.fit_piecewise_linear(x_arr, y_arr))

        for fit in fits:
            if fit is not None:
                models.append(fit)

        if not models:
            raise ValueError("No regression model could be fit to the data")

        # Rank by adjusted R² (penalizes overfitting)
        models.sort(key=lambda m: m.adjusted_r_squared, reverse=True)

        # Select best — but with sanity checks
        best = self._select_with_sanity(models, data_chars, forecast_periods)

        # Generate forecast from best model
        forecast, ci = self._generate_forecast(
            best, x_arr, y_arr, forecast_periods
        )

        # Build selection reasoning
        reasoning = self._build_selection_reasoning(best, models, data_chars, metric_name)

        return AutoSelectionResult(
            best_model=best,
            all_models=models,
            selection_reasoning=reasoning,
            data_characteristics=data_chars,
            forecast=forecast,
            forecast_confidence_intervals=ci,
        )

    # ------------------------------------------------------------------
    # Data analysis
    # ------------------------------------------------------------------

    def _analyze_data(self, x: np.ndarray, y: np.ndarray, metric_name: str) -> Dict[str, Any]:
        """Characterize the data for model selection and qualitative reasoning."""
        n = len(y)
        diffs = np.diff(y)

        # Trend
        slope = np.polyfit(x, y, 1)[0]
        trend = "increasing" if slope > 0 else "decreasing" if slope < 0 else "flat"

        # Volatility (coefficient of variation)
        cv = float(np.std(y) / abs(np.mean(y))) if np.mean(y) != 0 else 0
        volatility = "low" if cv < 0.1 else "moderate" if cv < 0.3 else "high"

        # Acceleration (second derivative)
        if n >= 3:
            second_diffs = np.diff(diffs)
            avg_accel = float(np.mean(second_diffs))
            accel_label = "accelerating" if avg_accel > 0 else "decelerating" if avg_accel < 0 else "constant"
        else:
            avg_accel = 0
            accel_label = "unknown"

        # Growth rate pattern
        growth_rates = []
        for i in range(1, n):
            if y[i - 1] != 0:
                growth_rates.append((y[i] - y[i - 1]) / abs(y[i - 1]))
        avg_growth = float(np.mean(growth_rates)) if growth_rates else 0

        # Detect potential S-curve (growth rates decreasing while values increasing)
        s_curve_signal = (trend == "increasing" and accel_label == "decelerating"
                          and len(growth_rates) >= 4)

        # Detect potential breakpoint
        breakpoint_signal = False
        if n >= 6:
            first_half_slope = np.polyfit(x[:n // 2], y[:n // 2], 1)[0]
            second_half_slope = np.polyfit(x[n // 2:], y[n // 2:], 1)[0]
            slope_ratio = second_half_slope / first_half_slope if first_half_slope != 0 else 1
            breakpoint_signal = abs(slope_ratio - 1) > 0.5  # >50% change in slope

        return {
            "n_points": n,
            "metric": metric_name,
            "trend": trend,
            "volatility": volatility,
            "coefficient_of_variation": round(cv, 3),
            "acceleration": accel_label,
            "avg_period_growth": round(avg_growth, 4),
            "s_curve_signal": s_curve_signal,
            "breakpoint_signal": breakpoint_signal,
            "min_value": float(np.min(y)),
            "max_value": float(np.max(y)),
            "latest_value": float(y[-1]),
            "total_growth": float((y[-1] / y[0] - 1) if y[0] != 0 else 0),
        }

    # ------------------------------------------------------------------
    # Model selection with sanity checks
    # ------------------------------------------------------------------

    def _select_with_sanity(
        self, models: List[RegressionResult], data_chars: Dict, forecast_periods: int
    ) -> RegressionResult:
        """Select best model with sanity checks against overfitting and explosion."""
        best = models[0]

        # Penalize models with high extrapolation risk for long forecasts
        if forecast_periods > 12 and best.extrapolation_risk == "high":
            # Look for a safer alternative with similar R²
            for m in models[1:]:
                if m.extrapolation_risk != "high" and m.adjusted_r_squared > best.adjusted_r_squared * 0.95:
                    logger.info(
                        f"Preferring {m.model_name} (adj_r²={m.adjusted_r_squared:.3f}) "
                        f"over {best.model_name} (adj_r²={best.adjusted_r_squared:.3f}) "
                        f"for {forecast_periods}-period forecast due to extrapolation risk"
                    )
                    best = m
                    break

        # If S-curve signal is strong and logistic fits well, prefer it
        if data_chars.get("s_curve_signal"):
            for m in models:
                if m.model_name == "logistic" and m.adjusted_r_squared > 0.8:
                    best = m
                    break

        # If breakpoint signal, prefer piecewise
        if data_chars.get("breakpoint_signal"):
            for m in models:
                if m.model_name == "piecewise_linear" and m.adjusted_r_squared > best.adjusted_r_squared * 0.9:
                    best = m
                    break

        return best

    # ------------------------------------------------------------------
    # Forecast generation
    # ------------------------------------------------------------------

    def _generate_forecast(
        self, model: RegressionResult, x: np.ndarray, y: np.ndarray,
        periods: int,
    ) -> Tuple[List[float], List[Dict[str, float]]]:
        """Generate forward forecast from the best-fit model."""
        last_x = float(x[-1])
        x_future = np.array([last_x + i + 1 for i in range(periods)])

        # Get the model function and params
        params = model.params
        name = model.model_name

        try:
            if name == "linear":
                forecast = _linear(x_future, params["slope"], params["intercept"])
            elif name == "weighted_linear":
                forecast = _linear(x_future, params["slope"], params["intercept"])
            elif name == "polynomial_deg2":
                forecast = _quadratic(x_future, params["a"], params["b"], params["c"])
            elif name == "polynomial_deg3":
                forecast = _cubic(x_future, params["a"], params["b"], params["c"], params["d"])
            elif name == "exponential_growth":
                forecast = _exponential_growth(x_future, params["initial_value"], params["growth_constant"])
            elif name == "logistic":
                forecast = _logistic(x_future, params["carrying_capacity"],
                                     params["growth_rate"], params["inflection_point"])
            elif name == "power_law":
                forecast = _power_law(x_future, params["coefficient"], params["exponent"])
            elif name == "gompertz":
                forecast = _gompertz(x_future, params["asymptote"],
                                     params["displacement"], params["growth_rate"])
            elif name == "piecewise_linear":
                # Use post-breakpoint slope for extrapolation
                forecast = _linear(x_future, params["slope2"], params["intercept2"])
            else:
                # Fallback: linear extrapolation from last two points
                slope = (y[-1] - y[-2]) / (x[-1] - x[-2]) if len(y) >= 2 else 0
                forecast = y[-1] + slope * np.arange(1, periods + 1)

            forecast = np.array(forecast)

            # Sanity: don't let forecasts go negative for revenue
            forecast = np.maximum(forecast, 0)

            # Confidence intervals based on residual std
            residual_std = float(np.std(model.residuals))
            ci = []
            for i in range(periods):
                # Widening CI: uncertainty grows with forecast horizon
                margin = residual_std * (1 + 0.15 * (i + 1))
                ci.append({
                    "lower": round(float(forecast[i] - 1.96 * margin), 2),
                    "upper": round(float(forecast[i] + 1.96 * margin), 2),
                })

            return forecast.tolist(), ci

        except Exception as e:
            logger.error(f"Forecast generation failed for {name}: {e}")
            # Fallback: simple linear extrapolation
            slope = float(np.polyfit(x, y, 1)[0])
            forecast = [float(y[-1] + slope * (i + 1)) for i in range(periods)]
            ci = [{"lower": v * 0.8, "upper": v * 1.2} for v in forecast]
            return forecast, ci

    # ------------------------------------------------------------------
    # Selection reasoning
    # ------------------------------------------------------------------

    def _build_selection_reasoning(
        self, best: RegressionResult, all_models: List[RegressionResult],
        data_chars: Dict, metric_name: str,
    ) -> str:
        """Build CFO-readable explanation of why this model was selected."""
        parts = []

        parts.append(
            f"Evaluated {len(all_models)} regression models on {data_chars['n_points']} "
            f"periods of {metric_name} data."
        )

        # Top 3 models
        top3 = all_models[:3]
        rankings = ", ".join(
            f"{m.model_name} (adj R²={m.adjusted_r_squared:.3f})" for m in top3
        )
        parts.append(f"Top models: {rankings}.")

        parts.append(
            f"Selected {best.model_name} — {best.qualitative_assessment}"
        )

        # Data context
        parts.append(
            f"Data shows {data_chars['trend']} trend with {data_chars['volatility']} volatility "
            f"({data_chars['acceleration']} growth). "
            f"Total growth over period: {data_chars['total_growth']:.0%}."
        )

        if data_chars.get("s_curve_signal"):
            parts.append("S-curve signal detected: growth is decelerating while values increase.")

        if data_chars.get("breakpoint_signal"):
            parts.append("Regime change detected: growth rate shifted significantly mid-series.")

        parts.append(f"Extrapolation risk: {best.extrapolation_risk}.")

        return " ".join(parts)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _r_squared(
        y_actual: np.ndarray, y_pred: np.ndarray, n_params: int,
        weights: Optional[np.ndarray] = None,
    ) -> Tuple[float, float]:
        """Calculate R² and adjusted R²."""
        n = len(y_actual)
        if weights is not None:
            ss_res = float(np.sum(weights * (y_actual - y_pred) ** 2))
            ss_tot = float(np.sum(weights * (y_actual - np.average(y_actual, weights=weights)) ** 2))
        else:
            ss_res = float(np.sum((y_actual - y_pred) ** 2))
            ss_tot = float(np.sum((y_actual - np.mean(y_actual)) ** 2))

        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        # Adjusted R²: penalizes extra parameters
        if n > n_params + 1:
            adj_r2 = 1 - (1 - r2) * (n - 1) / (n - n_params - 1)
        else:
            adj_r2 = r2

        return float(r2), float(adj_r2)

    @staticmethod
    def _confidence_label(adj_r2: float) -> str:
        if adj_r2 >= 0.9:
            return "high"
        elif adj_r2 >= 0.7:
            return "medium"
        else:
            return "low"

    # ------------------------------------------------------------------
    # Convenience: project a metric forward using best-fit model
    # ------------------------------------------------------------------

    def project_metric(
        self,
        actuals: List[Dict[str, Any]],
        periods: int = 12,
        metric_key: str = "amount",
        metric_name: str = "revenue",
    ) -> Dict[str, Any]:
        """Convenience method: takes actuals list, returns best-fit projection.

        This is what the forecast_method_router calls.

        Args:
            actuals: List of {period: "2025-01", amount: 500000, ...}
            periods: How many months to project
            metric_key: Key in actuals dict containing the value
            metric_name: Human name for the metric

        Returns:
            Dict with projected_values, model_info, and confidence_intervals.
        """
        values = [a[metric_key] for a in actuals if a.get(metric_key) is not None]
        if len(values) < 3:
            raise ValueError(f"Need at least 3 actuals for regression, got {len(values)}")

        x = list(range(len(values)))

        result = self.auto_select_best_model(x, values, forecast_periods=periods, metric_name=metric_name)

        return {
            "projected_values": result.forecast,
            "model": result.best_model.to_dict(),
            "all_models": [m.to_dict() for m in result.all_models],
            "selection_reasoning": result.selection_reasoning,
            "data_characteristics": result.data_characteristics,
            "confidence_intervals": result.forecast_confidence_intervals,
        }
