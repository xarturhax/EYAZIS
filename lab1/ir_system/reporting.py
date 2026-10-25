"""Единые имена и пояснения метрик для интерфейса и файлов отчёта."""

from lab1.ir_system.domain.models import MetricValues, RetrievalCounts, SearchResult

METRIC_DESCRIPTIONS = {
    "Precision": "Доля релевантных среди всех найденных документов",
    "Recall": "Доля найденных среди всех релевантных документов коллекции",
    "AP": "Среднее точностей на релевантных позициях; пропуски дают нулевой вклад",
    "MAP": "Арифметическое среднее AP по допустимым запросам",
    "P@5": "Число релевантных в первых 5 результатах / 5",
    "P@10": "Число релевантных в первых 10 результатах / 10",
    "R-precision": "Точность первых R результатов; R — число релевантных в коллекции",
}


def metric_values(metrics: MetricValues, aggregate: bool = False) -> dict[str, float]:
    return {
        "Precision": metrics.precision,
        "Recall": metrics.recall,
        "MAP" if aggregate else "AP": metrics.average_precision,
        "P@5": metrics.precision_at_5,
        "P@10": metrics.precision_at_10,
        "R-precision": metrics.r_precision,
    }


def count_values(counts: RetrievalCounts) -> dict[str, int]:
    return {
        "retrieved": counts.retrieved,
        "relevant": counts.relevant,
        "TP": counts.tp,
        "FP": counts.fp,
        "FN": counts.fn,
        "TN": counts.tn,
    }


def search_result_values(result: SearchResult) -> dict:
    return {
        "id": result.document.id,
        "title": result.document.title,
        "url": result.document.url,
        "score": result.score,
        "matched_words": list(result.matched_words),
        "snippet": result.snippet,
    }
