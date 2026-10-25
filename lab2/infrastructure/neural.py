"""Нейросеть обучается только на train: символьный TF-IDF -> MLP."""

import warnings
from collections.abc import Sequence

from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neural_network import MLPClassifier
from threadpoolctl import threadpool_limits

from lab2.domain.classifiers import unknown
from lab2.domain.models import Document, LabError, Prediction, Settings
from lab2.domain.text import input_problem, words


class NeuralClassifier:
    name = "neural"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.vectorizer = TfidfVectorizer(
            analyzer="char",
            ngram_range=(2, 4),
            lowercase=True,
            max_features=settings.neural_features,
            sublinear_tf=True,
        )
        self.model = MLPClassifier(
            hidden_layer_sizes=(settings.neural_hidden,),
            solver="lbfgs",
            alpha=0.01,
            max_iter=settings.neural_iterations,
            random_state=settings.seed,
        )
        self.notes: list[str] = []
        self.samples = 0
        self.fitted = False

    def fit(self, documents: Sequence[Document]) -> None:
        self.fitted = False
        texts, labels = [], []
        for document in documents:
            tokens = words(document.text)
            for start in range(0, len(tokens), self.settings.chunk_words):
                chunk = tokens[start : start + self.settings.chunk_words]
                if len(chunk) >= 10:
                    texts.append(" ".join(chunk))
                    labels.append(document.entry.language)
        if len(set(labels)) != 2:
            raise LabError("Для нейросети нужны непустые документы обоих языков")
        features = self.vectorizer.fit_transform(texts)
        with threadpool_limits(limits=1), warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ConvergenceWarning)
            self.model.fit(features, labels)
        self.notes = [str(item.message) for item in caught]
        self.samples = len(texts)
        self.fitted = True

    def predict(self, text: str) -> Prediction:
        if not self.fitted:
            raise LabError("Сначала обучите нейросеть")
        if problem := input_problem(text):
            return unknown(problem)
        features = self.vectorizer.transform([" ".join(words(text))])
        if features.nnz == 0:
            return unknown("Ни одного известного символьного признака.")
        with threadpool_limits(limits=1):
            probabilities = self.model.predict_proba(features)[0]
        scores = {
            str(language): float(p)
            for language, p in zip(self.model.classes_, probabilities, strict=True)
        }
        label = self.model.classes_[int(probabilities.argmax())]
        if abs(scores["en"] - scores["es"]) < 1e-10:
            label = None
        return Prediction(
            label,
            scores,
            "оценка MLP; больше лучше",
            "Вероятности модели не калиброваны. Выбор только между EN и ES; "
            "другие языки на латинице могут быть ошибочно отнесены к одному из них.",
        )

    def describe(self) -> dict[str, object]:
        return {
            "features": len(self.vectorizer.vocabulary_),
            "samples": self.samples,
            "hidden_layers": [self.settings.neural_hidden],
            "solver": "lbfgs",
            "iterations": int(self.model.n_iter_),
            "loss": float(self.model.loss_),
            "warnings": self.notes,
            "ngrams": [2, 4],
        }
