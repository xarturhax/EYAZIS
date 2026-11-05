import unittest
from dataclasses import replace

from lab9.logic import (
    DEFAULT_COMMANDS,
    Action,
    Command,
    Policy,
    Router,
    Utterance,
    Word,
    load_policy,
    normalize,
    word_error_rate,
)


def phrase(text, confidence=0.95, final=True):
    return Utterance(
        text, tuple(Word(w, confidence, i, i + 0.5) for i, w in enumerate(text.split())), final
    )


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy(DEFAULT_COMMANDS)
        self.router = Router(self.policy)

    def test_accents_case_punctuation(self):
        self.assertEqual(normalize("LECTEUR précédent!"), "lecteur precedent")
        self.assertEqual(
            self.router.resolve(phrase("LECTEUR PRÉCÉDENT!"), "fr", 0).action, Action.PREVIOUS
        )

    def test_whole_phrase_only(self):
        for text in ("commence", "lecteur commence le récit", "le lecteur commence"):
            with self.subTest(text=text):
                self.assertEqual(self.router.resolve(phrase(text), "fr", 0).status, "UNKNOWN")

    def test_partial_does_not_execute(self):
        self.assertEqual(
            self.router.resolve(phrase("lecteur commence", final=False), "fr", 0).status, "PARTIAL"
        )

    def test_confidence_missing_low_or_incomplete(self):
        cases = [
            Utterance("lecteur commence"),
            phrase("lecteur commence", 0.6),
            Utterance("lecteur commence", (Word("commence", 1, 0, 1),)),
            Utterance("lecteur commence", (Word("lecteur", 0.5, 0, 1), Word("commence", 1, 1, 2))),
        ]
        for utterance in cases:
            with self.subTest(utterance=utterance):
                self.assertEqual(self.router.resolve(utterance, "fr", 0).status, "LOW_CONFIDENCE")

    def test_disabled(self):
        policy = Policy((Command("fr", "lecteur commence", Action.READ, False),))
        self.assertEqual(
            Router(policy).resolve(phrase("lecteur commence"), "fr", 0).status, "DISABLED"
        )

    def test_cooldown_and_stop_exemption(self):
        self.assertEqual(self.router.resolve(phrase("lecteur suivant"), "fr", 0).status, "ACCEPTED")
        self.assertEqual(
            self.router.resolve(phrase("lecteur suivant"), "fr", 0.5).status, "COOLDOWN"
        )
        self.assertEqual(self.router.resolve(phrase("lecteur suivant"), "fr", 2).status, "ACCEPTED")
        for now in (2, 2.1):
            self.assertEqual(
                self.router.resolve(phrase("lecteur stop"), "fr", now).action, Action.STOP
            )

    def test_language_selection(self):
        self.assertEqual(self.router.resolve(phrase("reader read"), "fr", 0).status, "UNKNOWN")
        self.assertEqual(self.router.resolve(phrase("reader read"), "en", 0).action, Action.READ)
        with self.assertRaises(ValueError):
            self.router.resolve(phrase("reader read"), "de", 0)

    def test_policy_validation(self):
        invalid = [
            lambda: Command("fr", "commence maintenant", Action.READ),
            lambda: Command("de", "reader read", Action.READ),
            lambda: replace(self.policy, threshold=float("nan")),
            lambda: replace(self.policy, commands=self.policy.commands * 2),
            lambda: Policy(()),
        ]
        for factory in invalid:
            with self.assertRaises(ValueError):
                factory()

    def test_word_validation(self):
        for args in (("x", 2, 0, 1), ("x", 1, 2, 1), ("x", 1, 0, float("inf"))):
            with self.assertRaises(ValueError):
                Word(*args)

    def test_wer(self):
        self.assertEqual(word_error_rate("le livre rouge", "le roman rouge")["wer"], 1 / 3)
        self.assertEqual(word_error_rate("répète", "repete")["wer"], 0)
        self.assertEqual(word_error_rate("", "")["wer"], 0)
