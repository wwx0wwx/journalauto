from __future__ import annotations

import logging
from pathlib import Path


LOGGER_NAME = 'night_journal'


def get_logger(log_dir: Path) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    log_dir.mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(message)s')

    file_handler = logging.FileHandler(log_dir / 'night-journal.log', encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
