"""Composition root and rotating application log."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from lab3.application.experiment import Summarizer
from lab3.domain.ranking import PositionalRanker
from lab3.infrastructure.nlp import SpacyAnalyzer
from lab3.infrastructure.textrank import TextRank

ROOT = Path(__file__).resolve().parent
DEMO = ROOT / "data" / "demo" / "manifest.json"


def build_summarizer() -> Summarizer:
    return Summarizer(SpacyAnalyzer(), [PositionalRanker(), TextRank()])


def configure_logging() -> None:
    folder = ROOT / "logs"
    folder.mkdir(exist_ok=True)
    handler = RotatingFileHandler(
        folder / "lab3.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.getLogger("lab3").addHandler(handler)
    logging.getLogger("lab3").setLevel(logging.INFO)
