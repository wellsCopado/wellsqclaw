"""
CryptoMind Pro Plus AI - Log System
Supports file + console logging, Android compatible
LOG_DIR can be overridden at runtime by embedded_server._setup_android_paths()
"""
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Log directory - can be overridden at runtime for Android
LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "logs"
)

# Will be set to True once directories are ready
_initialized = False


def _ensure_log_dir():
    """Ensure log directory exists"""
    global _initialized
    if not _initialized:
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            _initialized = True
        except Exception:
            pass


def setup_logger(name: str = "CryptoMind", level: int = logging.INFO) -> logging.Logger:
    """Create and configure logger"""
    logger = logging.getLogger(name)
    
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File log (daily rolling)
    _ensure_log_dir()
    log_file = os.path.join(LOG_DIR, f"cryptomind_{datetime.now().strftime('%Y%m%d')}.log")
    try:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except IOError:
        pass  # Android early stage may not be able to write file
    
    return logger


# Global logger
logger = setup_logger()
