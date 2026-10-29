import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf

from lab5_7.application.annotation import propose
from lab5_7.domain.audio import Audio
from lab5_7.domain.segmentation import activity
from lab5_7.tools.import_review import main, validate_review


class DetectionTests(unittest.TestCase):
    def test_separated_bursts_and_small_internal_gap(self):
        rate = 4000
        x = np.zeros(rate * 4)
        t = np.arange(rate) / rate
        x[rate : 2 * rate] = 0.03 * np.sin(2 * np.pi * 100 * t)
        x[round(1.4 * rate) : round(1.45 * rate)] = 0
        x[round(2.6 * rate) : round(3.6 * rate)] = 0.03 * np.sin(2 * np.pi * 100 * t)
        regions = activity(Audio(x, rate))
        self.assertEqual(len(regions), 2)
        self.assertAlmostEqual(regions[0].start, 1, delta=0.02)
        self.assertAlmostEqual(regions[0].end, 2, delta=0.02)

    def test_silence_does_not_create_regions(self):
        self.assertEqual(activity(Audio(np.zeros(12000), 4000)), [])

    def test_detected_order_is_not_review_status(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "data/raw").mkdir(parents=True)
            rate = 4000
            x = np.zeros(rate * 5)
            x[rate : 2 * rate] = 0.03 * np.sin(2 * np.pi * 100 * np.arange(rate) / rate)
            x[3 * rate : 4 * rate] = 0.03 * np.sin(2 * np.pi * 120 * np.arange(rate) / rate)
            sf.write(root / "data/raw/vowels.wav", x, rate)
            rows = [
                dict(
                    id="ph_a",
                    file="vowels.wav",
                    kind="phone",
                    start="",
                    end="",
                    reviewed="",
                    note="",
                )
            ]
            with (
                patch("lab5_7.application.annotation.LAYOUTS", {"vowels": ["a", "o"]}),
                patch("lab5_7.application.annotation.segments", return_value=rows),
            ):
                proposed, _ = propose(root)
                self.assertFalse(proposed[0]["reviewed"])
                self.assertEqual(rows[0]["start"], "")
            with patch("lab5_7.application.annotation.LAYOUTS", {"vowels": ["a"]}):
                with self.assertRaisesRegex(ValueError, "expected 1"):
                    propose(root)

    def test_asr_timings_remain_unreviewed_and_are_hash_bound(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "data/raw").mkdir(parents=True)
            (root / "vendor").mkdir()
            rate = 4000
            x = np.zeros(rate * 7)
            for start in (1, 3, 5):
                x[start * rate : (start + 1) * rate] = 0.03 * np.sin(
                    2 * np.pi * 100 * np.arange(rate) / rate
                )
            source = root / "data/raw/student.wav"
            sf.write(source, x, rate)
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            cache = {
                "student": {
                    "eligible": True,
                    "source_sha256": digest,
                    "words": [
                        {"start": 1.1, "end": 1.3},
                        {"start": 1.4, "end": 1.6},
                        {"start": 1.7, "end": 1.9},
                    ],
                }
            }
            cache_file = root / "vendor/word_alignment.json"
            cache_file.write_text(json.dumps(cache))
            rows = [
                dict(
                    id="student_student",
                    file="student.wav",
                    kind="word",
                    start="",
                    end="",
                    reviewed="",
                    note="",
                )
            ]
            with (
                patch("lab5_7.application.annotation.LAYOUTS", {"student": ["phrase"] * 3}),
                patch("lab5_7.application.annotation.segments", return_value=rows),
            ):
                proposed, _ = propose(root)
                self.assertAlmostEqual(proposed[0]["start"], 1.085)
                self.assertFalse(proposed[0]["reviewed"])
                cache["student"]["source_sha256"] = "changed"
                cache_file.write_text(json.dumps(cache))
                with self.assertRaisesRegex(ValueError, "hash changed"):
                    propose(root)


class ReviewValidationTests(unittest.TestCase):
    def setUp(self):
        self.candidates = [
            {
                "id": "ph_a",
                "file": "vowels.wav",
                "source_sha256": "digest",
                "context_start": 1.0,
                "context_end": 3.0,
            }
        ]
        self.data = {
            "schema": 1,
            "assessment_kind": "BOUNDARY_AND_LABEL_REVIEW",
            "manifest_sha256": "manifest",
            "segments": [
                {
                    "id": "ph_a",
                    "file": "vowels.wav",
                    "source_sha256": "digest",
                    "start": 1.5,
                    "end": 2.5,
                    "reviewed": False,
                }
            ],
        }

    def test_explicit_unreviewed_is_retained(self):
        rows = validate_review(self.data, self.candidates, "manifest")
        self.assertFalse(rows[0]["reviewed"])

    def test_invalid_numeric_boundaries(self):
        for value in (float("nan"), float("inf"), True, "1.5", 0.5, 2.6):
            data = deepcopy(self.data)
            data["segments"][0]["start"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_review(data, self.candidates, "manifest")

    def test_substituted_file_or_digest_rejected(self):
        for key, value in (
            ("file", "../other.wav"),
            ("source_sha256", "changed"),
            ("id", "unknown"),
            ("reviewed", "yes"),
        ):
            data = deepcopy(self.data)
            data["segments"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_review(data, self.candidates, "manifest")

    def test_wrong_manifest_rejected(self):
        with self.assertRaises(ValueError):
            validate_review(self.data, self.candidates, "different")

    def test_duplicate_rejected(self):
        candidates = self.candidates + [self.candidates[0] | {"id": "ph_o"}]
        data = deepcopy(self.data)
        data["segments"] *= 2
        with self.assertRaises(ValueError):
            validate_review(data, candidates, "manifest")

    def test_import_requires_confirmation_and_retains_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data_dir = root / "data"
            data_dir.mkdir()
            manifest_dir = root / "manifest"
            manifest_dir.mkdir()
            source = data_dir / "vowels.wav"
            source.write_bytes(b"original fixture bytes")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            candidates = [self.candidates[0] | {"source_sha256": digest}]
            canonical = json.dumps(candidates).encode()
            manifest = hashlib.sha256(canonical).hexdigest()
            (manifest_dir / "candidates.json").write_bytes(canonical)
            (manifest_dir / "manifest.json").write_text(
                json.dumps({"manifest_sha256": manifest, "source_hashes": {"vowels.wav": digest}})
            )
            review = deepcopy(self.data)
            review["manifest_sha256"] = manifest
            review["segments"][0]["source_sha256"] = digest
            inp = root / "review.json"
            inp.write_text(json.dumps(review))
            target = data_dir / "segments.csv"
            target.write_bytes(b"original CSV")
            row = dict(
                id="ph_a", file="vowels.wav", start="", end="", kind="phone", reviewed="", note=""
            )
            with (
                patch("lab5_7.tools.import_review.ROOT", root),
                patch("lab5_7.tools.import_review.segment_path", return_value=source),
                patch("lab5_7.tools.import_review.segments", return_value=[row]),
                patch("sys.argv", ["import_review", str(inp), "--manifest-dir", str(manifest_dir)]),
            ):
                with self.assertRaisesRegex(ValueError, "No intervals"):
                    main()
                self.assertEqual(target.read_bytes(), b"original CSV")
                review["segments"][0]["reviewed"] = True
                inp.write_text(json.dumps(review))
                main()
                self.assertIn(",yes,", target.read_text(encoding="utf-8-sig"))
                snapshots = list(
                    (root / "reports/local").glob("annotation_import-*/segments_before.csv")
                )
                self.assertEqual(snapshots[0].read_bytes(), b"original CSV")
