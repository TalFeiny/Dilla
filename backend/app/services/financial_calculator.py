"""
Financial Calculator Service
Provides financial calculation functions (NPV, IRR, PMT, etc.) and bond/options calculations
"""

from typing import List, Optional, Dict, Any
import math
import numpy as np
from scipy.optimize import fsolve
import logging

logger = logging.getLogger(__name__)


class FinancialCalculator:
    """Financial calculator class for common financial calculations"""
    
    def npv(self, rate: float, cash_flows: List[float]) -> float:
        """
        Calculate Net Present Value
        
        Args:
            rate: Discount rate per period
            cash_flows: List of cash flows [initial_investment, period1, period2, ...]
        
        Returns:
            NPV value
        """
        if not cash_flows:
            return 0.0
        
        npv = 0.0
        for i, cf in enumerate(cash_flows):
            npv += cf / ((1 + rate) ** i)
        return npv
    
    def irr(self, cash_flows: List[float], guess: float = 0.1) -> Optional[float]:
        """
        Calculate Internal Rate of Return using Newton-Raphson method
        
        Args:
            cash_flows: List of cash flows [initial_investment, period1, period2, ...]
            guess: Initial guess for IRR (default 0.1 = 10%)
        
        Returns:
            IRR value or None if cannot be calculated
        """
        if not cash_flows or len(cash_flows) < 2:
            return None
        
        # Check for sign changes (required for IRR)
        positive_flows = sum(1 for cf in cash_flows if cf > 0)
        negative_flows = sum(1 for cf in cash_flows if cf < 0)
        
        if positive_flows == 0 or negative_flows == 0:
            return None
        
        def npv_func(rate: float) -> float:
            return sum(cf / ((1 + rate) ** i) for i, cf in enumerate(cash_flows))
        
        try:
            # Use scipy's fsolve to find root
            irr = fsolve(npv_func, guess)[0]
            return float(irr)
        except Exception as e:
            logger.error(f"IRR calculation error: {e}")
            # Fallback to simple bisection method
            return self._irr_bisection(cash_flows, guess)
    
    def _irr_bisection(self, cash_flows: List[float], guess: float = 0.1, tol: float = 1e-6) -> Optional[float]:
        """Bisection method for IRR calculation (fallback)"""
        low, high = -0.99, 10.0
        max_iter = 100
        
        for _ in range(max_iter):
            mid = (low + high) / 2
            npv_mid = sum(cf / ((1 + mid) ** i) for i, cf in enumerate(cash_flows))
            
            if abs(npv_mid) < tol:
                return mid
            
            npv_low = sum(cf / ((1 + low) ** i) for i, cf in enumerate(cash_flows))
            if npv_low * npv_mid < 0:
                high = mid
            else:
                low = mid
        
        return None
    
    def pv(self, rate: float, nper: int, pmt: float = 0, fv: float = 0, 
           when: int = 0) -> float:
        """
        Calculate Present Value
        
        Args:
            rate: Interest rate per period
            nper: Number of periods
            pmt: Payment per period
            fv: Future value
            when: 0 = end of period, 1 = beginning of period
        
        Returns:
            Present value
        """
        if rate == 0:
            return -(pmt * nper + fv)
        
        pv_factor = (1 + rate) ** -nper
        pv_pmt = pmt * ((1 - pv_factor) / rate) * (1 + rate * when)
        pv_fv = fv * pv_factor
        
        return -(pv_pmt + pv_fv)
    
    def fv(self, rate: float, nper: int, pmt: float = 0, pv: float = 0, 
           when: int = 0) -> float:
        """
        Calculate Future Value
        
        Args:
            rate: Interest rate per period
            nper: Number of periods
            pmt: Payment per period
            pv: Present value
            when: 0 = end of period, 1 = beginning of period
        
        Returns:
            Future value
        """
        if rate == 0:
            return -(pv + pmt * nper)
        
        fv_factor = (1 + rate) ** nper
        fv_pv = pv * fv_factor
        fv_pmt = pmt * ((fv_factor - 1) / rate) * (1 + rate * when)
        
        return -(fv_pv + fv_pmt)
    
    def pmt(self, rate: float, nper: int, pv: float, fv: float = 0, 
            when: int = 0) -> float:
        """
        Calculate Payment per period
        
        Args:
            rate: Interest rate per period
            nper: Number of periods
            pv: Present value
            fv: Future value
            when: 0 = end of period, 1 = beginning of period
        
        Returns:
            Payment per period
        """
        if rate == 0:
            return -(pv + fv) / nper
        
        pv_factor = (1 + rate) ** -nper
        pmt = -(pv * (1 + rate * when) + fv * pv_factor) / \
              ((1 - pv_factor) / rate * (1 + rate * when))
        
        return pmt
    
    def nper(self, rate: float, pmt: float, pv: float, fv: float = 0, 
             when: int = 0) -> float:
        """
        Calculate Number of periods
        
        Args:
            rate: Interest rate per period
            pmt: Payment per period
            pv: Present value
            fv: Future value
            when: 0 = end of period, 1 = beginning of period
        
        Returns:
            Number of periods
        """
        if rate == 0:
            return -(pv + fv) / pmt
        
        pmt_with_when = pmt * (1 + rate * when)
        
        if pmt_with_when == 0:
            # No payment case
            if pv == 0:
                return 0
            return math.log(-fv / pv) / math.log(1 + rate)
        
        # With payments
        a = -(fv + pv * (1 + rate) ** (when)) / pmt_with_when
        b = 1 + rate
        
        if b <= 0 or a <= 0:
            return float('inf')
        
        return math.log(a) / math.log(b)
    
    def rate(self, nper: int, pmt: float, pv: float, fv: float = 0, 
             when: int = 0, guess: float = 0.1) -> Optional[float]:
        """
        Calculate Interest rate
        
        Args:
            nper: Number of periods
            pmt: Payment per period
            pv: Present value
            fv: Future value
            when: 0 = end of period, 1 = beginning of period
            guess: Initial guess for rate
        
        Returns:
            Interest rate per period
        """
        def rate_func(r: float) -> float:
            if r == 0:
                return pv + pmt * nper + fv
            pv_factor = (1 + r) ** -nper
            return pv + pmt * ((1 - pv_factor) / r) * (1 + r * when) + fv * pv_factor
        
        try:
            rate = fsolve(rate_func, guess)[0]
            return float(rate)
        except Exception as e:
            logger.error(f"Rate calculation error: {e}")
            return None


# Module-level function wrappers for backward compatibility
class FinancialCalc:
    """Function-style wrapper for financial calculations"""
    
    def __init__(self):
        self._calc = FinancialCalculator()
    
    def npv(self, rate: float, cash_flows: List[float]) -> float:
        return self._calc.npv(rate, cash_flows)
    
    def irr(self, cash_flows: List[float]) -> Optional[float]:
        return self._calc.irr(cash_flows)
    
    def pmt(self, rate: float, nper: int, pv: float, fv: float = 0, when: int = 0) -> float:
        return self._calc.pmt(rate, nper, pv, fv, when)
    
    def pv(self, rate: float, nper: int, pmt: float = 0, fv: float = 0, when: int = 0) -> float:
        return self._calc.pv(rate, nper, pmt, fv, when)
    
    def fv(self, rate: float, nper: int, pmt: float = 0, pv: float = 0, when: int = 0) -> float:
        return self._calc.fv(rate, nper, pmt, pv, when)
    
    def nper(self, rate: float, pmt: float, pv: float, fv: float = 0, when: int = 0) -> float:
        return self._calc.nper(rate, pmt, pv, fv, when)
    
    def rate(self, nper: int, pmt: float, pv: float, fv: float = 0, when: int = 0, guess: float = 0.1) -> Optional[float]:
        return self._calc.rate(nper, pmt, pv, fv, when, guess)


class BondCalc:
    """Bond calculation functions"""
    
    def price(self, market_rate: float, coupon_rate: float, face_value: float, 
              years_to_maturity: int, payments_per_year: int = 2) -> float:
        """
        Calculate bond price
        
        Args:
            market_rate: Market interest rate (yield to maturity)
            coupon_rate: Annual coupon rate
            face_value: Par value of bond
            years_to_maturity: Years until maturity
            payments_per_year: Number of coupon payments per year (default 2 = semiannual)
        
        Returns:
            Bond price
        """
        n = years_to_maturity * payments_per_year
        periodic_rate = market_rate / payments_per_year
        periodic_coupon = (coupon_rate / payments_per_year) * face_value
        
        if periodic_rate == 0:
            return face_value + (periodic_coupon * n)
        
        # Present value of coupon payments
        pv_coupons = periodic_coupon * ((1 - (1 + periodic_rate) ** -n) / periodic_rate)
        
        # Present value of face value
        pv_face = face_value / ((1 + periodic_rate) ** n)
        
        return pv_coupons + pv_face
    
    def duration(self, market_rate: float, coupon_rate: float, face_value: float,
                 years_to_maturity: int, payments_per_year: int = 2) -> float:
        """
        Calculate Macaulay Duration
        
        Args:
            market_rate: Market interest rate (yield to maturity)
            coupon_rate: Annual coupon rate
            face_value: Par value of bond
            years_to_maturity: Years until maturity
            payments_per_year: Number of coupon payments per year
        
        Returns:
            Macaulay Duration in years
        """
        bond_price = self.price(market_rate, coupon_rate, face_value, years_to_maturity, payments_per_year)
        
        n = years_to_maturity * payments_per_year
        periodic_rate = market_rate / payments_per_year
        periodic_coupon = (coupon_rate / payments_per_year) * face_value
        
        weighted_sum = 0.0
        for t in range(1, n + 1):
            if t < n:
                cf = periodic_coupon
            else:
                cf = periodic_coupon + face_value
            
            pv_cf = cf / ((1 + periodic_rate) ** t)
            weighted_sum += (t / payments_per_year) * pv_cf
        
        return weighted_sum / bond_price
    
    def convexity(self, market_rate: float, coupon_rate: float, face_value: float,
                  years_to_maturity: int, payments_per_year: int = 2) -> float:
        """
        Calculate Bond Convexity
        
        Args:
            market_rate: Market interest rate (yield to maturity)
            coupon_rate: Annual coupon rate
            face_value: Par value of bond
            years_to_maturity: Years until maturity
            payments_per_year: Number of coupon payments per year
        
        Returns:
            Convexity measure
        """
        bond_price = self.price(market_rate, coupon_rate, face_value, years_to_maturity, payments_per_year)
        
        n = years_to_maturity * payments_per_year
        periodic_rate = market_rate / payments_per_year
        periodic_coupon = (coupon_rate / payments_per_year) * face_value
        
        convexity_sum = 0.0
        for t in range(1, n + 1):
            if t < n:
                cf = periodic_coupon
            else:
                cf = periodic_coupon + face_value
            
            pv_cf = cf / ((1 + periodic_rate) ** t)
            t_years = t / payments_per_year
            convexity_sum += (t_years * (t_years + 1 / payments_per_year) * pv_cf) / ((1 + periodic_rate) ** 2)
        
        return convexity_sum / bond_price


class OptionsCalc:
    """Options calculation functions (basic Black-Scholes implementation)"""
    
    def black_scholes(self, s: float, k: float, t: float, r: float, sigma: float, 
                     option_type: str = 'call') -> float:
        """
        Calculate option price using Black-Scholes model
        
        Args:
            s: Current stock price
            k: Strike price
            t: Time to expiration (in years)
            r: Risk-free interest rate
            sigma: Volatility (standard deviation of returns)
            option_type: 'call' or 'put'
        
        Returns:
            Option price
        """
        if t <= 0:
            if option_type.lower() == 'call':
                return max(s - k, 0)
            else:
                return max(k - s, 0)
        
        d1 = (math.log(s / k) + (r + 0.5 * sigma ** 2) * t) / (sigma * math.sqrt(t))
        d2 = d1 - sigma * math.sqrt(t)
        
        # Cumulative standard normal distribution (approximation)
        def norm_cdf(x: float) -> float:
            return 0.5 * (1 + math.erf(x / math.sqrt(2)))
        
        n_d1 = norm_cdf(d1)
        n_d2 = norm_cdf(d2)
        n_neg_d1 = norm_cdf(-d1)
        n_neg_d2 = norm_cdf(-d2)
        
        if option_type.lower() == 'call':
            return s * n_d1 - k * math.exp(-r * t) * n_d2
        else:  # put
            return k * math.exp(-r * t) * n_neg_d2 - s * n_neg_d1


# Module-level instances for direct function access
financial_calc = FinancialCalc()
bond_calc = BondCalc()
options_calc = OptionsCalc()
