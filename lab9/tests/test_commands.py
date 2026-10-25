import unittest
from dataclasses import replace

from lab9.bootstrap import DEFAULT_COMMANDS
from lab9.domain.commands import (
    Action,
    Command,
    Policy,
    Router,
    Utterance,
    Word,
    normalize,
    word_error_rate,
)
from lab9.domain.reader import Reader
from lab9.infrastructure.config import load_policy


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


class ReaderTests(unittest.TestCase):
    def test_navigation_bounds_and_read(self):
        reader = Reader()
        self.assertFalse(reader.apply(Action.READ).speak)
        reader.set_text("Premier\n\nDeuxième")
        self.assertTrue(reader.apply(Action.READ).speak)
        for _ in range(3):
            self.assertFalse(reader.apply(Action.NEXT).speak)
        self.assertEqual(reader.current, "Deuxième")
        self.assertTrue(reader.apply(Action.REPEAT).speak)
        for _ in range(3):
            reader.apply(Action.PREVIOUS)
        self.assertEqual(reader.position, 0)

    def test_text_change_and_limit(self):
        reader = Reader()
        reader.set_text("A\n\nB")
        reader.apply(Action.NEXT)
        reader.set_text("C")
        self.assertEqual(reader.position, 0)
        with self.assertRaises(ValueError):
            reader.set_text("x" * 5001)
        self.assertEqual(reader.current, "C")

    def test_speed_limits(self):
        reader = Reader()
        for _ in range(30):
            reader.apply(Action.FASTER)
        self.assertEqual(reader.speed, 2)
        for _ in range(30):
            reader.apply(Action.SLOWER)
        self.assertEqual(reader.speed, 0.5)
        self.assertFalse(reader.apply(Action.STOP).speak)
