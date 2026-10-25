import unittest

import numpy as np

from lab8.domain.models import Settings
from lab8.infrastructure.piper import PiperSynthesizer


class RealEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = PiperSynthesizer()

    def test_both_actual_voices_generate_french_waveform(self):
        for voice, rate in (("siwis", 22050), ("tom", 44100)):
            metadata = self.engine.prepare(voice)
            audio = self.engine.synthesize(
                "Bonjour. La littérature nous invite à réfléchir.", Settings(voice), lambda: False
            )
            self.assertEqual(metadata["voice"], voice)
            self.assertEqual(audio.rate, rate)
            self.assertGreater(len(audio.samples) / rate, 1)
            self.assertGreater(np.std(audio.samples), 0.001)

    def test_real_speed_and_volume_controls(self):
        self.engine.prepare("siwis")
        text = "Le lecteur découvre un personnage et partage ses émotions."
        slow = self.engine.synthesize(text, Settings("siwis", 0.75, 0.8), lambda: False)
        fast = self.engine.synthesize(text, Settings("siwis", 1.5, 0.8), lambda: False)
        quiet = self.engine.synthesize(text, Settings("siwis", 0.75, 0.4), lambda: False)
        self.assertLess(len(fast.samples), len(slow.samples))
        self.assertEqual(len(slow.samples), len(quiet.samples))
        ratio = np.sqrt(np.mean(quiet.samples**2)) / np.sqrt(np.mean(slow.samples**2))
        self.assertAlmostEqual(float(ratio), 0.5, delta=0.02)
