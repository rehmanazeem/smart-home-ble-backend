"""Logging setup: stdout plus a timestamped file under Logs/<date>/."""

import logging
import os
from datetime import datetime

LOG_FORMAT = "%(asctime)s %(levelname)s:%(name)s:%(message)s"


def setup_logging(base_dir: str = "Logs") -> str:
    """Attach file and stream handlers to the root logger; return the log file path."""
    now = datetime.now()
    day_dir = os.path.join(base_dir, now.strftime("%Y-%m-%d"))
    os.makedirs(day_dir, exist_ok=True)
    log_file = os.path.join(day_dir, f"{now.strftime('%H-%M-%S')}.log")

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for handler in (logging.FileHandler(log_file), logging.StreamHandler()):
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root.addHandler(handler)

    logging.info("Logging initialized. Log file: %s", log_file)
    return log_file
