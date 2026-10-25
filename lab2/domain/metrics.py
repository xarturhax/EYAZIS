"""Отказы учитываются как ошибки, неразмеченные файлы исключаются из accuracy."""

from collections.abc import Sequence
from statistics import mean

from .models import LANGUAGES, METHOD_NAMES, ClassMetrics, MethodMetrics, ResultRow


def evaluate(rows: Sequence[ResultRow]) -> dict[str, MethodMetrics]:
    result: dict[str, MethodMetrics] = {}
    for method in METHOD_NAMES:
        labeled = [row for row in rows if row.expected is not None]
        matrix: dict[str, dict[str, int]] = {
            truth: {prediction: 0 for prediction in (*LANGUAGES, "?")} for truth in LANGUAGES
        }
        for row in labeled:
            matrix[str(row.expected)][row.predictions[method].language or "?"] += 1
        correct = sum(matrix[lang][lang] for lang in LANGUAGES)
        per_class: dict[str, ClassMetrics] = {}
        for lang in LANGUAGES:
            tp = matrix[lang][lang]
            predicted = sum(matrix[truth][lang] for truth in LANGUAGES)
            actual = sum(matrix[lang].values())
            precision = tp / predicted if predicted else 0.0
            recall = tp / actual if actual else 0.0
            per_class[lang] = {
                "precision": precision,
                "recall": recall,
                "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            }
        result[method] = {
            "labeled": len(labeled),
            "correct": correct,
            "accuracy": correct / len(labeled) if labeled else None,
            "macro_f1": mean(v["f1"] for v in per_class.values()) if labeled else None,
            "abstentions": sum(row.predictions[method].language is None for row in rows),
            "mean_ms": mean(row.milliseconds[method] for row in rows) if rows else 0.0,
            "confusion": matrix,
            "per_class": per_class,
        }
    return result
