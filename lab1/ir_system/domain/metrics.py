"""Метрики дорожки поиска РОМИП’2004 и 11-точечная интерполяция TREC."""

from collections.abc import Mapping, Sequence
from dataclasses import fields
from statistics import mean

from .errors import ValidationError
from .models import MetricValues, PrecisionRecallPoint, RankingEvaluation, RetrievalCounts
from .text import validate_grade

RECALL_LEVELS = tuple(level / 10 for level in range(11))


def evaluate_ranking(ranking: Sequence[int], grades: Mapping[int, int]) -> RankingEvaluation:
    if len(set(ranking)) != len(ranking):
        raise ValidationError("Выдача содержит повторяющиеся документы")
    if any(document_id not in grades for document_id in ranking):
        raise ValidationError("Не все документы выдачи оценены")
    for grade in grades.values():
        validate_grade(grade)
    relevant = {d for d, grade in grades.items() if grade > 0}
    total_relevant = len(relevant)
    if not total_relevant:
        raise ValidationError("Запрос без релевантных документов исключается из оценки РОМИП")
    hits = 0
    ap_sum = 0.0
    curve = []
    for rank, document_id in enumerate(ranking, 1):
        if document_id in relevant:
            hits += 1
            ap_sum += hits / rank
        curve.append(PrecisionRecallPoint(rank, hits / rank, hits / total_relevant))
    interpolated = tuple(
        max((point.precision for point in curve if point.recall >= level), default=0.0)
        for level in RECALL_LEVELS
    )
    counts = RetrievalCounts(
        retrieved=len(ranking),
        relevant=total_relevant,
        tp=hits,
        fp=len(ranking) - hits,
        fn=total_relevant - hits,
        tn=len(grades) - total_relevant - (len(ranking) - hits),
    )
    metrics = MetricValues(
        precision=hits / len(ranking) if ranking else 0.0,
        recall=hits / total_relevant,
        average_precision=ap_sum / total_relevant,
        precision_at_5=sum(d in relevant for d in ranking[:5]) / 5,
        precision_at_10=sum(d in relevant for d in ranking[:10]) / 10,
        r_precision=sum(d in relevant for d in ranking[:total_relevant]) / total_relevant,
    )
    return RankingEvaluation(counts, metrics, tuple(curve), interpolated)


def average_metrics(evaluations: Sequence[RankingEvaluation]) -> MetricValues:
    if not evaluations:
        raise ValidationError("Нет результатов для усреднения")
    return MetricValues(
        **{
            item.name: mean(getattr(result.metrics, item.name) for result in evaluations)
            for item in fields(MetricValues)
        }
    )
