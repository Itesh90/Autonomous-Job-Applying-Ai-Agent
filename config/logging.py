# config/logging.py
import logging
import logging.handlers
import json
from datetime import datetime
from pathlib import Path
import gzip
import shutil

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
        if hasattr(record, 'platform'):
            log_entry['platform'] = record.platform
        if hasattr(record, 'error_details'):
            log_entry['error_details'] = record.error_details
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)

class CompressedRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Rotating file handler that compresses old log files"""
    
    def doRollover(self):
        super().doRollover()
        
        # Compress the rolled over file
        if self.backupCount > 0:
            for i in range(1, self.backupCount + 1):
                sfn = f"{self.baseFilename}.{i}"
                if Path(sfn).exists() and not sfn.endswith('.gz'):
                    with open(sfn, 'rb') as f_in:
                        with gzip.open(f"{sfn}.gz", 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    Path(sfn).unlink()

def setup_logging():
    """Configure application logging"""
    
    # Create logs directory
    logs_dir = Path('logs')
    logs_dir.mkdir(exist_ok=True)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler for all logs
    file_handler = CompressedRotatingFileHandler(
        logs_dir / 'application.log',
        maxBytes=50*1024*1024,  # 50MB
        backupCount=10
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)
    
    # Separate error log
    error_handler = CompressedRotatingFileHandler(
        logs_dir / 'errors.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(error_handler)
    
    # Component-specific loggers
    components = ['scraper', 'mapper', 'adapter', 'queue', 'ui', 'llm']
    
    for component in components:
        logger = logging.getLogger(component)
        handler = CompressedRotatingFileHandler(
            logs_dir / f'{component}.log',
            maxBytes=20*1024*1024,  # 20MB
            backupCount=3
        )
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
    
    # Audit logger (never rotates, keeps all records)
    audit_logger = logging.getLogger('audit')
    audit_handler = logging.FileHandler(logs_dir / 'audit.log')
    audit_handler.setFormatter(JSONFormatter())
    audit_logger.addHandler(audit_handler)
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False
    
    logging.info("Logging system initialized")

# Audit logging utilities
def log_application_attempt(job_id: str, platform: str, action: str, details: dict = None):
    """Log application attempt for audit trail"""
    audit_logger = logging.getLogger('audit')
    audit_logger.info(
        f"Application {action}",
        extra={
            'job_id': job_id,
            'platform': platform,
            'action': action,
            'details': details or {}
        }
    )

def log_llm_usage(provider: str, model: str, tokens: int, cost: float, request_type: str):
    """Log LLM usage for cost tracking"""
    audit_logger = logging.getLogger('audit')
    audit_logger.info(
        "LLM API call",
        extra={
            'provider': provider,
            'model': model,
            'tokens': tokens,
            'cost_usd': cost,
            'request_type': request_type
        }
    )
