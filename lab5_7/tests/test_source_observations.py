import unittest
from copy import deepcopy

from lab5_7.tools.import_source_observations import validate_source_observations


class SourceObservationTests(unittest.TestCase):
    def setUp(self):
        self.results = [
            {
                "id": "ref1",
                "group": "reference",
                "count_groups": True,
                "options": [["statement", "Statement"], ["unclear", "Unclear"]],
                "clips": [{"sha256": "clip"}],
            }
        ]
        self.data = {
            "schema": 1,
            "assessment_kind": "LAB6_SOURCE_OBSERVATIONS",
            "manifest_sha256": "manifest",
            "results": [
                {
                    "id": "ref1",
                    "clip_hashes": ["clip"],
                    "completed": True,
                    "labels_match": "yes",
                    "comment": "Neutral.",
                    "heard_label": "statement",
                    "accent_groups": "unclear",
                    "syntagms": "1",
                }
            ],
        }

    def test_uncertain_accent_count_remains_uncertain(self):
        rows = validate_source_observations(self.data, self.results, "manifest")
        self.assertEqual(rows[0]["accent_groups"], "unclear")
        self.assertEqual(rows[0]["syntagms"], "1")

    def test_invalid_perception_and_missing_counts_are_rejected(self):
        for key, value in [
            ("heard_label", "joy"),
            ("heard_label", ""),
            ("accent_groups", ""),
            ("accent_groups", 1),
            ("syntagms", "0"),
        ]:
            data = deepcopy(self.data)
            data["results"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_source_observations(data, self.results, "manifest")

    def test_intonation_does_not_require_group_counts(self):
        results = [self.results[0] | {"count_groups": False}]
        data = deepcopy(self.data)
        data["results"][0].update(accent_groups="", syntagms="")
        self.assertEqual(len(validate_source_observations(data, results, "manifest")), 1)

    def test_wrong_observation_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_source_observations(
                self.data | {"assessment_kind": "LAB5_COMPARISON_LISTENING"},
                self.results,
                "manifest",
            )
