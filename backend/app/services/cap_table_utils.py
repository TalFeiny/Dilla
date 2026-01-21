"""
Cap Table Utility Functions

Helper functions for safe type conversions and common cap table operations.
This module centralizes defensive type handling to reduce code duplication.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Union, Optional
import logging

logger = logging.getLogger(__name__)


def safe_to_decimal(value: Any, default: Decimal = Decimal('0'), field_name: str = "value") -> Decimal:
    """
    Safely convert a value to Decimal, handling various input types.
    
    Args:
        value: Value to convert (can be int, float, str, dict, Decimal, or None)
        default: Default value to use if conversion fails
        field_name: Name of the field for error logging
    
    Returns:
        Decimal representation of the value
    
    Examples:
        >>> safe_to_decimal(100)
        Decimal('100')
        >>> safe_to_decimal("100.5")
        Decimal('100.5')
        >>> safe_to_decimal({"value": 100})
        Decimal('100')
        >>> safe_to_decimal(None, default=Decimal('0'))
        Decimal('0')
    """
    if value is None:
        return default
    
    if isinstance(value, Decimal):
        return value
    
    if isinstance(value, dict):
        # Try common dict keys
        for key in ['value', 'amount', 'ownership', 'percentage']:
            if key in value:
                return safe_to_decimal(value[key], default, f"{field_name}.{key}")
        logger.warning(
            f"Cannot extract Decimal from dict for {field_name}: {value}. "
            f"Available keys: {list(value.keys())}. Using default: {default}"
        )
        return default
    
    try:
        # Convert to string first, then to Decimal (handles int, float, str)
        return Decimal(str(value))
    except (ValueError, TypeError, Exception) as e:
        logger.warning(
            f"Failed to convert {field_name} to Decimal: {value} (type: {type(value)}). "
            f"Error: {e}. Using default: {default}"
        )
        return default


def safe_to_float(value: Any, default: float = 0.0, field_name: str = "value") -> float:
    """
    Safely convert a value to float, handling various input types.
    
    Args:
        value: Value to convert
        default: Default value to use if conversion fails
        field_name: Name of the field for error logging
    
    Returns:
        float representation of the value
    """
    if value is None:
        return default
    
    if isinstance(value, (int, float)):
        return float(value)
    
    if isinstance(value, Decimal):
        return float(value)
    
    if isinstance(value, dict):
        # Try common dict keys
        for key in ['value', 'amount', 'ownership', 'percentage']:
            if key in value:
                return safe_to_float(value[key], default, f"{field_name}.{key}")
        logger.warning(
            f"Cannot extract float from dict for {field_name}: {value}. Using default: {default}"
        )
        return default
    
    try:
        return float(value)
    except (ValueError, TypeError, Exception) as e:
        logger.warning(
            f"Failed to convert {field_name} to float: {value} (type: {type(value)}). "
            f"Error: {e}. Using default: {default}"
        )
        return default


def clean_cap_table_ownerships(cap_table: Dict[str, Any]) -> Dict[str, Decimal]:
    """
    Clean and normalize a cap table dictionary, ensuring all ownership values are Decimals.
    
    Args:
        cap_table: Dictionary mapping shareholder names to ownership values
                  (values can be int, float, str, dict, or Decimal)
    
    Returns:
        Dictionary with all ownership values as Decimals
    
    Examples:
        >>> clean_cap_table_ownerships({"Founder": 0.5, "Investor": "0.3"})
        {'Founder': Decimal('0.5'), 'Investor': Decimal('0.3')}
    """
    cleaned = {}
    for shareholder, ownership in cap_table.items():
        cleaned[shareholder] = safe_to_decimal(ownership, field_name=f"cap_table[{shareholder}]")
    return cleaned


def quantize_decimal(value: Decimal, precision: str = '0.0001') -> Decimal:
    """
    Quantize a Decimal value to a specific precision.
    
    Args:
        value: Decimal value to quantize
        precision: Precision string (e.g., '0.0001' for 4 decimal places)
    
    Returns:
        Quantized Decimal value
    """
    return value.quantize(Decimal(precision), rounding=ROUND_HALF_UP)


def validate_ownership_sum(cap_table: Dict[str, Decimal], expected_sum: Decimal = Decimal('1.0'), 
                          tolerance: Decimal = Decimal('0.0001')) -> bool:
    """
    Validate that cap table ownership percentages sum to expected value.
    
    Args:
        cap_table: Dictionary mapping shareholder names to ownership Decimals
        expected_sum: Expected sum (default 1.0 for 100%)
        tolerance: Allowed deviation from expected sum
    
    Returns:
        True if sum is within tolerance, False otherwise
    """
    total = sum(cap_table.values())
    difference = abs(total - expected_sum)
    is_valid = difference <= tolerance
    
    if not is_valid:
        logger.warning(
            f"Cap table ownership sum validation failed: sum={total}, "
            f"expected={expected_sum}, difference={difference}, tolerance={tolerance}"
        )
    
    return is_valid
