"""Проверяем смысл рисунков: реальные данные, подписи, шкалы и источник кривой."""

import unittest
from dataclasses import replace

from lab1.ir_system.bootstrap import application_runtime
from lab1.ir_system.config import AppConfig
from lab1.ir_system.domain.metrics import RECALL_LEVELS
from lab1.ir_system.visualization import comparison_figure, metrics_figure, precision_recall_figure


class VisualizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with application_runtime(replace(AppConfig(), database=":memory:")) as services:
            collection = services.collection.import_demo()
            cls.report = services.evaluation.evaluate(collection.queries)

    def test_summary_has_six_metrics_and_exact_mean_values(self):
        figure = metrics_figure(self.report)
        axes = figure.axes[0]
        self.assertEqual(
            [t.get_text() for t in axes.get_yticklabels()],
            ["Precision", "Recall", "MAP", "P@5", "P@10", "R-precision"],
        )
        self.assertEqual(
            [p.get_width() for p in axes.patches], [0.85, 0.95, 0.9375, 0.48, 0.24, 0.95]
        )
        self.assertIn("Значение", axes.get_xlabel())

    def test_mean_curve_is_trec_and_single_query_has_separate_raw_curve(self):
        mean_axes = precision_recall_figure(self.report).axes[0]
        self.assertEqual(len(mean_axes.lines), 1)
        self.assertEqual(tuple(mean_axes.lines[0].get_xdata()), RECALL_LEVELS)
        self.assertEqual(tuple(mean_axes.lines[0].get_ydata()), self.report.mean_interpolated)
        self.assertIn("Полнота", mean_axes.get_xlabel())
        self.assertIn("Точность", mean_axes.get_ylabel())
        row = self.report.rows[0]
        axes = precision_recall_figure(self.report, row).axes[0]
        self.assertEqual(len(axes.lines), 2)
        self.assertEqual(
            tuple(axes.lines[0].get_xdata()), tuple(p.recall for p in row.evaluation.curve)
        )
        self.assertEqual(tuple(axes.lines[1].get_ydata()), row.evaluation.interpolated)
        self.assertIn("Фактические", axes.lines[0].get_label())

    def test_comparison_has_every_query_and_six_metrics_on_one_scale(self):
        axes = comparison_figure(self.report).axes[0]
        self.assertEqual(axes.images[0].get_array().shape, (5, 6))
        self.assertEqual(axes.images[0].get_clim(), (0, 1))
        self.assertEqual(
            [t.get_text().replace("\n", " ") for t in axes.get_yticklabels()],
            [row.query for row in self.report.rows],
        )
        self.assertEqual(len(axes.texts), 30)

    def test_empty_retrieval_curve_does_not_invent_raw_points(self):
        from lab1.ir_system.domain.metrics import evaluate_ranking
        from lab1.ir_system.domain.models import QueryEvaluation

        row = QueryEvaluation("unknown", (), evaluate_ranking([], {1: 2}))
        axes = precision_recall_figure(self.report, row).axes[0]
        self.assertEqual(len(axes.lines), 1)
        self.assertEqual(tuple(axes.lines[0].get_ydata()), (0,) * 11)
