import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logger(
    name: str = "job_scraper",
    log_dir: str = "logs",
    log_file: str = "app.log",
    level: int = logging.INFO,
) -> logging.Logger:
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # evita duplicar handlers se rodar no Spyder várias vezes
    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Arquivo rotativo
    fh = RotatingFileHandler(
        filename=os.path.join(log_dir, log_file),
        maxBytes=5_000_000,   # 5MB
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(level)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    logger.propagate = False
    return logger
