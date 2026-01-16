"""
Numpy to Native Python Type Converter
Converts all numpy/pandas types to native Python types recursively
Prevents JSON serialization errors from numpy.int64, numpy.float64, etc.
"""

import numpy as np
from typing import Any, Union
import logging

logger = logging.getLogger(__name__)

# Try to import pandas if available
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


def convert_numpy_to_native(obj: Any, _visited: set = None) -> Any:
    """
    Recursively convert numpy and pandas types to native Python types.
    
    This function handles:
    - numpy scalars (int64, float64, bool_, etc.)
    - numpy arrays
    - pandas DataFrames
    - pandas Series
    - nested dictionaries and lists containing numpy types
    
    Args:
        obj: Object to convert (any type)
        _visited: Internal tracking for circular references
        
    Returns:
        Object with all numpy/pandas types converted to native Python types
    """
    # Initialize visited set on first call
    if _visited is None:
        _visited = set()
    
    # Check for circular references
    obj_id = id(obj)
    if isinstance(obj, (dict, list)) and obj_id in _visited:
        return obj
    _visited.add(obj_id)
    
    try:
        # CRITICAL: Check numpy types FIRST before anything else
        if hasattr(type(obj), '__module__') and type(obj).__module__ == 'numpy':
            return _convert_numpy_scalar(obj)
        
        # Handle pandas DataFrame BEFORE dict operations
        if PANDAS_AVAILABLE and isinstance(obj, pd.DataFrame):
            return convert_numpy_to_native(obj.to_dict(orient='records'), _visited)
        
        # Handle pandas Series
        if PANDAS_AVAILABLE and isinstance(obj, pd.Series):
            return convert_numpy_to_native(obj.to_dict(), _visited)
        
        # Handle numpy arrays
        if isinstance(obj, np.ndarray):
            return convert_numpy_to_native(obj.tolist(), _visited)
        
        # Handle primitives (don't recurse)
        if isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj
        
        # Handle dictionaries - recursively convert values
        if isinstance(obj, dict):
            return {
                convert_numpy_to_native(k, _visited): convert_numpy_to_native(v, _visited)
                for k, v in obj.items()
            }
        
        # Handle lists and tuples
        if isinstance(obj, (list, tuple)):
            converted = [convert_numpy_to_native(item, _visited) for item in obj]
            return converted if isinstance(obj, list) else tuple(converted)
        
        # Handle dataclasses (if they have asdict method)
        if hasattr(obj, '__dataclass_fields__'):
            try:
                import dataclasses
                if dataclasses.is_dataclass(obj):
                    return convert_numpy_to_native(dataclasses.asdict(obj), _visited)
            except:
                pass
        
        # Handle Pydantic models
        if hasattr(obj, 'dict') and callable(getattr(obj, 'dict')):
            return convert_numpy_to_native(obj.dict(), _visited)
        
        # Handle objects with to_dict method
        if hasattr(obj, 'to_dict') and callable(obj.to_dict):
            return convert_numpy_to_native(obj.to_dict(), _visited)
        
        # For all other objects, try to stringify
        return str(obj)
        
    finally:
        # Clean up visited tracking
        if obj_id in _visited:
            _visited.remove(obj_id)


def _convert_numpy_scalar(obj: Any) -> Union[int, float, bool]:
    """
    Convert a numpy scalar to native Python type.
    
    Args:
        obj: numpy scalar (int64, float64, bool_, etc.)
        
    Returns:
        Native Python type (int, float, or bool)
    """
    try:
        # Check for numpy integer types
        if np.issubdtype(type(obj), np.integer):
            return int(obj)
        
        # Check for numpy float types
        elif np.issubdtype(type(obj), np.floating):
            val = float(obj)
            # Handle special cases
            if np.isnan(val):
                return 0
            elif np.isinf(val):
                return float('inf') if val > 0 else float('-inf')
            return val
        
        # Check for numpy boolean
        elif np.issubdtype(type(obj), np.bool_) or isinstance(obj, np.bool_):
            return bool(obj)
        
        # Try to use item() method as fallback
        elif hasattr(obj, 'item'):
            return _convert_numpy_scalar(obj.item())
        
        # Final fallback - convert to string then back (not ideal, but safe)
        else:
            if isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float64, np.float32)):
                return float(obj)
            elif isinstance(obj, np.bool_):
                return bool(obj)
            else:
                return str(obj)
    
    except (AttributeError, TypeError, ValueError) as e:
        logger.warning(f"Failed to convert numpy scalar {type(obj)}: {e}")
        return 0  # Safe fallback


def convert_pandas_to_native(df_or_series) -> Any:
    """
    Convert pandas DataFrame or Series to native Python types.
    
    Args:
        df_or_series: pandas DataFrame or Series
        
    Returns:
        Native Python representation (dict or list)
    """
    if not PANDAS_AVAILABLE:
        return str(df_or_series)
    
    if isinstance(df_or_series, pd.DataFrame):
        return convert_numpy_to_native(df_or_series.to_dict(orient='records'))
    elif isinstance(df_or_series, pd.Series):
        return convert_numpy_to_native(df_or_series.to_dict())
    else:
        return convert_numpy_to_native(df_or_series)


# Convenience functions for common patterns
def to_native_int(value: Any) -> int:
    """Convert any numeric type to native int"""
    if value is None:
        return 0
    if isinstance(value, (int, np.integer)):
        return int(value)
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return 0


def to_native_float(value: Any) -> float:
    """Convert any numeric type to native float"""
    if value is None:
        return 0.0
    if isinstance(value, (float, np.floating)):
        return float(value)
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def to_native_bool(value: Any) -> bool:
    """Convert any boolean-like type to native bool"""
    if value is None:
        return False
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    return bool(value)

