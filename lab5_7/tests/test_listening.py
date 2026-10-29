import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from lab5_7.tools.import_listening import import_listening, summarize, validate_listening


class ListeningTests(unittest.TestCase):
    def setUp(self):
        self.results = [
            {
                "id": "prosody/test",
                "sha256": "hash",
                "category": "prosody",
                "title": "Fixture",
                "method": "psola",
                "stage": 1,
                "focus": 0,
                "question_intended": True,
                "wav": "test.wav",
            },
            {
                "id": "permutations/test",
                "sha256": "hash",
                "category": "permutation",
                "title": "Pending",
                "wav": "test.wav",
            },
        ]
        self.data = {
            "schema": 1,
            "assessment_kind": "LAB6_EXPERIMENT_LISTENING",
            "manifest_sha256": "manifest",
            "results": [
                {
                    "id": "prosody/test",
                    "sha256": "hash",
                    "completed": True,
                    "intelligibility_1_5": 5,
                    "naturalness_1_5": 2,
                    "heard_focus": "student",
                    "heard_intonation": "statement",
                    "comment": "Question was not perceived",
                },
                {"id": "permutations/test", "sha256": "hash", "completed": False},
            ],
        }

    def test_partial_assessment_counts_only_explicit_confirmations(self):
        rows = validate_listening(self.data, self.results, "manifest")
        summary = summarize(rows, self.results)
        self.assertEqual(summary["completed_by_category"], {"prosody": 1, "permutation": 0})
        self.assertEqual(summary["pending"], 1)
        self.assertEqual(summary["groups"]["psola"]["intonation_matches_intent"], 0)
        self.assertEqual(summary["groups"]["psola"]["focus_matches_intent"], 1)

    def test_wrong_manifest_and_duplicate_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_listening(self.data, self.results, "changed")
        data = deepcopy(self.data)
        data["results"][1] = data["results"][0]
        with self.assertRaises(ValueError):
            validate_listening(data, self.results, "manifest")

    def test_invalid_completed_ratings_are_rejected(self):
        for key, value in [
            ("sha256", "changed"),
            ("completed", "yes"),
            ("intelligibility_1_5", True),
            ("naturalness_1_5", 5.0),
            ("naturalness_1_5", 0),
            ("naturalness_1_5", None),
            ("heard_focus", "sasha"),
            ("heard_intonation", ""),
            ("comment", {}),
        ]:
            data = deepcopy(self.data)
            data["results"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_listening(data, self.results, "manifest")

    def test_unconfirmed_values_are_preserved_without_becoming_assessed(self):
        data = deepcopy(self.data)
        data["results"][0]["completed"] = False
        rows = validate_listening(data, self.results, "manifest")
        self.assertEqual(summarize(rows, self.results)["completed"], 0)
        self.assertEqual(rows[0]["comment"], "Question was not perceived")

    def test_audio_verification_and_idempotent_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            audio = folder / "test.wav"
            audio.write_bytes(b"fixture audio")
            digest = hashlib.sha256(audio.read_bytes()).hexdigest()
            results = [r | {"sha256": digest} for r in self.results]
            canonical = json.dumps({"results": results}).encode()
            (folder / "results.json").write_bytes(canonical)
            data = deepcopy(self.data)
            data["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
            for row in data["results"]:
                row["sha256"] = digest
            source = folder / "incoming.json"
            source.write_text(json.dumps(data), encoding="utf-8")
            audio.write_bytes(b"changed audio")
            with self.assertRaisesRegex(ValueError, "audio changed"):
                import_listening(source, folder)
            self.assertFalse(list(folder.glob("listening_import-*")))
            audio.write_bytes(b"fixture audio")
            receipt = import_listening(source, folder)
            self.assertEqual((receipt / "listening.json").read_bytes(), source.read_bytes())
            self.assertEqual(import_listening(source, folder), receipt)
            self.assertEqual((folder / "results.json").read_bytes(), canonical)
            self.assertEqual(json.loads((receipt / "summary.json").read_text())["completed"], 1)
