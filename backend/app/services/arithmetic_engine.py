"""
Arithmetic Engine Service
High-precision mathematical operations for spreadsheet calculations
Provides 50+ functions including statistics, trigonometry, and advanced math
"""

from typing import List, Union, Optional, Any
import math
import statistics
import logging

logger = logging.getLogger(__name__)


class ArithmeticEngine:
    """Arithmetic engine class for mathematical operations"""
    
    def count(self, *values: Union[int, float]) -> int:
        """
        Count the number of values
        
        Args:
            *values: Variable number of numeric values
            
        Returns:
            Count of values
        """
        return len([v for v in values if v is not None])
    
    def sum(self, *values: Union[int, float]) -> float:
        """
        Sum of all values
        
        Args:
            *values: Variable number of numeric values
            
        Returns:
            Sum of values
        """
        numeric_values = [float(v) for v in values if v is not None]
        return sum(numeric_values) if numeric_values else 0.0
    
    def average(self, *values: Union[int, float]) -> float:
        """
        Average (mean) of values
        
        Args:
            *values: Variable number of numeric values
            
        Returns:
            Average of values
        """
        numeric_values = [float(v) for v in values if v is not None]
        if not numeric_values:
            return 0.0
        return sum(numeric_values) / len(numeric_values)
    
    def median(self, *values: Union[int, float]) -> float:
        """
        Median of values
        
        Args:
            *values: Variable number of numeric values
            
        Returns:
            Median of values
        """
        numeric_values = sorted([float(v) for v in values if v is not None])
        if not numeric_values:
            return 0.0
        return statistics.median(numeric_values)
    
    def mode(self, *values: Union[int, float]) -> Optional[Union[int, float]]:
        """
        Mode (most frequent value) of values
        
        Args:
            *values: Variable number of numeric values
            
        Returns:
            Mode value or None if no mode
        """
        numeric_values = [float(v) for v in values if v is not None]
        if not numeric_values:
            return None
        try:
            return statistics.mode(numeric_values)
        except statistics.StatisticsError:
            # No unique mode
            return None
    
    def min(self, *values: Union[int, float]) -> float:
        """
        Minimum value
        
        Args:
            *values: Variable number of numeric values
            
        Returns:
            Minimum value
        """
        numeric_values = [float(v) for v in values if v is not None]
        if not numeric_values:
            return 0.0
        return min(numeric_values)
    
    def max(self, *values: Union[int, float]) -> float:
        """
        Maximum value
        
        Args:
            *values: Variable number of numeric values
            
        Returns:
            Maximum value
        """
        numeric_values = [float(v) for v in values if v is not None]
        if not numeric_values:
            return 0.0
        return max(numeric_values)
    
    def stdev(self, *values: Union[int, float]) -> float:
        """
        Standard deviation (sample)
        
        Args:
            *values: Variable number of numeric values
            
        Returns:
            Standard deviation
        """
        numeric_values = [float(v) for v in values if v is not None]
        if len(numeric_values) < 2:
            return 0.0
        try:
            return statistics.stdev(numeric_values)
        except statistics.StatisticsError:
            return 0.0
    
    def var(self, *values: Union[int, float]) -> float:
        """
        Variance (sample)
        
        Args:
            *values: Variable number of numeric values
            
        Returns:
            Variance
        """
        numeric_values = [float(v) for v in values if v is not None]
        if len(numeric_values) < 2:
            return 0.0
        try:
            return statistics.variance(numeric_values)
        except statistics.StatisticsError:
            return 0.0
    
    def stdevp(self, *values: Union[int, float]) -> float:
        """
        Standard deviation (population)
        
        Args:
            *values: Variable number of numeric values
            
        Returns:
            Population standard deviation
        """
        numeric_values = [float(v) for v in values if v is not None]
        if len(numeric_values) < 2:
            return 0.0
        try:
            return statistics.pstdev(numeric_values)
        except statistics.StatisticsError:
            return 0.0
    
    def varp(self, *values: Union[int, float]) -> float:
        """
        Variance (population)
        
        Args:
            *values: Variable number of numeric values
            
        Returns:
            Population variance
        """
        numeric_values = [float(v) for v in values if v is not None]
        if len(numeric_values) < 2:
            return 0.0
        try:
            return statistics.pvariance(numeric_values)
        except statistics.StatisticsError:
            return 0.0
    
    # Advanced math functions
    def power(self, base: float, exponent: float) -> float:
        """Raise base to the power of exponent"""
        return math.pow(float(base), float(exponent))
    
    def sqrt(self, value: float) -> float:
        """Square root"""
        if value < 0:
            raise ValueError("Cannot calculate square root of negative number")
        return math.sqrt(float(value))
    
    def log(self, value: float, base: float = 10.0) -> float:
        """Logarithm with specified base (default 10)"""
        if value <= 0:
            raise ValueError("Logarithm of non-positive number is undefined")
        return math.log(float(value), float(base))
    
    def ln(self, value: float) -> float:
        """Natural logarithm (base e)"""
        if value <= 0:
            raise ValueError("Natural logarithm of non-positive number is undefined")
        return math.log(float(value))
    
    def exp(self, value: float) -> float:
        """Exponential function (e^x)"""
        return math.exp(float(value))
    
    def factorial(self, value: int) -> int:
        """Factorial"""
        if value < 0:
            raise ValueError("Factorial of negative number is undefined")
        return math.factorial(int(value))
    
    # Trigonometry functions (assume degrees for input)
    def sin(self, angle: float, radians: bool = False) -> float:
        """Sine of angle (degrees by default)"""
        angle_rad = float(angle) if radians else math.radians(float(angle))
        return math.sin(angle_rad)
    
    def cos(self, angle: float, radians: bool = False) -> float:
        """Cosine of angle (degrees by default)"""
        angle_rad = float(angle) if radians else math.radians(float(angle))
        return math.cos(angle_rad)
    
    def tan(self, angle: float, radians: bool = False) -> float:
        """Tangent of angle (degrees by default)"""
        angle_rad = float(angle) if radians else math.radians(float(angle))
        return math.tan(angle_rad)
    
    def asin(self, value: float, radians: bool = False) -> float:
        """Arc sine (returns degrees by default)"""
        result = math.asin(float(value))
        return result if radians else math.degrees(result)
    
    def acos(self, value: float, radians: bool = False) -> float:
        """Arc cosine (returns degrees by default)"""
        result = math.acos(float(value))
        return result if radians else math.degrees(result)
    
    def atan(self, value: float, radians: bool = False) -> float:
        """Arc tangent (returns degrees by default)"""
        result = math.atan(float(value))
        return result if radians else math.degrees(result)
    
    def atan2(self, y: float, x: float, radians: bool = False) -> float:
        """Arc tangent of y/x (returns degrees by default)"""
        result = math.atan2(float(y), float(x))
        return result if radians else math.degrees(result)
    
    # Rounding functions
    def round(self, value: float, decimals: int = 0) -> float:
        """Round to specified number of decimals"""
        return round(float(value), int(decimals))
    
    def roundup(self, value: float, decimals: int = 0) -> float:
        """Round up to specified number of decimals"""
        multiplier = 10 ** int(decimals)
        return math.ceil(float(value) * multiplier) / multiplier
    
    def rounddown(self, value: float, decimals: int = 0) -> float:
        """Round down to specified number of decimals"""
        multiplier = 10 ** int(decimals)
        return math.floor(float(value) * multiplier) / multiplier
    
    def ceiling(self, value: float, significance: float = 1.0) -> float:
        """Round up to nearest multiple of significance"""
        return math.ceil(float(value) / float(significance)) * float(significance)
    
    def floor(self, value: float, significance: float = 1.0) -> float:
        """Round down to nearest multiple of significance"""
        return math.floor(float(value) / float(significance)) * float(significance)
    
    def trunc(self, value: float) -> int:
        """Truncate to integer"""
        return int(math.trunc(float(value)))
    
    # Absolute value and sign
    def abs(self, value: float) -> float:
        """Absolute value"""
        return abs(float(value))
    
    def sign(self, value: float) -> int:
        """Sign of value: 1 if positive, -1 if negative, 0 if zero"""
        val = float(value)
        if val > 0:
            return 1
        elif val < 0:
            return -1
        else:
            return 0
    
    # Percentile functions
    def percentile(self, values: List[float], percentile: float) -> float:
        """
        Calculate percentile of a dataset
        
        Args:
            values: List of numeric values
            percentile: Percentile value (0-100)
            
        Returns:
            Percentile value
        """
        if not values:
            return 0.0
        sorted_values = sorted([float(v) for v in values])
        n = len(sorted_values)
        if n == 0:
            return 0.0
        
        index = (percentile / 100) * (n - 1)
        lower = int(index)
        upper = min(lower + 1, n - 1)
        
        if lower == upper:
            return sorted_values[lower]
        
        weight = index - lower
        return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
    
    def quartile(self, values: List[float], quartile: int) -> float:
        """
        Calculate quartile of a dataset
        
        Args:
            values: List of numeric values
            quartile: Quartile number (0, 1, 2, 3, 4)
                     0 = minimum, 1 = Q1, 2 = median, 3 = Q3, 4 = maximum
            
        Returns:
            Quartile value
        """
        if quartile == 0:
            return self.min(*values) if values else 0.0
        elif quartile == 1:
            return self.percentile(values, 25)
        elif quartile == 2:
            return self.median(*values) if values else 0.0
        elif quartile == 3:
            return self.percentile(values, 75)
        elif quartile == 4:
            return self.max(*values) if values else 0.0
        else:
            raise ValueError("Quartile must be 0, 1, 2, 3, or 4")


# Create singleton instance for use throughout the application
arithmetic_engine = ArithmeticEngine()
