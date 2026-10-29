import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from lab5_7.tools.import_phonetics_listening import import_observations, validate_observations


class PhoneticsListeningTests(unittest.TestCase):
    def setUp(self):
        self.results = [
            {
                "id": "ph_a",
                "loop_sha256": "loop",
                "kind": "vowel_period_estimate",
                "loop_wav": "loop.wav",
                "source": {"sha256": "source"},
                "confirmed_segment": {"file": "vowels.wav"},
            }
        ]
        self.data = {
            "schema": 1,
            "assessment_kind": "LAB5_PHONETICS_LISTENING",
            "manifest_sha256": "manifest",
            "results": [
                {
                    "id": "ph_a",
                    "loop_sha256": "loop",
                    "completed": True,
                    "loop_resemblance": "similar",
                    "comment": "",
                }
            ],
        }

    def test_explicit_observations_and_pending_status(self):
        self.assertEqual(
            validate_observations(self.data, self.results, "manifest")[0]["loop_resemblance"],
            "similar",
        )
        data = deepcopy(self.data)
        data["results"][0].update(completed=False, loop_resemblance="")
        self.assertFalse(validate_observations(data, self.results, "manifest")[0]["completed"])

    def test_invalid_schema_hashes_and_values(self):
        for key, value in [
            ("id", "ph_s"),
            ("id", []),
            ("loop_sha256", "changed"),
            ("completed", "yes"),
            ("loop_resemblance", ""),
            ("loop_resemblance", "guess"),
            ("comment", []),
        ]:
            data = deepcopy(self.data)
            data["results"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_observations(data, self.results, "manifest")
        with self.assertRaises(ValueError):
            validate_observations(self.data, self.results, "another manifest")
        with self.assertRaises(ValueError):
            validate_observations(
                self.data | {"results": self.data["results"] * 2}, self.results * 2, "manifest"
            )

    def test_audio_checks_precede_idempotent_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "source.wav"
            source.write_bytes(b"source recording")
            loop = folder / "loop.wav"
            loop.write_bytes(b"loop recording")
            result = deepcopy(self.results[0])
            result["source"]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
            result["loop_sha256"] = hashlib.sha256(loop.read_bytes()).hexdigest()
            canonical = json.dumps({"results": [result]}).encode()
            (folder / "results.json").write_bytes(canonical)
            data = deepcopy(self.data)
            data["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
            data["results"][0]["loop_sha256"] = result["loop_sha256"]
            incoming = folder / "review.json"
            incoming.write_text(json.dumps(data))
            with patch("lab5_7.tools.import_phonetics_listening.segment_path", return_value=source):
                source.write_bytes(b"changed")
                with self.assertRaises(ValueError):
                    import_observations(incoming, folder)
                self.assertFalse(list(folder.glob("listening_import-*")))
                source.write_bytes(b"source recording")
                receipt = import_observations(incoming, folder)
                self.assertEqual(import_observations(incoming, folder), receipt)
                self.assertEqual((receipt / "listening.json").read_bytes(), incoming.read_bytes())
                summary = json.loads((receipt / "summary.json").read_text())
                self.assertEqual(summary["groups"]["vowel_period_estimate"], {"similar": 1})
