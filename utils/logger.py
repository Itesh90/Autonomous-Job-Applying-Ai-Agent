"""
Logging configuration and utilities
"""
import logging
import logging.handlers
import json
from datetime import datetime
from pathlib import Path
import sys
from typing import Any, Dict

from config.settings import settings

# Create logs directory
settings.logs_dir.mkdir(parents=True, exist_ok=True)

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcfromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'component': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add extra fields if present
        if hasattr(record, 'job_id'):
            log_entry['job_id'] = record.job_id
        if hasattr(record, 'application_id'):
            log_entry['application_id'] = record.application_id
        if hasattr(record, 'error_details'):
            log_entry['error_details'] = record.error_details
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)

def setup_logger(name: str, level=None) -> logging.Logger:
    """Set up logger for a component"""
    logger = logging.getLogger(name)
    
    # Set level from settings or parameter
    log_level = level or getattr(logging, settings.log_level.upper())
    logger.setLevel(log_level)
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        settings.logs_dir / f"{name}.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)
    
    # Error file handler
    error_handler = logging.handlers.RotatingFileHandler(
        settings.logs_dir / "errors.log",
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    logger.addHandler(error_handler)
    
    return logger

def get_logger(name: str) -> logging.Logger:
    """Get or create logger for component"""
    return setup_logger(name)

# Create audit logger
audit_logger = setup_logger("audit")
audit_logger.propagate = False

def log_audit(action: str, details: Dict[str, Any] = None):
    """Log audit event"""
    audit_logger.info(
        action,
        extra={
            'audit': True,
            'details': details or {}
        }
    )
