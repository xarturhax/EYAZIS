import unittest

import numpy as np

from lab5_7.application.prosody_experiment import Phrase, WordRange, derive_phrase, transform
from lab5_7.domain.audio import Audio


class ProsodyExperimentTests(unittest.TestCase):
    def setUp(self):
        self.rate = 16000
        t = np.arange(self.rate * 3) / self.rate
        self.audio = Audio(0.03 * np.sin(2 * np.pi * 100 * t), self.rate)
        self.phrase = Phrase(
            self.audio,
            tuple(
                WordRange(label, i, i + 1)
                for i, label in enumerate(["student", "pisal", "referat"])
            ),
            0,
            3,
            (),
        )

    def test_contiguous_source_is_not_duplicate_word_concatenation(self):
        rows = [
            dict(
                id="student_" + label,
                file="student.wav",
                start=str(start),
                end=str(end),
                reviewed="yes",
                note=note,
            )
            for label, start, end, note in [
                ("student", 0.1, 1.1, ""),
                ("pisal", 1.07, 2.05, "joined articulation"),
                ("referat", 2.03, 2.9, ""),
            ]
        ]
        phrase = derive_phrase(self.audio, rows)
        self.assertAlmostEqual(phrase.audio.duration, 2.8)
        self.assertEqual(phrase.words[0].end, phrase.words[1].start)
        self.assertEqual(phrase.words[1].end, phrase.words[2].start)
        self.assertLessEqual(phrase.words[-1].end, phrase.audio.duration)
        np.testing.assert_array_equal(phrase.audio.samples, self.audio.samples[1600:46400])
        self.assertIn("joined articulation", phrase.notes)

    def test_unconfirmed_or_reversed_components_are_rejected(self):
        rows = [
            dict(
                id="student_" + label,
                file="student.wav",
                start=str(i),
                end=str(i + 1),
                reviewed="yes",
                note="",
            )
            for i, label in enumerate(["student", "pisal", "referat"])
        ]
        rows[1]["reviewed"] = ""
        with self.assertRaises(ValueError):
            derive_phrase(self.audio, rows)
        rows[1]["reviewed"] = "yes"
        rows[1]["start"] = "2.5"
        with self.assertRaises(ValueError):
            derive_phrase(self.audio, rows)

    def test_f0_only_psola_preserves_duration(self):
        changed, controls = transform(self.phrase, "psola", True, 2, 1)
        self.assertAlmostEqual(changed.duration, self.audio.duration, delta=0.003)
        self.assertEqual(controls["gain_db"], 0)
        self.assertEqual(controls["listening_status"], "PENDING_HUMAN_LISTENING")

    def test_gain_is_applied_to_output_word_after_time_warp(self):
        first, _ = transform(self.phrase, "coupled_contour", True, 1, 1)
        second, controls = transform(self.phrase, "coupled_contour", True, 1, 2)
        span = controls["output_word_ranges"][1]
        a = round((span["start"] + 0.03) * self.rate)
        b = round((span["end"] - 0.03) * self.rate)
        ratio = np.sqrt(np.mean(second.samples[a:b] ** 2) / np.mean(first.samples[a:b] ** 2))
        self.assertAlmostEqual(float(ratio), 10 ** (3 / 20), places=5)
        np.testing.assert_array_equal(
            first.samples[: round(span["start"] * self.rate)],
            second.samples[: round(span["start"] * self.rate)],
        )

    def test_stretch_length_and_partition_mapping(self):
        changed, controls = transform(self.phrase, "psola", False, 1, 3)
        # 1.25 within a 1-second word with two 10-ms linear transition ramps.
        self.assertAlmostEqual(changed.duration, 3 + 0.25 * (1 - 0.01), delta=0.003)
        spans = controls["output_word_ranges"]
        self.assertAlmostEqual(spans[-1]["end"], changed.duration, places=8)
        self.assertAlmostEqual(spans[0]["end"], spans[1]["start"], places=8)

    def test_all_conditions_stay_finite_and_preserve_input(self):
        original = self.audio.samples.copy()
        for method in ["psola", "coupled_contour"]:
            for question in [False, True]:
                for focus in range(3):
                    for stage in [1, 2, 3]:
                        with self.subTest(
                            method=method, question=question, focus=focus, stage=stage
                        ):
                            changed, controls = transform(
                                self.phrase, method, question, focus, stage
                            )
                            self.assertTrue(np.isfinite(changed.samples).all())
                            self.assertLess(float(np.max(np.abs(changed.samples))), 1)
                            for word in controls["output_word_ranges"]:
                                self.assertTrue(
                                    0 <= word["start"] < word["end"] <= changed.duration
                                )
        np.testing.assert_array_equal(original, self.audio.samples)

    def test_invalid_configuration(self):
        for method, focus, stage in [("unknown", 0, 1), ("psola", 3, 1), ("psola", 0, 4)]:
            with self.assertRaises(ValueError):
                transform(self.phrase, method, False, focus, stage)
