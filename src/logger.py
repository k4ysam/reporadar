from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path


def get_logger(name: str, run_id: str) -> logging.LoggerAdapter:
    logger = logging.getLogger(name)
    if not logger.handlers:
        fmt = "%(asctime)s [%(levelname)s] [run=%(run_id)s] %(name)s: %(message)s"
        formatter = logging.Formatter(fmt)

        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)

        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "reporadar.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        logger.setLevel(logging.INFO)

    return logging.LoggerAdapter(logger, {"run_id": run_id})
