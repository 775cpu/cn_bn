import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler


def setup_logging(log_dir: str, max_bytes: int = 10 * 1024 * 1024, backup_count: int = 5) -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    for name in ("app", "network", "mismatch", "error"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        handler = RotatingFileHandler(Path(log_dir) / f"{name}.log", maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    logging.getLogger("app").addHandler(console)
    root.addHandler(console)
    error_handler = RotatingFileHandler(Path(log_dir) / "error.log", maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root.addHandler(error_handler)


def setup_symbol_mismatch_logging(log_dir: str, symbol: str, max_bytes: int = 10 * 1024 * 1024, backup_count: int = 5) -> logging.Logger:
    logger = logging.getLogger(f"mismatch.{symbol}")
    logger.setLevel(logging.ERROR)
    logger.propagate = False
    if not logger.handlers:
        handler = RotatingFileHandler(Path(log_dir) / f"mismatch_{symbol}.log", maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
    return logger
