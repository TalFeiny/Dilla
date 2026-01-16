"""
Centralized data validation and safe operations module.
Prevents NoneType errors and ensures data integrity across all services.
"""

from typing import Any, Dict, List, Optional, Union
from decimal import Decimal
import logging

# Try to import numpy for type checking
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

logger = logging.getLogger(__name__)


class DataValidator:
    """Centralized data validation and safe operations"""
    
    @staticmethod
    def ensure_numeric(value: Any, default: float = 0) -> float:
        """
        Ensure a value is numeric, handling various input types including InferenceResult.
        
        Args:
            value: Input value (can be None, InferenceResult, Decimal, string, etc.)
            default: Default value if input is None or invalid
            
        Returns:
            Float value, guaranteed to be numeric
        """
        # Handle None explicitly
        if value is None:
            return default
            
        # Handle InferenceResult objects (has .value attribute)
        if hasattr(value, 'value'):
            value = value.value
            
        # Check again for None after extracting from InferenceResult
        if value is None:
            return default
            
        # Handle Decimal
        if isinstance(value, Decimal):
            return float(value)
        
        # Handle numpy types (BEFORE converting to int/float)
        if NUMPY_AVAILABLE:
            try:
                if hasattr(type(value), '__module__') and type(value).__module__ == 'numpy':
                    # It's a numpy type - convert to native Python type
                    if isinstance(value, np.integer):
                        return float(int(value))
                    elif isinstance(value, np.floating):
                        return float(value)
                    elif isinstance(value, np.bool_):
                        return 1.0 if value else 0.0
                    elif isinstance(value, np.ndarray):
                        # For arrays, use first element or 0
                        if value.size > 0:
                            return float(value.flat[0]) if np.issubdtype(value.dtype, np.number) else default
                        return default
                    else:
                        # Fallback for other numpy types
                        if hasattr(value, 'item'):
                            item = value.item()
                            return float(item) if isinstance(item, (int, float)) else default
                        else:
                            return float(value) if np.issubdtype(type(value), np.number) else default
            except (AttributeError, TypeError, ValueError) as e:
                logger.warning(f"Could not convert numpy type to numeric: {e}")
            
        # Handle numeric types
        if isinstance(value, (int, float)):
            return float(value)
            
        # Handle string values
        if isinstance(value, str):
            # Use extract_numeric_from_text for complex string parsing
            extracted = DataValidator.extract_numeric_from_text(value, default)
            
            # Fallback to simple cleaning
            cleaned = (value.replace('$', '')
                           .replace('€', '')
                           .replace('£', '')
                           .replace(',', '')
                           .replace('%', '')
                           .strip())
            try:
                # Handle special strings
                if cleaned.lower() in ['none', 'null', 'n/a', 'na', '-', '']:
                    return default
                # Try to convert cleaned numeric text
                cleaned_value = float(cleaned)
                return cleaned_value
            except (ValueError, TypeError):
                if extracted != default:
                    return extracted
                logger.warning(f"Could not convert '{value}' to numeric, using default {default}")
                return default
                
        # For any other type, try conversion or use default
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f"Unexpected type {type(value)} for numeric conversion, using default {default}")
            return default
    
    @staticmethod
    def safe_divide(numerator: Any, denominator: Any, default: float = 0) -> float:
        """
        Safely divide two values, handling None, zero, and InferenceResult.
        
        Args:
            numerator: The dividend
            denominator: The divisor  
            default: Value to return if division fails
            
        Returns:
            Result of division or default if division would fail
        """
        num = DataValidator.ensure_numeric(numerator, 0)
        denom = DataValidator.ensure_numeric(denominator, 0)
        
        if denom == 0:
            return default
            
        try:
            return num / denom
        except (ZeroDivisionError, TypeError, ValueError):
            return default
    
    @staticmethod
    def safe_get_value(value: Any, default: Any = 0) -> Any:
        """
        Extract value from InferenceResult, Decimal, or return as-is.
        Handles None explicitly to prevent errors.
        
        Args:
            value: Input value (can be InferenceResult, Decimal, None, etc.)
            default: Default value if input is None
            
        Returns:
            Extracted value or default
        """
        # Handle None explicitly
        if value is None:
            return default
            
        # Handle InferenceResult objects
        if hasattr(value, 'value'):
            extracted = value.value
            return extracted if extracted is not None else default
            
        # Handle Decimal
        if isinstance(value, Decimal):
            return float(value)
        
        # Handle numpy types (prevent JSON serialization errors)
        if NUMPY_AVAILABLE:
            try:
                # Check if it's a numpy type by checking the type module
                if hasattr(type(value), '__module__') and type(value).__module__ == 'numpy':
                    # It's a numpy type - convert to native Python type
                    if isinstance(value, np.integer):
                        return int(value)
                    elif isinstance(value, np.floating):
                        return float(value)
                    elif isinstance(value, np.bool_):
                        return bool(value)
                    elif isinstance(value, np.ndarray):
                        return value.tolist()
                    else:
                        # Fallback for other numpy types
                        if hasattr(value, 'item'):
                            return value.item()
                        else:
                            return str(value)
            except (AttributeError, TypeError, ValueError):
                pass
            
        # Return the value as-is if not None
        return value
    
    @staticmethod
    def safe_multiply(value1: Any, value2: Any, default: float = 0) -> float:
        """
        Safely multiply two values, handling None and InferenceResult.
        
        Args:
            value1: First multiplicand
            value2: Second multiplicand
            default: Value to return if multiplication fails
            
        Returns:
            Result of multiplication or default
        """
        v1 = DataValidator.ensure_numeric(value1, 0)
        v2 = DataValidator.ensure_numeric(value2, 0)
        
        try:
            return v1 * v2
        except (TypeError, ValueError):
            return default
    
    @staticmethod
    def safe_get(data: Optional[Dict], key: str, default: Any = None) -> Any:
        """
        Safely get value from dictionary, handling None dict.
        
        Args:
            data: Dictionary or None
            key: Key to retrieve
            default: Default value if key not found or dict is None
            
        Returns:
            Value from dict or default
        """
        if data is None:
            return default
        if not isinstance(data, dict):
            return default
        return data.get(key, default)
    
    @staticmethod
    def validate_company_data(company_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and clean company data, ensuring critical fields are never None.
        
        Args:
            company_data: Raw company data dictionary
            
        Returns:
            Validated company data with guaranteed non-None critical fields
        """
        if not company_data:
            return {}
            
        validated = dict(company_data)  # Copy to avoid modifying original
        
        # Critical numeric fields that must have values
        numeric_fields = [
            'revenue', 'valuation', 'total_funding', 'total_raised',
            'arr', 'gross_margin', 'burn_rate', 'runway_months',
            'employee_count', 'customer_count', 'revenue_growth'
        ]
        
        for field in numeric_fields:
            # First check actual value
            value = validated.get(field)
            
            # If None or 0, check for inferred version
            if value is None or value == 0:
                inferred_field = f'inferred_{field}'
                inferred_value = validated.get(inferred_field)
                if inferred_value is not None:
                    validated[field] = DataValidator.ensure_numeric(inferred_value, 0)
                else:
                    # Set to 0 rather than None
                    validated[field] = 0
            else:
                # Ensure it's numeric even if it exists
                validated[field] = DataValidator.ensure_numeric(value, 0)
        
        # Special handling for revenue - MUST have a value
        if validated.get('revenue', 0) == 0:
            # Try multiple fallbacks
            revenue_fallbacks = ['inferred_revenue', 'arr', 'inferred_arr']
            for fallback in revenue_fallbacks:
                fallback_value = validated.get(fallback)
                if fallback_value and DataValidator.ensure_numeric(fallback_value, 0) > 0:
                    validated['revenue'] = DataValidator.ensure_numeric(fallback_value, 0)
                    break
            
            # If still no revenue, use a minimal default based on stage
            if validated.get('revenue', 0) == 0:
                stage = validated.get('funding_stage', 'Series A')
                stage_defaults = {
                    'Pre-Seed': 100_000,
                    'Seed': 500_000,
                    'Series A': 1_000_000,
                    'Series B': 5_000_000,
                    'Series C': 15_000_000,
                    'Series D': 30_000_000,
                }
                validated['revenue'] = stage_defaults.get(stage, 1_000_000)
                logger.warning(f"No revenue found for {validated.get('company', 'Unknown')}, "
                             f"using stage default: ${validated['revenue']:,.0f}")
        
        # Ensure lists are not None
        list_fields = ['funding_rounds', 'investors', 'founders', 'customers']
        for field in list_fields:
            if validated.get(field) is None:
                validated[field] = []
        
        # Ensure string fields are not None
        string_fields = ['company', 'business_model', 'sector', 'funding_stage', 
                        'geography', 'website', 'description']
        for field in string_fields:
            if validated.get(field) is None:
                validated[field] = ''
        
        return validated
    
    @staticmethod
    def validate_funding_round(round_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate funding round data.
        
        Args:
            round_data: Raw funding round data
            
        Returns:
            Validated funding round data
        """
        if not round_data:
            return {}
            
        validated = dict(round_data)
        
        # Normalize alternate amount keys before numeric coercion
        amount_value = validated.get('amount')
        if not amount_value:
            for alt_key in ('round_size', 'size'):
                alt_value = validated.get(alt_key)
                if alt_value not in (None, '', 0):
                    validated['amount'] = DataValidator.ensure_numeric(alt_value, 0)
                    break
        
        # Ensure numeric fields
        numeric_fields = ['amount', 'valuation', 'shares_issued', 'price_per_share']
        for field in numeric_fields:
            validated[field] = DataValidator.ensure_numeric(validated.get(field), 0)
        
        # Ensure string fields
        string_fields = ['round', 'date', 'lead_investor']
        for field in string_fields:
            if validated.get(field) is None:
                validated[field] = ''
        
        # Ensure lists
        if validated.get('investors') is None:
            validated['investors'] = []
            
        return validated
    
    @staticmethod
    def extract_numeric_from_text(text: str, default: float = 0) -> float:
        """
        Extract numeric value from text containing numbers and units.
        
        Args:
            text: Text potentially containing numeric values (e.g., "$1.5M", "50%")
            default: Default value if no number found
            
        Returns:
            Extracted numeric value
        """
        if not text or not isinstance(text, str):
            return default
            
        import re
        
        # Remove currency symbols
        text = text.replace('$', '').replace('€', '').replace('£', '')
        
        # Look for patterns like 1.5M, 10B, 500K
        multipliers = {
            'k': 1_000,
            'm': 1_000_000,
            'b': 1_000_000_000,
            't': 1_000_000_000_000
        }
        
        # Pattern for number with optional decimal and multiplier
        pattern = r'(\d+\.?\d*)\s*([kmbt])?'
        match = re.search(pattern, text.lower())
        
        if match:
            number = float(match.group(1))
            multiplier_char = match.group(2)
            
            if multiplier_char:
                number *= multipliers.get(multiplier_char, 1)
                
            return number
            
        return default


# Create singleton instance for easy import
validator = DataValidator()

# Export commonly used functions at module level
ensure_numeric = validator.ensure_numeric
safe_divide = validator.safe_divide
safe_get_value = validator.safe_get_value
safe_multiply = validator.safe_multiply
safe_get = validator.safe_get
validate_company_data = validator.validate_company_data
validate_funding_round = validator.validate_funding_round
extract_numeric_from_text = validator.extract_numeric_from_text