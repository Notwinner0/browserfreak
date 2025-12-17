"""
Logging configuration for BrowserFreak
"""

import sys
from pathlib import Path

from loguru import logger

from .config import settings


def setup_logging():
    """Configure logging for the application"""

    # Remove default handler
    logger.remove()

    # Determine log level
    log_level = settings.agent.log_level.upper()

    # Console handler with color
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # File handler for errors and above
    log_file = Path("logs/browserfreak.log")
    log_file.parent.mkdir(exist_ok=True)

    logger.add(
        log_file,
        level="WARNING",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="10 MB",
        retention="1 week",
        encoding="utf-8",
    )

    # File handler for all logs
    logger.add(
        log_file.with_suffix(".debug.log"),
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="50 MB",
        retention="3 days",
        encoding="utf-8",
    )

    logger.info("Logging configured successfully")
    return logger


# Global logger instance
log = setup_logging()
