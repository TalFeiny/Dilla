"""
Agent-Ready Financial and Arithmetic Tools
Production-ready tools for spreadsheet and financial calculations
"""

from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
import logging
from app.services.financial_calculator import financial_calc, bond_calc, options_calc
from app.services.arithmetic_engine import arithmetic_engine
from app.services.formula_evaluator import formula_evaluator

logger = logging.getLogger(__name__)


class FinancialTools:
    """Collection of financial calculation tools for agent use"""
    
    @staticmethod
    def calculate_npv(discount_rate: float, cash_flows: List[float]) -> Dict[str, Any]:
        """
        Calculate Net Present Value of cash flows
        
        Args:
            discount_rate: Discount rate (e.g., 0.10 for 10%)
            cash_flows: List of cash flows [initial_investment, year1, year2, ...]
        
        Returns:
            Dictionary with NPV result and analysis
        """
        try:
            npv = financial_calc.npv(discount_rate, cash_flows)
            
            # Additional analysis
            total_cash_flows = sum(cash_flows[1:])  # Exclude initial investment
            initial_investment = abs(cash_flows[0]) if cash_flows else 0
            
            result = {
                "npv": npv,
                "discount_rate": discount_rate,
                "cash_flows": cash_flows,
                "total_undiscounted_cash_flows": total_cash_flows,
                "initial_investment": initial_investment,
                "profitable": npv > 0,
                "recommendation": "Accept project" if npv > 0 else "Reject project",
                "profitability_index": (npv + initial_investment) / initial_investment if initial_investment > 0 else 0
            }
            
            return result
            
        except Exception as e:
            logger.error(f"NPV calculation error: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def calculate_irr(cash_flows: List[float]) -> Dict[str, Any]:
        """
        Calculate Internal Rate of Return
        
        Args:
            cash_flows: List of cash flows [initial_investment, year1, year2, ...]
        
        Returns:
            Dictionary with IRR result and analysis
        """
        try:
            irr = financial_calc.irr(cash_flows)
            
            if irr is None:
                return {"error": "IRR cannot be calculated (no sign changes in cash flows)"}
            
            result = {
                "irr": irr,
                "irr_percentage": irr * 100,
                "cash_flows": cash_flows,
                "periods": len(cash_flows) - 1,
                "annualized_return": f"{irr:.1%}"
            }
            
            return result
            
        except Exception as e:
            logger.error(f"IRR calculation error: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def calculate_loan_payment(principal: float, annual_rate: float, years: int, 
                             payment_frequency: int = 12) -> Dict[str, Any]:
        """
        Calculate loan payment details
        
        Args:
            principal: Loan amount
            annual_rate: Annual interest rate (e.g., 0.05 for 5%)
            years: Loan term in years
            payment_frequency: Payments per year (12 for monthly)
        
        Returns:
            Complete loan analysis
        """
        try:
            periodic_rate = annual_rate / payment_frequency
            total_payments = years * payment_frequency
            
            payment = financial_calc.pmt(periodic_rate, total_payments, principal)
            total_interest = (payment * total_payments) - principal
            
            result = {
                "monthly_payment": abs(payment),
                "total_payments": total_payments,
                "total_interest": total_interest,
                "total_cost": principal + total_interest,
                "principal": principal,
                "annual_rate": annual_rate,
                "annual_rate_percentage": annual_rate * 100,
                "years": years,
                "payment_frequency": payment_frequency,
                "interest_to_principal_ratio": total_interest / principal if principal > 0 else 0,
                
                # Payment schedule (first few payments)
                "sample_schedule": FinancialTools._create_payment_schedule(
                    principal, payment, periodic_rate, 6
                )
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Loan payment calculation error: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def _create_payment_schedule(principal: float, payment: float, 
                               rate: float, num_payments: int) -> List[Dict]:
        """Create sample payment schedule"""
        schedule = []
        remaining_balance = principal
        
        for payment_num in range(1, min(num_payments + 1, 100)):
            interest_payment = remaining_balance * rate
            principal_payment = abs(payment) - interest_payment
            remaining_balance -= principal_payment
            
            schedule.append({
                "payment_number": payment_num,
                "payment_amount": abs(payment),
                "principal_payment": principal_payment,
                "interest_payment": interest_payment,
                "remaining_balance": max(0, remaining_balance)
            })
            
            if remaining_balance <= 0:
                break
        
        return schedule
    
    @staticmethod
    def calculate_investment_growth(initial_amount: float, annual_return: float, 
                                  years: int, additional_monthly: float = 0) -> Dict[str, Any]:
        """
        Calculate investment growth with compound interest
        
        Args:
            initial_amount: Starting investment
            annual_return: Expected annual return (e.g., 0.07 for 7%)
            years: Investment period
            additional_monthly: Monthly additional contributions
        
        Returns:
            Investment growth projection
        """
        try:
            # Simple compound interest for initial amount
            final_value_initial = initial_amount * ((1 + annual_return) ** years)
            
            # Future value of annuity for monthly contributions
            if additional_monthly > 0:
                monthly_rate = annual_return / 12
                months = years * 12
                fv_annuity = additional_monthly * (((1 + monthly_rate) ** months - 1) / monthly_rate)
            else:
                fv_annuity = 0
            
            total_final_value = final_value_initial + fv_annuity
            total_contributions = initial_amount + (additional_monthly * 12 * years)
            total_growth = total_final_value - total_contributions
            
            # Year-by-year breakdown
            yearly_values = []
            current_value = initial_amount
            for year in range(1, years + 1):
                # Growth from existing investments
                current_value *= (1 + annual_return)
                # Add annual contributions
                current_value += additional_monthly * 12
                
                yearly_values.append({
                    "year": year,
                    "value": current_value,
                    "total_contributions": initial_amount + (additional_monthly * 12 * year),
                    "growth": current_value - (initial_amount + (additional_monthly * 12 * year))
                })
            
            result = {
                "initial_investment": initial_amount,
                "annual_return": annual_return,
                "annual_return_percentage": annual_return * 100,
                "years": years,
                "monthly_contributions": additional_monthly,
                "final_value": total_final_value,
                "total_contributions": total_contributions,
                "total_growth": total_growth,
                "growth_percentage": (total_growth / total_contributions * 100) if total_contributions > 0 else 0,
                "effective_annual_return": ((total_final_value / total_contributions) ** (1/years) - 1) if total_contributions > 0 else 0,
                "yearly_breakdown": yearly_values[-5:] if len(yearly_values) > 5 else yearly_values  # Last 5 years
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Investment growth calculation error: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def calculate_bond_price(face_value: float, coupon_rate: float, 
                           market_rate: float, years_to_maturity: int) -> Dict[str, Any]:
        """
        Calculate bond pricing and analysis
        
        Args:
            face_value: Par value of bond
            coupon_rate: Annual coupon rate
            market_rate: Current market interest rate
            years_to_maturity: Years until maturity
        
        Returns:
            Bond analysis including price, yield, duration
        """
        try:
            bond_price = bond_calc.price(market_rate, coupon_rate, face_value, years_to_maturity)
            duration = bond_calc.duration(market_rate, coupon_rate, face_value, years_to_maturity)
            convexity = bond_calc.convexity(market_rate, coupon_rate, face_value, years_to_maturity)
            
            annual_coupon = face_value * coupon_rate
            current_yield = annual_coupon / bond_price if bond_price > 0 else 0
            
            result = {
                "bond_price": bond_price,
                "face_value": face_value,
                "coupon_rate": coupon_rate,
                "coupon_rate_percentage": coupon_rate * 100,
                "market_rate": market_rate,
                "market_rate_percentage": market_rate * 100,
                "years_to_maturity": years_to_maturity,
                "annual_coupon_payment": annual_coupon,
                "current_yield": current_yield,
                "current_yield_percentage": current_yield * 100,
                "duration": duration,
                "convexity": convexity,
                "premium_discount": "Premium" if bond_price > face_value else "Discount" if bond_price < face_value else "Par",
                "price_sensitivity": f"1% rate change = ${duration * bond_price * 0.01:.2f} price change"
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Bond calculation error: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def create_financial_model(revenue: float, growth_rate: float, 
                             margins: Dict[str, float], years: int = 5) -> Dict[str, Any]:
        """
        Create a comprehensive financial model
        
        Args:
            revenue: Base year revenue
            growth_rate: Annual revenue growth rate
            margins: Dictionary of margin assumptions (gross, operating, net)
            years: Number of years to project
        
        Returns:
            Complete financial model with projections
        """
        try:
            model = {
                "assumptions": {
                    "base_revenue": revenue,
                    "growth_rate": growth_rate,
                    "growth_rate_percentage": growth_rate * 100,
                    "margins": margins,
                    "projection_years": years
                },
                "projections": []
            }
            
            for year in range(1, years + 1):
                # Revenue projection
                projected_revenue = revenue * ((1 + growth_rate) ** year)
                
                # Cost and profit calculations
                gross_margin = margins.get('gross', 0.6)
                operating_margin = margins.get('operating', 0.2)
                net_margin = margins.get('net', 0.15)
                
                cogs = projected_revenue * (1 - gross_margin)
                gross_profit = projected_revenue - cogs
                
                operating_expenses = projected_revenue * (gross_margin - operating_margin)
                operating_income = gross_profit - operating_expenses
                
                net_income = projected_revenue * net_margin
                
                year_projection = {
                    "year": year,
                    "revenue": projected_revenue,
                    "cogs": cogs,
                    "gross_profit": gross_profit,
                    "gross_margin_percentage": (gross_profit / projected_revenue * 100),
                    "operating_expenses": operating_expenses,
                    "operating_income": operating_income,
                    "operating_margin_percentage": (operating_income / projected_revenue * 100),
                    "net_income": net_income,
                    "net_margin_percentage": net_margin * 100,
                    
                    # Additional metrics
                    "revenue_growth_yoy": growth_rate * 100 if year > 1 else 0,
                    "cumulative_revenue": sum(p.get("revenue", 0) for p in model["projections"]) + projected_revenue
                }
                
                model["projections"].append(year_projection)
            
            # Summary metrics
            total_revenue = sum(p["revenue"] for p in model["projections"])
            total_net_income = sum(p["net_income"] for p in model["projections"])
            
            model["summary"] = {
                "total_projected_revenue": total_revenue,
                "total_projected_net_income": total_net_income,
                "average_annual_revenue": total_revenue / years,
                "average_annual_net_income": total_net_income / years,
                "final_year_revenue": model["projections"][-1]["revenue"] if model["projections"] else 0,
                "revenue_cagr": ((model["projections"][-1]["revenue"] / revenue) ** (1/years) - 1) * 100 if model["projections"] else 0
            }
            
            return model
            
        except Exception as e:
            logger.error(f"Financial model creation error: {e}")
            return {"error": str(e)}


class SpreadsheetTools:
    """Collection of spreadsheet calculation tools"""
    
    @staticmethod
    def evaluate_formula(formula: str, cell_values: Dict[str, Any] = None, 
                        named_ranges: Dict[str, List] = None) -> Dict[str, Any]:
        """
        Evaluate Excel-style formula
        
        Args:
            formula: Formula string (with or without =)
            cell_values: Dictionary of cell references and values
            named_ranges: Dictionary of named ranges
        
        Returns:
            Formula evaluation result
        """
        try:
            # Set up evaluator
            if cell_values:
                for cell_ref, value in cell_values.items():
                    formula_evaluator.set_cell_value(cell_ref, value)
            
            if named_ranges:
                for name, values in named_ranges.items():
                    formula_evaluator.set_named_range(name, values)
            
            # Evaluate formula
            result = formula_evaluator.evaluate(formula)
            
            return {
                "formula": formula,
                "result": result,
                "result_type": type(result).__name__,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Formula evaluation error: {e}")
            return {
                "formula": formula,
                "error": str(e),
                "success": False
            }
    
    @staticmethod
    def calculate_statistics(values: List[Union[int, float]]) -> Dict[str, Any]:
        """
        Calculate comprehensive statistics for a dataset
        
        Args:
            values: List of numeric values
        
        Returns:
            Statistical analysis
        """
        try:
            if not values:
                return {"error": "No values provided"}
            
            # Basic statistics
            result = {
                "count": arithmetic_engine.count(*values),
                "sum": arithmetic_engine.sum(*values),
                "average": arithmetic_engine.average(*values),
                "median": arithmetic_engine.median(*values),
                "mode": arithmetic_engine.mode(*values) if len(set(values)) < len(values) else "No mode",
                "min": arithmetic_engine.min(*values),
                "max": arithmetic_engine.max(*values),
                "range": arithmetic_engine.max(*values) - arithmetic_engine.min(*values),
                "standard_deviation": arithmetic_engine.stdev(*values),
                "variance": arithmetic_engine.var(*values),
                
                # Additional metrics
                "coefficient_of_variation": (arithmetic_engine.stdev(*values) / arithmetic_engine.average(*values)) * 100 if arithmetic_engine.average(*values) != 0 else 0,
                "skewness": SpreadsheetTools._calculate_skewness(values),
                "kurtosis": SpreadsheetTools._calculate_kurtosis(values),
                
                # Quartiles
                "q1": SpreadsheetTools._percentile(values, 25),
                "q2": arithmetic_engine.median(*values),
                "q3": SpreadsheetTools._percentile(values, 75),
                "iqr": SpreadsheetTools._percentile(values, 75) - SpreadsheetTools._percentile(values, 25)
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Statistics calculation error: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def _calculate_skewness(values: List[float]) -> float:
        """Calculate skewness of dataset"""
        try:
            from scipy import stats
            return stats.skew(values)
        except ImportError:
            # Fallback calculation
            n = len(values)
            if n < 3:
                return 0
            mean = sum(values) / n
            std = (sum((x - mean) ** 2 for x in values) / (n - 1)) ** 0.5
            skewness = sum((x - mean) ** 3 for x in values) / (n * std ** 3)
            return skewness
    
    @staticmethod
    def _calculate_kurtosis(values: List[float]) -> float:
        """Calculate kurtosis of dataset"""
        try:
            from scipy import stats
            return stats.kurtosis(values)
        except ImportError:
            # Fallback calculation
            n = len(values)
            if n < 4:
                return 0
            mean = sum(values) / n
            std = (sum((x - mean) ** 2 for x in values) / (n - 1)) ** 0.5
            kurtosis = sum((x - mean) ** 4 for x in values) / (n * std ** 4) - 3
            return kurtosis
    
    @staticmethod
    def _percentile(values: List[float], percentile: float) -> float:
        """Calculate percentile of dataset"""
        sorted_values = sorted(values)
        n = len(sorted_values)
        if n == 0:
            return 0
        
        index = (percentile / 100) * (n - 1)
        lower = int(index)
        upper = min(lower + 1, n - 1)
        
        if lower == upper:
            return sorted_values[lower]
        
        weight = index - lower
        return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
    
    @staticmethod
    def create_pivot_summary(data: List[Dict[str, Any]], 
                           group_by: str, aggregate_field: str, 
                           operation: str = "sum") -> Dict[str, Any]:
        """
        Create pivot table summary
        
        Args:
            data: List of dictionaries with data
            group_by: Field to group by
            aggregate_field: Field to aggregate
            operation: Aggregation operation (sum, average, count, min, max)
        
        Returns:
            Pivot table summary
        """
        try:
            groups = {}
            
            for row in data:
                group_value = row.get(group_by, "Unknown")
                agg_value = row.get(aggregate_field, 0)
                
                if group_value not in groups:
                    groups[group_value] = []
                
                groups[group_value].append(agg_value)
            
            # Aggregate by operation
            result = {}
            total = 0
            
            for group, values in groups.items():
                if operation == "sum":
                    agg_result = arithmetic_engine.sum(*values)
                elif operation == "average":
                    agg_result = arithmetic_engine.average(*values)
                elif operation == "count":
                    agg_result = len(values)
                elif operation == "min":
                    agg_result = arithmetic_engine.min(*values)
                elif operation == "max":
                    agg_result = arithmetic_engine.max(*values)
                else:
                    agg_result = arithmetic_engine.sum(*values)
                
                result[group] = agg_result
                total += agg_result if operation != "count" else len(values)
            
            return {
                "pivot_data": result,
                "group_by": group_by,
                "aggregate_field": aggregate_field,
                "operation": operation,
                "total": total,
                "group_count": len(result),
                "summary": f"Grouped {len(data)} records by {group_by}, {operation} of {aggregate_field}"
            }
            
        except Exception as e:
            logger.error(f"Pivot summary error: {e}")
            return {"error": str(e)}


# Create singleton instances for agent use
financial_tools = FinancialTools()
spreadsheet_tools = SpreadsheetTools()