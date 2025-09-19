"""
Excel Agent Tools - Production Ready
Simple interface for agents to use Excel functionality
"""

from typing import Dict, Any, List, Optional
from app.services.production_excel import excel as excel_engine
from app.services.financial_calculator import financial_calc
import logging

logger = logging.getLogger(__name__)


class ExcelAgent:
    """Excel tools for agent use - handles ALL complex formulas"""
    
    def __init__(self):
        self.excel = excel_engine
        self.financial = financial_calc
        
    def evaluate_formula(self, formula: str, cells: Dict[str, Any] = None) -> Any:
        """
        Evaluate any Excel formula with optional cell values
        
        Examples:
            evaluate_formula('=SUM(A1:A10)', {'A1': 100, 'A2': 200, ...})
            evaluate_formula('=NPV(0.1,-1000,300,400,500)')
            evaluate_formula('=IF(A1>100,A1*2,A1/2)', {'A1': 150})
        """
        try:
            # Set cell values if provided
            if cells:
                for ref, value in cells.items():
                    self.excel.set_cell(ref, value)
            
            # Evaluate the formula
            result = self.excel.evaluate(formula)
            
            return {
                'success': True,
                'result': result,
                'formula': formula
            }
            
        except Exception as e:
            logger.error(f"Formula evaluation error: {e}")
            return {
                'success': False,
                'error': str(e),
                'formula': formula
            }
    
    def financial_analysis(self, analysis_type: str, **params) -> Dict[str, Any]:
        """
        Perform financial analysis
        
        Types:
            'npv': params = discount_rate, cash_flows
            'irr': params = cash_flows
            'loan': params = principal, rate, years
            'investment': params = initial, rate, years, monthly_add
        """
        try:
            if analysis_type == 'npv':
                rate = params.get('discount_rate', 0.1)
                flows = params.get('cash_flows', [])
                npv = self.financial.npv(rate, flows)
                
                return {
                    'success': True,
                    'type': 'npv',
                    'result': npv,
                    'profitable': npv > 0,
                    'recommendation': 'Accept' if npv > 0 else 'Reject'
                }
                
            elif analysis_type == 'irr':
                flows = params.get('cash_flows', [])
                irr = self.financial.irr(flows)
                
                return {
                    'success': True,
                    'type': 'irr',
                    'result': irr,
                    'percentage': f"{irr:.1%}" if irr else "N/A"
                }
                
            elif analysis_type == 'loan':
                principal = params.get('principal', 0)
                rate = params.get('rate', 0.05)
                years = params.get('years', 30)
                
                monthly_rate = rate / 12
                months = years * 12
                payment = self.financial.pmt(monthly_rate, months, principal)
                
                return {
                    'success': True,
                    'type': 'loan',
                    'monthly_payment': abs(payment),
                    'total_payments': abs(payment) * months,
                    'total_interest': abs(payment) * months - principal
                }
                
            elif analysis_type == 'investment':
                initial = params.get('initial', 0)
                rate = params.get('rate', 0.07)
                years = params.get('years', 10)
                monthly_add = params.get('monthly_add', 0)
                
                # Future value of initial
                fv_initial = self.financial.fv(rate, years, 0, -initial)
                
                # Future value of monthly contributions
                if monthly_add > 0:
                    monthly_rate = rate / 12
                    months = years * 12
                    fv_monthly = self.financial.fv(monthly_rate, months, -monthly_add)
                else:
                    fv_monthly = 0
                
                total_fv = fv_initial + fv_monthly
                total_invested = initial + (monthly_add * 12 * years)
                
                return {
                    'success': True,
                    'type': 'investment',
                    'final_value': total_fv,
                    'total_invested': total_invested,
                    'total_growth': total_fv - total_invested,
                    'return_percentage': ((total_fv / total_invested) - 1) * 100 if total_invested > 0 else 0
                }
                
            else:
                return {
                    'success': False,
                    'error': f"Unknown analysis type: {analysis_type}"
                }
                
        except Exception as e:
            logger.error(f"Financial analysis error: {e}")
            return {
                'success': False,
                'error': str(e),
                'type': analysis_type
            }
    
    def create_spreadsheet(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a spreadsheet with data and formulas
        
        Example:
            data = {
                'cells': {'A1': 100, 'A2': 200, 'B1': '=A1+A2'},
                'formulas': {'C1': '=SUM(A1:A2)', 'C2': '=AVERAGE(A1:A2)'}
            }
        """
        try:
            results = {}
            
            # Set regular cells
            if 'cells' in data:
                for ref, value in data['cells'].items():
                    self.excel.set_cell(ref, value)
                    results[ref] = value
            
            # Set and evaluate formulas
            if 'formulas' in data:
                for ref, formula in data['formulas'].items():
                    self.excel.set_cell(ref, formula)
                    results[ref] = self.excel.get_cell(ref)
            
            return {
                'success': True,
                'spreadsheet': results,
                'cell_count': len(results)
            }
            
        except Exception as e:
            logger.error(f"Spreadsheet creation error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def batch_calculate(self, calculations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Perform multiple calculations in batch
        
        Example:
            calculations = [
                {'formula': '=NPV(0.1,-1000,300,400,500)'},
                {'formula': '=SUM(A1:A10)', 'cells': {'A1': 100, 'A2': 200, ...}}
            ]
        """
        results = []
        
        for calc in calculations:
            formula = calc.get('formula', '')
            cells = calc.get('cells', {})
            
            result = self.evaluate_formula(formula, cells)
            results.append(result)
        
        return results
    
    def financial_model(self, revenue: float, growth_rate: float, 
                       years: int = 5, margins: Dict[str, float] = None) -> Dict[str, Any]:
        """
        Create a financial model projection
        """
        try:
            if margins is None:
                margins = {
                    'gross': 0.6,
                    'operating': 0.2,
                    'net': 0.15
                }
            
            projections = []
            
            for year in range(1, years + 1):
                year_revenue = revenue * ((1 + growth_rate) ** year)
                
                projection = {
                    'year': year,
                    'revenue': year_revenue,
                    'gross_profit': year_revenue * margins.get('gross', 0.6),
                    'operating_income': year_revenue * margins.get('operating', 0.2),
                    'net_income': year_revenue * margins.get('net', 0.15)
                }
                
                projections.append(projection)
            
            # Calculate summary metrics
            total_revenue = sum(p['revenue'] for p in projections)
            total_net_income = sum(p['net_income'] for p in projections)
            
            # Simple DCF valuation
            dcf_discount_rate = 0.12
            terminal_growth = 0.03
            
            # Calculate NPV of cash flows
            cash_flows = [-revenue]  # Initial investment (negative of current revenue)
            for p in projections:
                cash_flows.append(p['net_income'])
            
            npv = self.financial.npv(dcf_discount_rate, cash_flows)
            
            # Terminal value (simplified)
            terminal_value = projections[-1]['net_income'] * (1 + terminal_growth) / (dcf_discount_rate - terminal_growth)
            terminal_pv = terminal_value / ((1 + dcf_discount_rate) ** years)
            
            enterprise_value = npv + terminal_pv
            
            return {
                'success': True,
                'projections': projections,
                'summary': {
                    'total_revenue': total_revenue,
                    'total_net_income': total_net_income,
                    'revenue_cagr': ((projections[-1]['revenue'] / revenue) ** (1/years) - 1) * 100,
                    'average_net_margin': (total_net_income / total_revenue) * 100
                },
                'valuation': {
                    'npv': npv,
                    'terminal_value': terminal_value,
                    'enterprise_value': enterprise_value,
                    'revenue_multiple': enterprise_value / projections[-1]['revenue']
                }
            }
            
        except Exception as e:
            logger.error(f"Financial model error: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# Create singleton instance for agent use
excel_agent = ExcelAgent()


# Simple API functions for direct use

def calculate(formula: str, **cells) -> Any:
    """
    Simple calculate function
    
    Examples:
        calculate('=A1+A2', A1=100, A2=200)  # Returns 300
        calculate('=SUM(A1:A3)', A1=100, A2=200, A3=300)  # Returns 600
        calculate('=NPV(0.1,-1000,300,400,500)')  # Returns NPV
    """
    result = excel_agent.evaluate_formula(formula, cells)
    return result['result'] if result['success'] else None


def npv(discount_rate: float, *cash_flows) -> float:
    """Calculate NPV directly"""
    return financial_calc.npv(discount_rate, list(cash_flows))


def irr(*cash_flows) -> float:
    """Calculate IRR directly"""
    return financial_calc.irr(list(cash_flows))


def loan_payment(principal: float, annual_rate: float, years: int) -> float:
    """Calculate monthly loan payment"""
    monthly_rate = annual_rate / 12
    months = years * 12
    return abs(financial_calc.pmt(monthly_rate, months, principal))