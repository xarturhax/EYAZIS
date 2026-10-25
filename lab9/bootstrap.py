import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_COMMANDS = ROOT / "data/commands.json"


def configure_logging() -> None:
    folder = ROOT / "logs"
    folder.mkdir(exist_ok=True)
    logger = logging.getLogger("lab9")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = RotatingFileHandler(
            folder / "lab9.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
