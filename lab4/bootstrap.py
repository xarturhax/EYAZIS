import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from lab4.application.translation import TranslationService
from lab4.infrastructure.lexicon import SqliteLexicon
from lab4.infrastructure.marian import MarianTranslator
from lab4.infrastructure.nlp import EnglishAnalyzer

ROOT = Path(__file__).resolve().parent


def build_service(database: Path | None = None) -> tuple[TranslationService, SqliteLexicon]:
    lexicon = SqliteLexicon(database or ROOT / "data" / "lexicon.sqlite3")
    return TranslationService(EnglishAnalyzer(), MarianTranslator(), lexicon), lexicon


def configure_logging() -> None:
    folder = ROOT / "logs"
    folder.mkdir(exist_ok=True)
    handler = RotatingFileHandler(
        folder / "lab4.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger = logging.getLogger("lab4")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
