"""
Analytics Bridge Service
Provides Monte Carlo simulations, sensitivity analysis, and advanced financial analytics
"""

import numpy as np
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
import asyncio
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class MonteCarloResult:
    """Result from Monte Carlo simulation"""
    mean: float
    median: float
    std_dev: float
    percentile_10: float
    percentile_25: float
    percentile_50: float
    percentile_75: float
    percentile_90: float
    simulations: List[float]
    
@dataclass
class SensitivityResult:
    """Result from sensitivity analysis"""
    base_case: float
    sensitivity_factors: Dict[str, Dict[str, float]]  # factor -> {low, base, high}
    tornado_chart_data: List[Dict[str, Any]]


class AnalyticsBridge:
    """
    Bridge service for advanced analytics including:
    - Monte Carlo simulations
    - Sensitivity analysis
    - Scenario modeling
    - Statistical analysis
    """
    
    def __init__(self):
        self.cache = {}
        logger.info("AnalyticsBridge initialized")
    
    async def process_analysis(
        self,
        company: str,
        analysis_type: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process various types of advanced analytics
        """
        logger.info(f"Processing {analysis_type} for {company}")
        
        if analysis_type == "monte_carlo":
            return await self._run_monte_carlo(company, parameters)
        elif analysis_type == "sensitivity":
            return await self._run_sensitivity_analysis(company, parameters)
        elif analysis_type == "scenario":
            return await self._run_scenario_analysis(company, parameters)
        elif analysis_type == "full_research":
            return await self._run_full_research(company, parameters)
        else:
            return {
                "status": "unsupported",
                "message": f"Analysis type {analysis_type} not yet implemented"
            }
    
    async def _run_monte_carlo(
        self,
        company: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run Monte Carlo simulation for valuation
        """
        # Extract parameters
        num_simulations = parameters.get("simulations", 10000)
        revenue_mean = parameters.get("revenue_mean", 10_000_000)
        revenue_std = parameters.get("revenue_std", 2_000_000)
        growth_mean = parameters.get("growth_mean", 0.3)
        growth_std = parameters.get("growth_std", 0.1)
        multiple_mean = parameters.get("multiple_mean", 5)
        multiple_std = parameters.get("multiple_std", 1)
        
        # Run simulations
        np.random.seed(42)  # For reproducibility
        
        revenues = np.random.normal(revenue_mean, revenue_std, num_simulations)
        growth_rates = np.random.normal(growth_mean, growth_std, num_simulations)
        multiples = np.random.normal(multiple_mean, multiple_std, num_simulations)
        
        # Calculate valuations
        future_revenues = revenues * (1 + growth_rates) ** 3  # 3-year projection
        valuations = future_revenues * multiples
        
        # Remove negative values
        valuations = valuations[valuations > 0]
        
        result = MonteCarloResult(
            mean=float(np.mean(valuations)),
            median=float(np.median(valuations)),
            std_dev=float(np.std(valuations)),
            percentile_10=float(np.percentile(valuations, 10)),
            percentile_25=float(np.percentile(valuations, 25)),
            percentile_50=float(np.percentile(valuations, 50)),
            percentile_75=float(np.percentile(valuations, 75)),
            percentile_90=float(np.percentile(valuations, 90)),
            simulations=valuations[:100].tolist()  # Return sample for visualization
        )
        
        return {
            "company": company,
            "analysis_type": "monte_carlo",
            "results": {
                "mean_valuation": result.mean,
                "median_valuation": result.median,
                "std_deviation": result.std_dev,
                "confidence_intervals": {
                    "10%": result.percentile_10,
                    "25%": result.percentile_25,
                    "50%": result.percentile_50,
                    "75%": result.percentile_75,
                    "90%": result.percentile_90
                },
                "probability_above_target": self._calculate_probability_above(
                    valuations, parameters.get("target_valuation", result.mean)
                ),
                "sample_simulations": result.simulations
            },
            "parameters_used": {
                "simulations": num_simulations,
                "revenue_assumptions": {
                    "mean": revenue_mean,
                    "std_dev": revenue_std
                },
                "growth_assumptions": {
                    "mean": growth_mean,
                    "std_dev": growth_std
                },
                "multiple_assumptions": {
                    "mean": multiple_mean,
                    "std_dev": multiple_std
                }
            }
        }
    
    async def _run_sensitivity_analysis(
        self,
        company: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run sensitivity analysis on key valuation drivers
        """
        base_revenue = parameters.get("base_revenue", 10_000_000)
        base_growth = parameters.get("base_growth", 0.3)
        base_multiple = parameters.get("base_multiple", 5)
        
        # Define sensitivity ranges (±20%)
        sensitivity_factors = {
            "revenue": {"low": base_revenue * 0.8, "base": base_revenue, "high": base_revenue * 1.2},
            "growth_rate": {"low": base_growth * 0.8, "base": base_growth, "high": base_growth * 1.2},
            "exit_multiple": {"low": base_multiple * 0.8, "base": base_multiple, "high": base_multiple * 1.2}
        }
        
        # Calculate base case
        base_case = base_revenue * (1 + base_growth) ** 3 * base_multiple
        
        # Calculate sensitivities
        tornado_data = []
        for factor, values in sensitivity_factors.items():
            if factor == "revenue":
                low_val = values["low"] * (1 + base_growth) ** 3 * base_multiple
                high_val = values["high"] * (1 + base_growth) ** 3 * base_multiple
            elif factor == "growth_rate":
                low_val = base_revenue * (1 + values["low"]) ** 3 * base_multiple
                high_val = base_revenue * (1 + values["high"]) ** 3 * base_multiple
            else:  # exit_multiple
                low_val = base_revenue * (1 + base_growth) ** 3 * values["low"]
                high_val = base_revenue * (1 + base_growth) ** 3 * values["high"]
            
            tornado_data.append({
                "factor": factor,
                "low_impact": (low_val - base_case) / base_case,
                "high_impact": (high_val - base_case) / base_case,
                "low_value": low_val,
                "high_value": high_val
            })
        
        # Sort by impact magnitude
        tornado_data.sort(key=lambda x: abs(x["high_impact"] - x["low_impact"]), reverse=True)
        
        return {
            "company": company,
            "analysis_type": "sensitivity",
            "results": {
                "base_case_valuation": base_case,
                "sensitivity_factors": sensitivity_factors,
                "tornado_chart": tornado_data,
                "most_sensitive_factor": tornado_data[0]["factor"] if tornado_data else None,
                "sensitivity_ranges": {
                    factor: {
                        "min": data["low_value"],
                        "max": data["high_value"],
                        "range": data["high_value"] - data["low_value"]
                    }
                    for factor, data in zip(
                        [d["factor"] for d in tornado_data],
                        tornado_data
                    )
                }
            }
        }
    
    async def _run_scenario_analysis(
        self,
        company: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run scenario analysis (bear, base, bull cases)
        """
        scenarios = {
            "bear": {
                "revenue": parameters.get("bear_revenue", 5_000_000),
                "growth": parameters.get("bear_growth", 0.1),
                "multiple": parameters.get("bear_multiple", 3),
                "probability": parameters.get("bear_probability", 0.25)
            },
            "base": {
                "revenue": parameters.get("base_revenue", 10_000_000),
                "growth": parameters.get("base_growth", 0.3),
                "multiple": parameters.get("base_multiple", 5),
                "probability": parameters.get("base_probability", 0.5)
            },
            "bull": {
                "revenue": parameters.get("bull_revenue", 15_000_000),
                "growth": parameters.get("bull_growth", 0.5),
                "multiple": parameters.get("bull_multiple", 8),
                "probability": parameters.get("bull_probability", 0.25)
            }
        }
        
        results = {}
        for scenario_name, scenario_params in scenarios.items():
            valuation = (
                scenario_params["revenue"] *
                (1 + scenario_params["growth"]) ** 3 *
                scenario_params["multiple"]
            )
            results[scenario_name] = {
                "valuation": valuation,
                "probability": scenario_params["probability"],
                "parameters": scenario_params
            }
        
        # Calculate probability-weighted valuation
        weighted_valuation = sum(
            result["valuation"] * result["probability"]
            for result in results.values()
        )
        
        return {
            "company": company,
            "analysis_type": "scenario",
            "results": {
                "scenarios": results,
                "probability_weighted_valuation": weighted_valuation,
                "valuation_range": {
                    "min": results["bear"]["valuation"],
                    "max": results["bull"]["valuation"],
                    "spread": results["bull"]["valuation"] - results["bear"]["valuation"]
                }
            }
        }
    
    async def _run_full_research(
        self,
        company: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run comprehensive research combining all analytics
        """
        # Run all analyses in parallel
        monte_carlo_task = self._run_monte_carlo(company, parameters)
        sensitivity_task = self._run_sensitivity_analysis(company, parameters)
        scenario_task = self._run_scenario_analysis(company, parameters)
        
        results = await asyncio.gather(
            monte_carlo_task,
            sensitivity_task,
            scenario_task
        )
        
        return {
            "company": company,
            "analysis_type": "full_research",
            "timestamp": datetime.utcnow().isoformat(),
            "results": {
                "monte_carlo": results[0]["results"],
                "sensitivity": results[1]["results"],
                "scenario": results[2]["results"],
                "executive_summary": self._generate_executive_summary(results)
            }
        }
    
    def _calculate_probability_above(
        self,
        simulations: np.ndarray,
        target: float
    ) -> float:
        """Calculate probability of exceeding target value"""
        return float(np.mean(simulations > target))
    
    def _generate_executive_summary(self, results: List[Dict]) -> Dict[str, Any]:
        """Generate executive summary from all analyses"""
        monte_carlo = results[0]["results"]
        sensitivity = results[1]["results"]
        scenario = results[2]["results"]
        
        return {
            "valuation_range": {
                "conservative": monte_carlo["confidence_intervals"]["25%"],
                "likely": monte_carlo["median_valuation"],
                "optimistic": monte_carlo["confidence_intervals"]["75%"]
            },
            "key_drivers": sensitivity["most_sensitive_factor"],
            "recommended_valuation": scenario["probability_weighted_valuation"],
            "confidence_level": "high" if monte_carlo["std_deviation"] / monte_carlo["mean_valuation"] < 0.3 else "moderate"
        }
    
    async def get_cached_analysis(
        self,
        company: str,
        analysis_type: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached analysis if available"""
        cache_key = f"{company}_{analysis_type}"
        return self.cache.get(cache_key)