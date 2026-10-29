import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

import numpy as np

from lab5_7.application.synthesis_repair import (
    assemble_first_phrase_phones,
    assemble_syllables,
    edge_fade,
    prepare_unit,
)
from lab5_7.domain.audio import Audio
from lab5_7.tools.import_synthesis_listening import import_assessment, validate_assessment


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.rate = 16000
        voice = 0.02 * np.sin(2 * np.pi * 100 * np.arange(4800) / self.rate)
        self.audio = Audio(np.r_[np.zeros(480), voice, np.zeros(800)], self.rate)

    def test_padding_is_trimmed_and_source_preserved(self):
        original = self.audio.samples.copy()
        changed, operation = prepare_unit(self.audio)
        self.assertGreaterEqual(operation["trim_start_samples"], 320)
        self.assertGreaterEqual(operation["trim_end_samples"], 640)
        first = operation["trim_start_samples"]
        np.testing.assert_array_equal(
            changed.samples, original[first : first + len(changed.samples)]
        )
        np.testing.assert_array_equal(original, self.audio.samples)

    def test_transient_is_retained_and_fade_ends_at_zero(self):
        samples = np.r_[np.ones(80) * 0.05, self.audio.samples[480:5280]]
        source = Audio(samples.copy(), self.rate)
        prepared, operation = prepare_unit(source)
        self.assertEqual(operation["trim_start_samples"], 0)
        faded = edge_fade(prepared)
        self.assertEqual(faded.samples[0], 0)
        self.assertAlmostEqual(faded.samples[-1], 0)
        np.testing.assert_array_equal(source.samples, samples)

    def test_syllable_processing_shortens_gaps_without_clipping(self):
        changed, operations = assemble_syllables([self.audio, self.audio], 0.01)
        self.assertLess(changed.duration, self.audio.duration * 2 - 0.1)
        self.assertEqual(len(operations), 2)
        self.assertTrue(all(-3 <= r["gain_db"] <= 3 for r in operations))
        self.assertTrue(np.isfinite(changed.samples).all())
        self.assertLess(np.max(np.abs(changed.samples)), 1)

    def test_phone_timing_never_invents_or_extends_unit_samples(self):
        units = [
            "ph_s",
            "ph_a",
            "ph_sh",
            "ph_a",
            "ph_k",
            "ph_u",
            "ph_sh",
            "ph_a",
            "ph_l",
            "ph_k",
            "ph_a",
            "ph_sh",
            "ph_u",
        ]
        source = Audio(np.ones(3840) * 0.01, self.rate)
        changed, operations = assemble_first_phrase_phones([source] * 13, units, 1.645)
        self.assertAlmostEqual(changed.duration, 1.645, delta=0.002)
        self.assertTrue(all(r["selected_samples"] <= len(source.samples) for r in operations))
        np.testing.assert_array_equal(source.samples, np.ones(3840) * 0.01)

    def test_invalid_or_silent_processing_is_rejected(self):
        with self.assertRaises(ValueError):
            prepare_unit(Audio(np.zeros(1600), self.rate))
        with self.assertRaises(ValueError):
            prepare_unit(self.audio, gain_db=7)
        with self.assertRaises(ValueError):
            assemble_first_phrase_phones([self.audio], ["ph_a"], 1)


class SynthesisImportTests(unittest.TestCase):
    def setUp(self):
        self.results = [
            {
                "id": "test",
                "sha256": "audio",
                "reference_sha256": "ref",
                "category": "phones",
                "wav": "test.wav",
                "reference_wav": "ref.wav",
            }
        ]
        self.data = {
            "schema": 1,
            "assessment_kind": "LAB7_SYNTHESIS_LISTENING",
            "manifest_sha256": "manifest",
            "results": [
                {
                    "id": "test",
                    "sha256": "audio",
                    "reference_sha256": "ref",
                    "completed": True,
                    "intelligibility_1_5": 3,
                    "naturalness_1_5": 1,
                }
            ],
        }

    def test_low_scores_are_accepted_but_substituted_data_is_rejected(self):
        self.assertEqual(
            validate_assessment(self.data, self.results, "manifest")[0]["naturalness_1_5"], 1
        )
        for key, value in [
            ("completed", "yes"),
            ("naturalness_1_5", True),
            ("intelligibility_1_5", 6),
            ("reference_sha256", "changed"),
            ("comment", {}),
            ("id", []),
        ]:
            data = deepcopy(self.data)
            data["results"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_assessment(data, self.results, "manifest")
        with self.assertRaises(ValueError):
            validate_assessment(self.data, self.results, "other experiment")

    def test_hash_verification_precedes_idempotent_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "test.wav").write_bytes(b"audio")
            (folder / "ref.wav").write_bytes(b"ref")
            result = self.results[0] | {
                "sha256": hashlib.sha256(b"audio").hexdigest(),
                "reference_sha256": hashlib.sha256(b"ref").hexdigest(),
            }
            canonical = json.dumps({"results": [result]}).encode()
            (folder / "results.json").write_bytes(canonical)
            data = deepcopy(self.data)
            data["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
            data["results"][0].update({k: result[k] for k in ["sha256", "reference_sha256"]})
            source = folder / "review.json"
            source.write_text(json.dumps(data))
            (folder / "ref.wav").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                import_assessment(source, folder)
            self.assertFalse(list(folder.glob("listening_import-*")))
            (folder / "ref.wav").write_bytes(b"ref")
            receipt = import_assessment(source, folder)
            self.assertEqual(import_assessment(source, folder), receipt)
            self.assertEqual((receipt / "listening.json").read_bytes(), source.read_bytes())
            summary = json.loads((receipt / "summary.json").read_text())
            self.assertEqual(summary["groups"]["phones"]["naturalness_1_5"], 1)
