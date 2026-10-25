"""Версия 2 отчёта: поисковые метрики РОМИП, количества и исключения."""

from dataclasses import asdict

from lab1.ir_system.domain.models import EvaluationReport
from lab1.ir_system.reporting import count_values, metric_values


def report_to_dict(report: EvaluationReport) -> dict:
    rows = []
    for row in report.rows:
        rows.append(
            {
                "query": row.query,
                "ranking": list(row.ranking),
                **metric_values(row.evaluation.metrics),
                **count_values(row.evaluation.counts),
                "curve": [asdict(point) for point in row.evaluation.curve],
                "interpolated": list(row.evaluation.interpolated),
            }
        )
    return {
        "schema_version": 2,
        "methodology": "РОМИП’2004: дорожка поиска; интерполяция TREC",
        "document_count": report.document_count,
        "precision_cutoffs": [5, 10],
        "averaging": "Арифметическое среднее по запросам с R > 0",
        "excluded_queries": [asdict(query) for query in report.excluded_queries],
        "parameters": asdict(report.parameters),
        "rows": rows,
        "averages": metric_values(report.averages, aggregate=True),
        "mean_interpolated": list(report.mean_interpolated),
    }
