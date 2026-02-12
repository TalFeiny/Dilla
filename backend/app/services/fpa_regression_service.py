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
            # TODO: Implement using numpy/scipy
            slope, intercept = np.polyfit(x, y, 1)
            r_squared = np.corrcoef(x, y)[0, 1] ** 2
            
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
        """Generate time series forecast using exponential smoothing"""
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
            
            # Simple exponential smoothing
            alpha = 0.3  # Smoothing parameter
            smoothed = [values[0]]
            for i in range(1, len(values)):
                smoothed.append(alpha * values[i] + (1 - alpha) * smoothed[-1])
            
            # Forecast future periods
            last_smoothed = smoothed[-1]
            last_value = values[-1]
            trend = (values[-1] - values[0]) / len(values) if len(values) > 1 else 0
            
            forecast = []
            confidence_intervals = []
            for i in range(1, periods + 1):
                # Simple trend extrapolation
                forecast_value = last_value + trend * i
                forecast.append(forecast_value)
                
                # Simple confidence interval (wider as we go further out)
                std_dev = np.std(values) if len(values) > 1 else abs(values[0]) * 0.1
                margin = std_dev * (1 + i * 0.1)  # Increasing uncertainty
                confidence_intervals.append({
                    "lower": forecast_value - margin,
                    "upper": forecast_value + margin
                })
            
            return {
                "forecast": forecast,
                "confidence_intervals": confidence_intervals,
                "method": "exponential_smoothing",
                "alpha": alpha
            }
        except Exception as e:
            logger.error(f"Error in time series forecast: {e}")
            raise
    
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
        """
        Analyze relationships between qualitative and quantitative factors in a world model
        
        Args:
            factors: List of factor dictionaries from world model
            target_factor_name: Factor to analyze relationships for
            
        Returns:
            Analysis of which factors correlate with the target
        """
        try:
            # Find target factor
            target_factor = next((f for f in factors if f["factor_name"] == target_factor_name), None)
            if not target_factor:
                raise ValueError(f"Target factor {target_factor_name} not found")
            
            target_value = target_factor.get("current_value")
            if not isinstance(target_value, (int, float)):
                # Try to extract numeric value
                if isinstance(target_value, dict) and "score" in target_value:
                    target_value = target_value["score"]
                else:
                    raise ValueError(f"Target factor {target_factor_name} has non-numeric value")
            
            # Collect other factors with numeric values
            other_factors = []
            for factor in factors:
                if factor["factor_name"] == target_factor_name:
                    continue
                
                value = factor.get("current_value")
                if isinstance(value, (int, float)):
                    other_factors.append({
                        "factor_name": factor["factor_name"],
                        "factor_type": factor.get("factor_type"),
                        "factor_category": factor.get("factor_category"),
                        "value": value
                    })
                elif isinstance(value, dict) and "score" in value:
                    other_factors.append({
                        "factor_name": factor["factor_name"],
                        "factor_type": factor.get("factor_type"),
                        "factor_category": factor.get("factor_category"),
                        "value": value["score"]
                    })
            
            if len(other_factors) < 2:
                return {
                    "target_factor": target_factor_name,
                    "correlations": [],
                    "message": "Not enough factors for correlation analysis"
                }
            
            # Calculate correlations
            correlations = []
            for factor in other_factors:
                # For single data point, we can't calculate correlation
                # This would need multiple companies or time series
                # For now, calculate simple relationship strength
                other_value = factor["value"]
                
                # Normalize both values to 0-1 scale for comparison
                # This is a simplified approach - real correlation needs multiple data points
                if target_value != 0 and other_value != 0:
                    ratio = other_value / target_value if target_value != 0 else 0
                    relationship_strength = 1.0 - abs(1.0 - ratio)  # Closer to 1.0 = stronger relationship
                else:
                    relationship_strength = 0.0
                
                correlations.append({
                    "factor_name": factor["factor_name"],
                    "factor_type": factor["factor_type"],
                    "factor_category": factor["factor_category"],
                    "value": other_value,
                    "relationship_strength": relationship_strength,
                    "target_value": target_value
                })
            
            # Sort by relationship strength
            correlations.sort(key=lambda x: x["relationship_strength"], reverse=True)
            
            return {
                "target_factor": target_factor_name,
                "target_value": target_value,
                "correlations": correlations,
                "strongest_relationships": correlations[:5]
            }
        except Exception as e:
            logger.error(f"Error analyzing world model relationships: {e}")
            raise
    
    async def correlation_matrix(
        self,
        factors: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate correlation matrix for all numeric factors in a world model
        
        Note: This requires multiple data points (companies or time series)
        For single data point, returns relationship strengths instead
        """
        try:
            # Extract numeric factors
            numeric_factors = []
            for factor in factors:
                value = factor.get("current_value")
                if isinstance(value, (int, float)):
                    numeric_factors.append({
                        "name": factor["factor_name"],
                        "value": value,
                        "type": factor.get("factor_type"),
                        "category": factor.get("factor_category")
                    })
                elif isinstance(value, dict) and "score" in value:
                    numeric_factors.append({
                        "name": factor["factor_name"],
                        "value": value["score"],
                        "type": factor.get("factor_type"),
                        "category": factor.get("factor_category")
                    })
            
            if len(numeric_factors) < 2:
                return {
                    "matrix": {},
                    "message": "Not enough numeric factors for correlation matrix"
                }
            
            # Build correlation-like matrix (relationship strengths)
            matrix = {}
            for i, factor1 in enumerate(numeric_factors):
                matrix[factor1["name"]] = {}
                for factor2 in numeric_factors:
                    if factor1["name"] == factor2["name"]:
                        matrix[factor1["name"]][factor2["name"]] = 1.0
                    else:
                        # Calculate relationship strength
                        val1 = factor1["value"]
                        val2 = factor2["value"]
                        if val1 != 0 and val2 != 0:
                            ratio = val2 / val1 if val1 != 0 else 0
                            strength = 1.0 - min(1.0, abs(1.0 - ratio))
                        else:
                            strength = 0.0
                        matrix[factor1["name"]][factor2["name"]] = strength
            
            return {
                "matrix": matrix,
                "factors": [f["name"] for f in numeric_factors],
                "note": "Relationship strengths calculated from single data point. For true correlations, multiple data points required."
            }
        except Exception as e:
            logger.error(f"Error calculating correlation matrix: {e}")
            raise
