"""
FPA Regression Service
Linear regression, exponential decay, time-series, Monte Carlo, sensitivity sweeps
Extended for world model analysis - finding relationships between qualitative and quantitative factors
"""

import logging
from typing import Dict, List, Any, Optional, Callable
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import curve_fit

logger = logging.getLogger(__name__)


class FPARegressionService:
    """Statistical analysis and regression for FPA and world models"""
    
    def __init__(self):
        pass
    
    async def linear_regression(
        self,
        x: List[float],
        y: List[float]
    ) -> Dict[str, Any]:
        """Perform linear regression"""
        try:
            slope, intercept = np.polyfit(x, y, 1)
            y_pred = np.polyval([slope, intercept], x)
            ss_res = np.sum((np.array(y) - y_pred) ** 2)
            ss_tot = np.sum((np.array(y) - np.mean(y)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
            
            return {
                "slope": float(slope),
                "intercept": float(intercept),
                "r_squared": float(r_squared),
                "equation": f"y = {slope:.2f}x + {intercept:.2f}"
            }
        except Exception as e:
            logger.error(f"Error in linear regression: {e}")
            raise
    
    async def exponential_decay(
        self,
        data: List[float],
        time_periods: List[float]
    ) -> Dict[str, Any]:
        """Fit exponential decay model y = a * e^(-b * t)"""
        try:
            if len(data) != len(time_periods) or len(data) < 2:
                raise ValueError("Data and time_periods must have same length and at least 2 points")
            
            x = np.array(time_periods)
            y = np.array(data)
            
            # Exponential decay function: y = a * exp(-b * x)
            def exp_decay(x, a, b):
                return a * np.exp(-b * x)
            
            # Initial guess
            a_init = data[0] if data[0] > 0 else 1.0
            b_init = 0.1
            
            # Fit the curve
            popt, pcov = curve_fit(exp_decay, x, y, p0=[a_init, b_init], maxfev=10000)
            a, b = popt
            
            # Calculate half-life: t_half = ln(2) / b
            half_life = np.log(2) / b if b > 0 else np.inf
            
            # Calculate R-squared
            y_pred = exp_decay(x, a, b)
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
            
            return {
                "decay_rate": float(b),
                "initial_value": float(a),
                "half_life": float(half_life),
                "r_squared": float(r_squared),
                "equation": f"y = {a:.2f} * e^(-{b:.4f} * t)"
            }
        except Exception as e:
            logger.error(f"Error in exponential decay: {e}")
            raise
    
    async def time_series_forecast(
        self,
        historical_data: List[Dict[str, Any]],
        periods: int
    ) -> Dict[str, Any]:
        """Generate time series forecast using Holt's linear trend with optimized parameters.

        Alpha (level) and beta (trend) are chosen via grid search to minimize
        one-step-ahead MSE on the historical data, rather than hardcoded.
        """
        try:
            if not historical_data:
                raise ValueError("Historical data is required")

            # Extract values and dates
            values = [d.get("value", 0) for d in historical_data]
            dates = [d.get("date") or d.get("period", i) for i, d in enumerate(historical_data)]

            if len(values) < 2:
                # Simple linear extrapolation
                if len(values) == 1:
                    forecast = [values[0]] * periods
                else:
                    forecast = []
                return {
                    "forecast": forecast,
                    "confidence_intervals": []
                }

            # Optimize alpha and beta via grid search on in-sample MSE
            alpha, beta = self._optimize_holt_params(values)

            # Run Holt's with optimized parameters
            level, trend_vals = self._holt_smooth(values, alpha, beta)

            last_level = level[-1]
            last_trend = trend_vals[-1]

            forecast = []
            confidence_intervals = []
            residuals = [
                values[i] - (level[i] + trend_vals[i])
                for i in range(len(values))
            ]
            std_dev = float(np.std(residuals)) if len(residuals) > 1 else abs(values[0]) * 0.1

            for i in range(1, periods + 1):
                forecast_value = last_level + last_trend * i
                forecast.append(forecast_value)

                margin = std_dev * (1 + i * 0.1)
                confidence_intervals.append({
                    "lower": forecast_value - margin,
                    "upper": forecast_value + margin
                })

            return {
                "forecast": forecast,
                "confidence_intervals": confidence_intervals,
                "method": "holts_linear_trend",
                "alpha": alpha,
                "beta": beta,
                "optimized": True,
            }
        except Exception as e:
            logger.error(f"Error in time series forecast: {e}")
            raise

    @staticmethod
    def _holt_smooth(
        values: List[float], alpha: float, beta: float
    ) -> tuple:
        """Run Holt's double exponential smoothing, return (level, trend) lists."""
        level = [values[0]]
        trend_vals = [values[1] - values[0] if len(values) > 1 else 0.0]

        for i in range(1, len(values)):
            new_level = alpha * values[i] + (1 - alpha) * (level[-1] + trend_vals[-1])
            new_trend = beta * (new_level - level[-1]) + (1 - beta) * trend_vals[-1]
            level.append(new_level)
            trend_vals.append(new_trend)

        return level, trend_vals

    def _optimize_holt_params(
        self, values: List[float]
    ) -> tuple:
        """Grid search for (alpha, beta) that minimizes one-step-ahead MSE.

        Tests 10x10 grid (0.05..0.95 for each). Falls back to (0.3, 0.1)
        if the series is too short to optimize (< 4 points).
        """
        if len(values) < 4:
            return 0.3, 0.1

        grid = np.arange(0.05, 1.0, 0.1)
        best_mse = float("inf")
        best_alpha, best_beta = 0.3, 0.1

        for a in grid:
            for b in grid:
                level, trend_vals = self._holt_smooth(values, float(a), float(b))
                # One-step-ahead errors: predict values[i] from level[i-1]+trend[i-1]
                errors = []
                for i in range(1, len(values)):
                    predicted = level[i - 1] + trend_vals[i - 1]
                    errors.append((values[i] - predicted) ** 2)
                mse = sum(errors) / len(errors)
                if mse < best_mse:
                    best_mse = mse
                    best_alpha, best_beta = float(a), float(b)

        return round(best_alpha, 2), round(best_beta, 2)
    
    async def monte_carlo_simulation(
        self,
        base_scenario: Dict[str, Any],
        distributions: Dict[str, Dict[str, float]],
        iterations: int = 1000
    ) -> Dict[str, Any]:
        """Run Monte Carlo simulation"""
        try:
            np.random.seed(42)  # For reproducibility
            
            results = []
            
            for _ in range(iterations):
                scenario = base_scenario.copy()
                
                # Sample from distributions
                for var_name, dist_params in distributions.items():
                    dist_type = dist_params.get("type", "normal")
                    
                    if dist_type == "normal":
                        mean = dist_params.get("mean", 0)
                        std = dist_params.get("std", 1)
                        scenario[var_name] = np.random.normal(mean, std)
                    elif dist_type == "uniform":
                        low = dist_params.get("low", 0)
                        high = dist_params.get("high", 1)
                        scenario[var_name] = np.random.uniform(low, high)
                    elif dist_type == "lognormal":
                        mean = dist_params.get("mean", 0)
                        std = dist_params.get("std", 1)
                        scenario[var_name] = np.random.lognormal(mean, std)
                
                results.append(scenario)
            
            # Calculate statistics
            output_vars = list(base_scenario.keys())
            statistics = {}
            
            for var in output_vars:
                values = [r[var] for r in results if var in r and isinstance(r[var], (int, float))]
                if values:
                    statistics[var] = {
                        "mean": float(np.mean(values)),
                        "std": float(np.std(values)),
                        "min": float(np.min(values)),
                        "max": float(np.max(values)),
                        "median": float(np.median(values)),
                        "p5": float(np.percentile(values, 5)),
                        "p95": float(np.percentile(values, 95))
                    }
            
            return {
                "results": results[:100],  # Return sample
                "statistics": statistics,
                "iterations": iterations
            }
        except Exception as e:
            logger.error(f"Error in Monte Carlo simulation: {e}")
            raise
    
    async def sensitivity_analysis(
        self,
        base_inputs: Dict[str, float],
        variable_ranges: Dict[str, List[float]],
        model_function: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Perform sensitivity analysis (tornado chart)"""
        try:
            if not model_function:
                # Default: simple linear model
                def default_model(inputs):
                    return sum(inputs.values())
                model_function = default_model
            
            base_output = model_function(base_inputs)
            
            tornado_data = []
            sensitivity_rankings = []
            
            for var_name, var_range in variable_ranges.items():
                if var_name not in base_inputs:
                    continue
                
                impacts = []
                for var_value in var_range:
                    test_inputs = base_inputs.copy()
                    test_inputs[var_name] = var_value
                    test_output = model_function(test_inputs)
                    impact = test_output - base_output
                    impacts.append({
                        "value": var_value,
                        "output": test_output,
                        "impact": impact
                    })
                
                # Calculate range of impacts
                impact_values = [i["impact"] for i in impacts]
                min_impact = min(impact_values)
                max_impact = max(impact_values)
                impact_range = max_impact - min_impact
                
                tornado_data.append({
                    "variable": var_name,
                    "min_impact": min_impact,
                    "max_impact": max_impact,
                    "impact_range": impact_range,
                    "base_value": base_inputs[var_name]
                })
                
                sensitivity_rankings.append({
                    "variable": var_name,
                    "sensitivity": abs(impact_range),
                    "impact_range": impact_range
                })
            
            # Sort by sensitivity
            sensitivity_rankings.sort(key=lambda x: x["sensitivity"], reverse=True)
            tornado_data.sort(key=lambda x: x["impact_range"], reverse=True)
            
            return {
                "tornado_chart_data": tornado_data,
                "sensitivity_rankings": sensitivity_rankings,
                "base_output": base_output
            }
        except Exception as e:
            logger.error(f"Error in sensitivity analysis: {e}")
            raise
    
    async def analyze_world_model_relationships(
        self,
        factors: List[Dict[str, Any]],
        target_factor_name: str
    ) -> Dict[str, Any]:
        """DEPRECATED: Use DriverImpactService.driver_impact_ranking() instead.

        This method computed fake ratios from single data points.
        Kept as a redirect for any callers that haven't migrated.
        """
        logger.warning(
            "analyze_world_model_relationships is deprecated. "
            "Use DriverImpactService.driver_impact_ranking() for real sensitivity analysis."
        )
        return {
            "target_factor": target_factor_name,
            "correlations": [],
            "message": (
                "DEPRECATED: This method produced fake ratios, not real correlations. "
                "Use DriverImpactService.correlate_actuals() for time-series correlation "
                "or DriverImpactService.driver_impact_ranking() for sensitivity analysis."
            ),
        }

    async def correlation_matrix(
        self,
        factors: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """DEPRECATED: Use DriverImpactService.correlate_actuals() instead.

        This method computed fake ratios from single data points.
        Kept as a redirect for any callers that haven't migrated.
        """
        logger.warning(
            "correlation_matrix is deprecated. "
            "Use DriverImpactService.correlate_actuals() for real correlation."
        )
        return {
            "matrix": {},
            "factors": [],
            "message": (
                "DEPRECATED: This method produced fake ratios, not real correlations. "
                "Use DriverImpactService.correlate_actuals() with two metric names "
                "for actual Pearson/Spearman correlation on time-series data."
            ),
        }
