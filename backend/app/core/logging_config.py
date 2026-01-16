"""
Enhanced Logging Configuration for Dilla AI Backend
Provides structured logging with rotation and monitoring
"""
import logging
import logging.handlers
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data
        
        # Add request context if available
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        
        return json.dumps(log_data)


class DetailedFormatter(logging.Formatter):
    """Detailed human-readable formatter"""
    
    def __init__(self):
        super().__init__(
            fmt='%(asctime)s | %(levelname)-8s | %(name)-20s | %(funcName)-15s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


def setup_logging(
    log_dir: Path = Path(__file__).parent.parent.parent / "logs",
    level: str = "INFO",
    enable_json: bool = False,
    enable_console: bool = True
) -> logging.Logger:
    """
    Setup comprehensive logging for the backend
    
    Args:
        log_dir: Directory to store log files
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_json: Enable JSON formatted logs
        enable_console: Enable console output
    """
    # Create logs directory if it doesn't exist
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # File handler with rotation (10MB, keep 5 backups)
    log_file = log_dir / "backend.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    
    # Error file handler (only errors and above)
    error_file = log_dir / "backend_errors.log"
    error_handler = logging.handlers.RotatingFileHandler(
        error_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    
    # Choose formatter
    if enable_json:
        formatter = JSONFormatter()
    else:
        formatter = DetailedFormatter()
    
    file_handler.setFormatter(formatter)
    error_handler.setFormatter(formatter)
    
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)
    
    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = DetailedFormatter()
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # Create application logger
    logger = logging.getLogger("dilla_ai")
    
    logger.info(f"Logging configured - Level: {level}, Directory: {log_dir}")
    logger.info(f"Log files: {log_file}, {error_file}")
    
    return logger


# Initialize logging on import
_log_dir = Path(__file__).parent.parent.parent / "logs"
_log_level = "INFO"
logger = setup_logging(
    log_dir=_log_dir,
    level=_log_level,
    enable_json=False,
    enable_console=True
)

