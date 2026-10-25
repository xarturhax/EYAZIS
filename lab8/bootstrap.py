import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from lab8.application.service import SpeechService
from lab8.infrastructure.piper import PiperSynthesizer

ROOT = Path(__file__).resolve().parent


def build_service() -> SpeechService:
    return SpeechService(PiperSynthesizer())


def configure_logging() -> None:
    folder = ROOT / "logs"
    folder.mkdir(exist_ok=True)
    handler = RotatingFileHandler(
        folder / "lab8.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger = logging.getLogger("lab8")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        logger.addHandler(handler)
