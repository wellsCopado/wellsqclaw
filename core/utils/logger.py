"""
CryptoMind Pro Plus AI - 日志系统
支持文件日志 + 控制台日志，Android 兼容
"""
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# 日志目录
LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "logs"
)
os.makedirs(LOG_DIR, exist_ok=True)


def setup_logger(name: str = "CryptoMind", level: int = logging.INFO) -> logging.Logger:
    """创建并配置 logger"""
    logger = logging.getLogger(name)
    
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件日志（按天滚动）
    log_file = os.path.join(LOG_DIR, f"cryptomind_{datetime.now().strftime('%Y%m%d')}.log")
    try:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except IOError:
        pass  # Android 早期可能无法写入文件
    
    return logger


# 全局 logger
logger = setup_logger()
