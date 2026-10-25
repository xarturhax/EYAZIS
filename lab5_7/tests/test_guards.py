import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import sounddevice as sd
import soundfile as sf

from lab5_7.application.experiments import assemble, extract_bank
from lab5_7.infrastructure.analysis import analyze
from lab5_7.infrastructure.capture import record
from lab5_7.infrastructure.prosody import coupled_contour
from lab5_7.tests.test_audio import tone


class GuardTests(unittest.TestCase):
    def test_dynamic_coupled_clock_changes_pitch_and_duration(self):
        result = coupled_contour(tone(), [(0, 2), (1, 2)])
        self.assertAlmostEqual(result.duration, 0.5, delta=0.002)
        self.assertAlmostEqual(analyze(result)["f0_median_hz"], 400, delta=5)
        unchanged = coupled_contour(tone(), [(0, 1), (1, 1)])
        self.assertTrue(np.allclose(unchanged.samples, tone().samples, atol=1e-10))

    def test_draft_recipe_is_not_executed(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            with self.assertRaises(ValueError):
                assemble("ref1_phones", base, base / "output.wav", 0)
            self.assertFalse((base / "output.wav").exists())

    def test_unreviewed_segments_do_not_become_bank_units(self):
        row = dict(id="ph_a", file="missing.wav", start=".1", end=".2", reviewed="", kind="phone")
        with tempfile.TemporaryDirectory() as directory:
            with patch("lab5_7.application.experiments.segments", return_value=[row]):
                self.assertEqual(extract_bank(Path(directory)), 0)
            self.assertFalse((Path(directory) / "ph_a.wav").exists())

    def test_microphone_is_mocked_and_capture_uses_requested_pcm(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recording.wav"
            with (
                patch("sounddevice.check_input_settings"),
                patch("sounddevice.rec", return_value=np.zeros((8000, 1))) as rec,
                patch("sounddevice.wait", return_value=None),
                patch("sounddevice.stop"),
            ):
                record(path, 1, 8000, 8, None)
                rec.assert_called_once()
            self.assertEqual(sf.info(path).subtype, "PCM_U8")
            with self.assertRaises(FileExistsError):
                record(path, 1, 8000, 8, None)

    def test_device_error_does_not_create_fake_wav(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.wav"
            with (
                patch(
                    "sounddevice.check_input_settings", side_effect=sd.PortAudioError("unavailable")
                ),
                patch("sounddevice.rec") as rec,
            ):
                with self.assertRaises(ValueError):
                    record(path, 1, 8000, 16, None)
                rec.assert_not_called()
            self.assertFalse(path.exists())
