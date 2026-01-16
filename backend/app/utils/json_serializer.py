"""
Custom JSON serializer for handling complex objects in streaming responses
Handles circular references, Decimal, datetime, numpy arrays, etc.
"""

import json
import decimal
import datetime
import numpy as np
from typing import Any, Dict, Set
import logging

# Try to import pandas if available
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

logger = logging.getLogger(__name__)


class SafeJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles complex types and circular references"""
    
    def __init__(self, *args, **kwargs):
        self._visited_ids: Set[int] = set()
        self._depth = 0
        self.max_depth = kwargs.pop('max_depth', 50)
        super().__init__(*args, **kwargs)
    
    def encode(self, o: Any) -> str:
        """Override encode to reset visited IDs for each top-level encode"""
        self._visited_ids = set()
        self._depth = 0
        return super().encode(o)
    
    def default(self, obj: Any) -> Any:
        """Convert non-JSON-serializable objects to serializable forms"""
        
        # Check recursion depth
        if self._depth > self.max_depth:
            return f"<Max depth {self.max_depth} exceeded>"
        
        # Handle circular references for complex objects
        obj_id = id(obj)
        if isinstance(obj, (dict, list)) and obj_id in self._visited_ids:
            return "<Circular Reference>"
        
        try:
            self._depth += 1
            
            # Track complex objects to detect cycles
            if isinstance(obj, (dict, list)):
                self._visited_ids.add(obj_id)
            
            # Handle specific types
            if isinstance(obj, decimal.Decimal):
                return float(obj)
            elif isinstance(obj, (datetime.datetime, datetime.date)):
                return obj.isoformat()
            elif isinstance(obj, datetime.timedelta):
                return obj.total_seconds()
            elif isinstance(obj, bytes):
                return obj.decode('utf-8', errors='ignore')
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            # Handle numpy integer types (int64, int32, etc.)
            elif isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
                return float(obj)
            elif isinstance(obj, np.bool_):
                return bool(obj)
            # Handle numpy number base class
            elif isinstance(obj, np.number):
                if np.issubdtype(obj.dtype, np.integer):
                    return int(obj)
                elif np.issubdtype(obj.dtype, np.floating):
                    return float(obj)
                elif np.issubdtype(obj.dtype, np.bool_):
                    return bool(obj)
            elif hasattr(obj, '__dict__'):
                # Handle custom objects with __dict__
                return {
                    '_type': obj.__class__.__name__,
                    '_data': obj.__dict__
                }
            elif hasattr(obj, 'to_dict'):
                # Handle objects with to_dict method
                return obj.to_dict()
            elif hasattr(obj, 'dict'):
                # Handle Pydantic models
                return obj.dict()
            else:
                # Fall back to string representation
                return str(obj)
                
        finally:
            self._depth -= 1
            # Clean up visited IDs when leaving this object
            if isinstance(obj, (dict, list)) and obj_id in self._visited_ids:
                self._visited_ids.discard(obj_id)


def safe_json_dumps(obj: Any, **kwargs) -> str:
    """
    Safely serialize object to JSON string, handling complex types and circular references
    
    Args:
        obj: Object to serialize
        **kwargs: Additional arguments to pass to json.dumps
        
    Returns:
        JSON string representation of the object
    """
    try:
        # Try with our custom encoder
        return json.dumps(obj, cls=SafeJSONEncoder, **kwargs)
    except Exception as e:
        logger.error(f"Failed to serialize object with SafeJSONEncoder: {e}")
        # Fallback to a very simple representation
        try:
            return json.dumps({
                "error": "Serialization failed",
                "type": str(type(obj)),
                "message": str(e)
            })
        except:
            return '{"error": "Critical serialization failure"}'


def clean_for_json(obj: Any, max_depth: int = 10, _depth: int = 0, _visited: Set[int] = None) -> Any:
    """
    Recursively clean an object for JSON serialization
    
    Args:
        obj: Object to clean
        max_depth: Maximum recursion depth
        _depth: Current recursion depth (internal)
        _visited: Set of visited object IDs (internal)
        
    Returns:
        Cleaned object safe for JSON serialization
    """
    if _visited is None:
        _visited = set()
    
    # Check depth limit
    if _depth > max_depth:
        return f"<Max depth {max_depth} exceeded>"
    
    # CRITICAL: Check numpy types BEFORE circular reference checks
    # numpy types don't have __dict__ and aren't iterable, so checking them late causes errors
    try:
        # Fast path: check if it's a numpy type by module
        if hasattr(obj, '__class__') and hasattr(type(obj), '__module__'):
            if type(obj).__module__ == 'numpy':
                # It's a numpy type - convert immediately
                if isinstance(obj, np.ndarray):
                    return clean_for_json(obj.tolist(), max_depth, _depth + 1, _visited)
                elif isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
                    return int(obj)
                elif isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
                    return float(obj)
                elif isinstance(obj, np.bool_):
                    return bool(obj)
                elif isinstance(obj, np.number):
                    if np.issubdtype(type(obj), np.integer):
                        return int(obj)
                    elif np.issubdtype(type(obj), np.floating):
                        return float(obj)
                    elif np.issubdtype(type(obj), np.bool_):
                        return bool(obj)
                elif hasattr(obj, 'item'):
                    return clean_for_json(obj.item(), max_depth, _depth + 1, _visited)
                else:
                    # Final fallback
                    return int(obj) if np.issubdtype(type(obj), np.integer) else (float(obj) if np.issubdtype(type(obj), np.floating) else str(obj))
    except (AttributeError, TypeError, ValueError):
        pass
    
    # Check for circular references (only for complex types)
    obj_id = id(obj)
    if isinstance(obj, (dict, list)) and obj_id in _visited:
        return "<Circular Reference>"
    
    # Handle None
    if obj is None:
        return None
    
    # Handle pandas DataFrame and Series BEFORE primitives
    if PANDAS_AVAILABLE:
        if isinstance(obj, pd.DataFrame):
            # Convert DataFrame to dict
            return clean_for_json(obj.to_dict(orient='records'), max_depth, _depth + 1, _visited)
        elif isinstance(obj, pd.Series):
            # Convert Series to dict
            return clean_for_json(obj.to_dict(), max_depth, _depth + 1, _visited)
    
    # Handle primitives (but ONLY after numpy checks)
    if isinstance(obj, (str, int, bool)):
        return obj
    
    # Handle float with infinity/nan check
    if isinstance(obj, float):
        if obj != obj:  # NaN check
            return 0
        elif obj == float('inf'):
            return 999999999  # Large positive number
        elif obj == float('-inf'):
            return -999999999  # Large negative number
        return obj
    
    # Handle special numeric types
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    
    # Handle datetime
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    
    # Track this object
    if isinstance(obj, (dict, list)):
        _visited.add(obj_id)
    
    try:
        # Handle dictionaries
        if isinstance(obj, dict):
            return {
                clean_for_json(k, max_depth, _depth + 1, _visited): 
                clean_for_json(v, max_depth, _depth + 1, _visited)
                for k, v in obj.items()
            }
        
        # Handle lists and tuples
        if isinstance(obj, (list, tuple)):
            return [clean_for_json(item, max_depth, _depth + 1, _visited) for item in obj]
        
        # Handle objects with dict method (Pydantic)
        if hasattr(obj, 'dict'):
            return clean_for_json(obj.dict(), max_depth, _depth + 1, _visited)
        
        # Handle objects with to_dict method
        if hasattr(obj, 'to_dict'):
            return clean_for_json(obj.to_dict(), max_depth, _depth + 1, _visited)
        
        # Handle objects with __dict__ (but NOT numpy types which have special __dict__)
        # numpy types must be handled BEFORE this point
        if hasattr(obj, '__dict__'):
            # CRITICAL: Explicit check for numpy types BEFORE trying vars()
            if hasattr(type(obj), '__module__') and type(obj).__module__ == 'numpy':
                # numpy types shouldn't get here, but if they do, convert properly
                try:
                    if isinstance(obj, np.integer):
                        return int(obj)
                    elif isinstance(obj, np.floating):
                        return float(obj)
                    elif isinstance(obj, np.bool_):
                        return bool(obj)
                    elif hasattr(obj, 'item'):
                        return clean_for_json(obj.item(), max_depth, _depth + 1, _visited)
                    else:
                        return str(obj)
                except:
                    return str(obj)
            
            try:
                # Try to access __dict__ safely
                return clean_for_json({
                    '_type': obj.__class__.__name__,
                    '_data': vars(obj)
                }, max_depth, _depth + 1, _visited)
            except (TypeError, ValueError) as e:
                # If vars() fails, just stringify
                logger.warning(f"vars() failed on {type(obj).__name__}: {e}")
                return str(obj)
        
        # Fallback to string
        return str(obj)
        
    finally:
        # Clean up visited tracking
        if isinstance(obj, (dict, list)) and obj_id in _visited:
            _visited.discard(obj_id)


def detect_circular_references(obj: Any, path: str = "root") -> Dict[str, Any]:
    """
    Detect circular references in an object structure
    
    Args:
        obj: Object to check
        path: Current path in the object tree
        
    Returns:
        Dictionary with circular reference information
    """
    visited = {}
    cycles = []
    
    def _check(o: Any, current_path: str, ancestors: Set[int]):
        obj_id = id(o)
        
        # Check if we've seen this object in our ancestors (circular reference)
        if obj_id in ancestors:
            cycles.append({
                'path': current_path,
                'object_id': obj_id,
                'type': type(o).__name__
            })
            return
        
        # Track this object
        ancestors.add(obj_id)
        visited[obj_id] = current_path
        
        try:
            if isinstance(o, dict):
                for key, value in o.items():
                    _check(value, f"{current_path}.{key}", ancestors.copy())
            elif isinstance(o, (list, tuple)):
                for i, item in enumerate(o):
                    _check(item, f"{current_path}[{i}]", ancestors.copy())
            elif hasattr(o, '__dict__'):
                for key, value in o.__dict__.items():
                    _check(value, f"{current_path}.{key}", ancestors.copy())
        except Exception as e:
            logger.debug(f"Error checking object at {current_path}: {e}")
    
    _check(obj, path, set())
    
    return {
        'has_cycles': len(cycles) > 0,
        'cycles': cycles,
        'total_objects': len(visited)
    }
