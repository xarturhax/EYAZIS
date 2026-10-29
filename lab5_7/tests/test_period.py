import unittest

import numpy as np

from lab5_7.domain.audio import Audio
from lab5_7.tools.build_lab5 import period_bounds


class PeriodTests(unittest.TestCase):
    def test_finds_real_cycle_and_preserves_source(self):
        rate = 16000
        t = np.arange(rate) / rate
        samples = 0.02 * np.sin(2 * np.pi * 100 * t) + 0.01 * np.sin(2 * np.pi * 200 * t)
        audio = Audio(samples.copy(), rate)
        start, end = period_bounds(audio, 103)
        self.assertAlmostEqual((end - start) / rate, 0.01, delta=1 / rate)
        np.testing.assert_array_equal(audio.samples, samples)
        self.assertTrue(0 < start < end < len(samples))

    def test_missing_or_invalid_period_evidence_is_rejected(self):
        for audio, f0 in [
            (Audio(np.zeros(16000), 16000), 100),
            (Audio(np.ones(16000), 16000), 100),
            (Audio(np.ones(100), 16000), 100),
            (Audio(np.ones(16000), 16000), float("nan")),
            (Audio(np.ones(16000), 16000), 0),
        ]:
            with self.subTest(f0=f0), self.assertRaises(ValueError):
                period_bounds(audio, f0)
