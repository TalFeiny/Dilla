# Only import services that still exist after cleanup
# Other services have been removed or replaced with stubs

from typing import Any

__all__ = ["python_executor"]


def __getattr__(name: str) -> Any:
    if name == "python_executor":
        from .python_executor import python_executor  # Lazy import to avoid heavy deps at package import time

        return python_executor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")