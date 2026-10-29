import unittest

import numpy as np

from lab5_7.application.prosody_experiment import Phrase, WordRange
from lab5_7.application.question_refinement import refined_controls, reinforce_question
from lab5_7.domain.audio import Audio
from lab5_7.infrastructure.prosody import manipulate


class QuestionRefinementTests(unittest.TestCase):
    def setUp(self):
        rate = 16000
        times = np.arange(rate * 3) / rate
        self.audio = Audio(0.02 * np.sin(2 * np.pi * 100 * times), rate)
        self.phrase = Phrase(
            self.audio,
            tuple(WordRange(w, i, i + 1) for i, w in enumerate(["student", "pisal", "referat"])),
            0,
            3,
            (),
        )

    def test_trial_contours_are_finite_ordered_and_do_not_relabel_anchors(self):
        original = self.audio.samples.copy()
        for focus in (0, 1):
            for contour in ("nucleus_fall", "terminal_rise"):
                controls = refined_controls(self.phrase, focus, contour)
                points = controls["pitch_points"]
                self.assertTrue(all(0 <= t <= 3 and 60 <= f <= 500 for t, f in points))
                self.assertTrue(all(a[0] < b[0] for a, b in zip(points, points[1:], strict=False)))
                self.assertIn("NOT_HUMAN_CONFIRMED", controls["anchor_status"])
                result = manipulate(self.audio, points)
                self.assertAlmostEqual(result.duration, self.audio.duration, delta=0.003)
                self.assertTrue(np.isfinite(result.samples).all())
        np.testing.assert_array_equal(self.audio.samples, original)

    def test_invalid_focus_or_style_is_rejected(self):
        for focus, style in [(2, "nucleus_fall"), (0, "unknown")]:
            with self.assertRaises(ValueError):
                refined_controls(self.phrase, focus, style)

    def test_reinforcement_gain_uses_selected_output_word(self):
        controls = refined_controls(self.phrase, 1, "terminal_rise")
        base = manipulate(self.audio, controls["pitch_points"])
        changed, controls = reinforce_question(self.phrase, 1, 2)
        self.assertAlmostEqual(changed.duration, base.duration, delta=0.003)
        np.testing.assert_array_equal(changed.samples[:16000], base.samples[:16000])
        np.testing.assert_array_equal(changed.samples[32000:], base.samples[32000:])
        ratio = np.sqrt(
            np.mean(changed.samples[16500:31500] ** 2) / np.mean(base.samples[16500:31500] ** 2)
        )
        self.assertAlmostEqual(float(ratio), 10 ** (4.5 / 20), places=5)

    def test_reinforcement_maps_stretched_ranges(self):
        changed, controls = reinforce_question(self.phrase, 1, 3)
        self.assertAlmostEqual(changed.duration, 3 + 0.15 * 0.99, delta=0.003)
        spans = controls["output_word_ranges"]
        self.assertAlmostEqual(spans[-1]["end"], changed.duration)
        self.assertAlmostEqual(spans[1]["end"], spans[2]["start"])
        self.assertTrue(np.isfinite(changed.samples).all())
        with self.assertRaises(ValueError):
            reinforce_question(self.phrase, 1, 1)
