import platform
from importlib.metadata import version
from pathlib import Path

from lab2.application.experiment import Experiment
from lab2.domain.classifiers import AlphabetClassifier, ShortWordClassifier
from lab2.domain.models import Settings
from lab2.infrastructure.pdf import PdfDocumentReader

ROOT = Path(__file__).resolve().parent
DEMO_MANIFEST = ROOT / "data" / "demo" / "manifest.json"


def build_experiment(settings: Settings) -> Experiment:
    from lab2.infrastructure.neural import NeuralClassifier

    versions = {
        package: version(package) for package in ("pypdf", "scikit-learn", "numpy", "scipy")
    }
    versions["python"] = platform.python_version()
    versions["platform"] = platform.platform()
    return Experiment(
        PdfDocumentReader(),
        [ShortWordClassifier(settings), AlphabetClassifier(settings), NeuralClassifier(settings)],
        settings,
        versions,
    )
