"""Real offline decoder integration; fixtures are synthetic and never played."""

import unittest

from lab9.logic import (
    DEFAULT_COMMANDS,
    ROOT,
    Action,
    RecognitionService,
    Router,
    VoskEngine,
    load_pcm,
    load_policy,
)


class RealRecognitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = RecognitionService(VoskEngine())

    def test_french_synthetic_command(self):
        pcm, _ = load_pcm(ROOT / "reports/demo/audio/tom_stop.wav")
        result = self.service.run(pcm, 16000, "fr")
        router = Router(load_policy(DEFAULT_COMMANDS))
        actions = [router.resolve(u, "fr", 10).action for u in result.utterances]
        self.assertEqual(actions, [Action.STOP])
        self.assertTrue(all(w.start <= w.end for u in result.utterances for w in u.words))

    def test_french_noncommand(self):
        pcm, _ = load_pcm(ROOT / "reports/demo/audio/tom_negative2.wav")
        result = self.service.run(pcm, 16000, "fr")
        self.assertTrue(result.utterances)
        router = Router(load_policy(DEFAULT_COMMANDS))
        self.assertTrue(all(router.resolve(u, "fr", 10).action is None for u in result.utterances))

    def test_english_model_selected(self):
        result = self.service.run(bytes(32000), 16000, "en")
        self.assertEqual(result.versions["model"], "vosk-model-small-en-us-0.15")
        self.assertEqual(result.utterances, ())
