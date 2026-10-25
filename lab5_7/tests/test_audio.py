import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from lab5_7.application.experiments import quality
from lab5_7.domain.audio import Audio, concatenate, crop, gain, loop, resample
from lab5_7.infrastructure.analysis import analyze, export_analysis
from lab5_7.infrastructure.prosody import coupled_shift, manipulate
from lab5_7.infrastructure.wav import load, save


def tone(rate=16000, duration=1.0, frequency=200):
    return Audio(
        0.3 * np.sin(2 * np.pi * frequency * np.arange(round(rate * duration)) / rate), rate
    )


class AudioTests(unittest.TestCase):
    def test_audio_validation(self):
        for samples in (np.array([]), np.array([np.nan]), np.zeros((2, 2))):
            with self.assertRaises(ValueError):
                Audio(samples, 16000)

    def test_crop_maps_time_to_samples_without_changing_original(self):
        audio = tone()
        piece = crop(audio, 0.1, 0.2)
        self.assertEqual(len(piece.samples), 1600)
        self.assertTrue(np.array_equal(piece.samples, audio.samples[1600:3200]))
        for a, b in [(-0.1, 0.2), (0.2, 0.1), (0, 2)]:
            with self.assertRaises(ValueError):
                crop(audio, a, b)

    def test_resampling_preserves_duration_and_rejects_alias(self):
        audio = tone(frequency=3000)
        result = resample(audio, 4000)
        self.assertAlmostEqual(result.duration, audio.duration, places=3)
        self.assertLess(np.sqrt(np.mean(result.samples[100:-100] ** 2)), 0.01)

    def test_pcm_subtypes_and_eight_bit_quantization(self):
        audio = tone()
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for bits, subtype in [(8, "PCM_U8"), (16, "PCM_16")]:
                path = base / f"{bits}.wav"
                save(audio, path, bits)
                self.assertEqual(sf.info(path).subtype, subtype)
                restored, _ = load(path)
                self.assertEqual(len(restored.samples), len(audio.samples))
            a = load(base / "8.wav")[0].samples
            b = load(base / "16.wav")[0].samples
            self.assertGreater(np.mean((a - audio.samples) ** 2), np.mean((b - audio.samples) ** 2))
            with self.assertRaises(FileExistsError):
                save(audio, base / "8.wav")

    def test_stereo_analysis_uses_explicit_first_channel(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stereo.wav"
            x = tone().samples
            sf.write(path, np.column_stack((x, -x)), 16000)
            result, metadata = load(path)
            self.assertGreater(np.std(result.samples), 0.1)
            self.assertEqual(metadata["channels"], 2)
            self.assertEqual(metadata["analysis_channel"], 1)

    def test_concatenation_crossfade_length_and_rate_guard(self):
        audio = tone(duration=0.1)
        plain = concatenate([audio, audio])
        smooth = concatenate([audio, audio], 5)
        self.assertEqual(len(plain.samples), 3200)
        self.assertEqual(len(smooth.samples), 3120)
        with self.assertRaises(ValueError):
            concatenate([audio, tone(rate=8000)])

    def test_gain_and_clip_guard(self):
        audio = tone()
        result = gain(audio, 0.2, 0.8, 6)
        ratio = np.std(result.samples[4000:8000]) / np.std(audio.samples[4000:8000])
        self.assertAlmostEqual(ratio, 10 ** (6 / 20), places=3)
        with self.assertRaises(ValueError):
            gain(audio, 0, 1, 24)

    def test_period_loop_has_expected_length(self):
        result = loop(crop(tone(), 0.1, 0.105), 200)
        self.assertEqual(len(result.samples), 16000)
        self.assertAlmostEqual(analyze(result)["f0_median_hz"], 200, delta=2)

    def test_pitch_and_silence_are_not_confused(self):
        self.assertAlmostEqual(analyze(tone())["f0_median_hz"], 200, delta=2)
        silence = analyze(Audio(np.zeros(16000), 16000))
        self.assertIsNone(silence["f0_median_hz"])
        self.assertTrue(all(v is None for v in silence["f0_hz"]))
        self.assertTrue(silence["warnings"])

    def test_psola_pitch_preserves_duration(self):
        result = manipulate(tone(), [(0, 300), (1, 300)])
        self.assertAlmostEqual(result.duration, 1, delta=0.01)
        self.assertAlmostEqual(analyze(result)["f0_median_hz"], 300, delta=5)

    def test_duration_tier_and_coupled_shift_have_distinct_effects(self):
        stretched = manipulate(tone(), [], [(0, 1.2), (1, 1.2)])
        shifted = coupled_shift(tone(), 12)
        self.assertAlmostEqual(stretched.duration, 1.2, delta=0.03)
        self.assertAlmostEqual(shifted.duration, 0.5, delta=0.01)
        self.assertAlmostEqual(analyze(shifted)["f0_median_hz"], 400, delta=5)

    def test_invalid_pitch_points_are_rejected(self):
        for points in [[(0.7, 200), (0.2, 250)], [(2, 200)], [(0, 10)]]:
            with self.assertRaises(ValueError):
                manipulate(tone(), points)

    def test_quality_experiment_keeps_human_assessment_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            path = base / "tone.wav"
            save(tone(), path)
            quality(path, base / "quality", "synthetic")
            result = json.loads((base / "quality/experiment.json").read_text(encoding="utf-8"))
            self.assertEqual(len(result["results"]), 8)
            self.assertEqual(result["listening_assessment"], "PENDING")
            self.assertEqual(result["source_kind"], "synthetic")
            self.assertTrue(
                all(row["actual_subtype"] in ("PCM_U8", "PCM_16") for row in result["results"])
            )

    def test_technical_report_is_explicitly_not_voice_experiment(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            save(tone(), base / "tone.wav")
            data = export_analysis(base / "tone.wav", base / "report", "synthetic")
            self.assertEqual(data["status"], "TECHNICAL_TEST_ONLY")
            self.assertTrue((base / "report/contours.png").is_file())
            text = (base / "report/report.html").read_text(encoding="utf-8")
            self.assertIn("СИНТЕТИЧЕСКИЙ", text)
