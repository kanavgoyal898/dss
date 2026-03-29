"""
Purpose: Centralised logging configuration for the DSS Peer Node process.
Responsibilities:
    - Configure Python's logging subsystem with a structured format.
    - Set log levels for the peer node service tree.
    - Expose a configure_logging() function called at application startup.
Dependencies: logging
"""

import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """
    Configure root and DSS-namespace loggers with a timestamped format.
    level must be a valid logging level string (DEBUG, INFO, WARNING, ERROR).
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt))
    root = logging.getLogger()
    root.setLevel(numeric_level)
    root.addHandler(handler)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
