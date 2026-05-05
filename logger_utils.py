import logging
from datetime import datetime
from pathlib import Path


def get_daily_logger(name: str, log_dir: Path | None = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    base_dir = Path(__file__).resolve().parent
    target_dir = log_dir or (base_dir / 'logs')
    target_dir.mkdir(parents=True, exist_ok=True)

    log_file = target_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(filename)s:%(lineno)d | %(message)s'
    )

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.propagate = False
    return logger
