"""
Logging configuration for the QToken protocol
"""

import logging
import sys
from config.defaults import DEFAULT_LOG_LEVEL


def setup_logging(level=None, name=None):
    """
    Configure logging for the application

    Args:
        level (str): Log level (DEBUG, INFO, WARNING, ERROR)
        name (str): Logger name
    """
    if level is None:
        level = DEFAULT_LOG_LEVEL

    # Format configuration
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    # Console handler configuration
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Logger configuration
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    logger.addHandler(console_handler)

    # Avoid log duplication
    logger.propagate = False

    return logger
