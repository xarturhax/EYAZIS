import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from lab5_7.tools.import_comparisons import import_comparisons, validate_comparisons


class ComparisonImportTests(unittest.TestCase):
    def setUp(self):
        self.results = [
            {
                "id": "consonant_context_b",
                "group": "consonant_context",
                "clips": [
                    {
                        "wav": "clip.wav",
                        "sha256": "clip",
                        "source": {"file": "source.wav", "source_sha256": "source"},
                    }
                ],
            }
        ]
        self.data = {
            "schema": 1,
            "assessment_kind": "LAB5_COMPARISON_LISTENING",
            "manifest_sha256": "manifest",
            "results": [
                {
                    "id": "consonant_context_b",
                    "clip_hashes": ["clip"],
                    "completed": True,
                    "labels_match": "no",
                    "comment": "The loop sounds like humming.",
                }
            ],
        }

    def test_negative_answer_is_not_rewritten_as_label_approval(self):
        rows = validate_comparisons(self.data, self.results, "manifest")
        self.assertEqual(rows[0]["labels_match"], "no")
        self.assertEqual(rows[0]["comment"], "The loop sounds like humming.")

    def test_invalid_bindings_and_incomplete_observations(self):
        for key, value in [
            ("clip_hashes", ["different"]),
            ("completed", "yes"),
            ("labels_match", "guess"),
            ("comment", ""),
            ("id", []),
        ]:
            data = deepcopy(self.data)
            data["results"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_comparisons(data, self.results, "manifest")
        with self.assertRaises(ValueError):
            validate_comparisons(self.data, self.results, "other manifest")
        with self.assertRaises(ValueError):
            validate_comparisons(
                self.data | {"results": self.data["results"] * 2}, self.results * 2, "manifest"
            )

    def test_changed_wav_is_rejected_before_archiving(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "source.wav"
            source.write_bytes(b"source")
            wav = folder / "clip.wav"
            wav.write_bytes(b"clip")
            results = deepcopy(self.results)
            clip = results[0]["clips"][0]
            clip["sha256"] = hashlib.sha256(b"clip").hexdigest()
            clip["source"]["source_sha256"] = hashlib.sha256(b"source").hexdigest()
            canonical = json.dumps({"results": results}).encode()
            (folder / "results.json").write_bytes(canonical)
            data = deepcopy(self.data)
            data["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
            data["results"][0]["clip_hashes"] = [clip["sha256"]]
            incoming = folder / "incoming.json"
            incoming.write_text(json.dumps(data))
            with patch("lab5_7.tools.import_comparisons.segment_path", return_value=source):
                wav.write_bytes(b"changed")
                with self.assertRaises(ValueError):
                    import_comparisons(incoming, folder)
                self.assertFalse(list(folder.glob("listening_import-*")))
                wav.write_bytes(b"clip")
                receipt = import_comparisons(incoming, folder)
                self.assertEqual(import_comparisons(incoming, folder), receipt)
                self.assertEqual((receipt / "listening.json").read_bytes(), incoming.read_bytes())
                summary = json.loads((receipt / "summary.json").read_text())
                self.assertEqual(summary["negative_answers_preserved"], ["consonant_context_b"])
