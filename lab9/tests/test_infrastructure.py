import json
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

import numpy as np
import soundfile as sf

from lab9.application.recognition import RecognitionService
from lab9.bootstrap import DEFAULT_COMMANDS
from lab9.infrastructure.audio import load_pcm
from lab9.infrastructure.config import load_policy, save_policy
from lab9.infrastructure.export import export_journal
from lab9.infrastructure.recognizer import CancelledError, VoskEngine, parse_result


class InfrastructureTests(unittest.TestCase):
    def test_config_roundtrip(self):
        policy = load_policy(DEFAULT_COMMANDS)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "commands.json"
            save_policy(path, policy)
            self.assertEqual(load_policy(path), policy)

    def test_invalid_config(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.json"
            for payload in ("{}", "[]", '{"schema":2}', '{"schema":1, "commands":null}'):
                path.write_text(payload, encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_policy(path)

    def test_resample_selects_first_channel(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.wav"
            sf.write(path, np.column_stack((np.zeros(4410), np.ones(4410) * 0.5)), 44100)
            pcm, metadata = load_pcm(path)
            self.assertEqual(len(pcm), 3200)
            self.assertFalse(any(pcm))
            self.assertEqual(metadata["original_channels"], 2)

    def test_bad_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "invalid.wav"
            path.write_text("invalid")
            with self.assertRaises((ValueError, sf.LibsndfileError)):
                load_pcm(path)

    def test_parse_final_partial(self):
        value = parse_result(
            json.dumps(
                {
                    "text": "lecteur commence",
                    "result": [
                        {"word": "lecteur", "conf": 0.9, "start": 0, "end": 0.5},
                        {"word": "commence", "conf": 1, "start": 0.5, "end": 1},
                    ],
                }
            )
        )
        self.assertEqual(len(value.words), 2)
        self.assertAlmostEqual(value.confidence, 0.95)
        self.assertFalse(parse_result('{"partial":"lecteur"}', False).final)

    def test_pcm_validation_before_model_load(self):
        service = RecognitionService(VoskEngine())
        for pcm, rate in ((b"", 16000), (b"x", 16000), (b"xx", 100)):
            with self.assertRaises(ValueError):
                service.run(pcm, rate, "fr")

    def test_decode_cancelled_does_not_flush(self):
        decoder = type(
            "Decoder", (), {"FinalResult": lambda _: self.fail("Cancelled input flushed")}
        )()
        engine = VoskEngine()
        with patch.object(engine, "prepare"), patch.object(engine, "decoder", return_value=decoder):
            with self.assertRaises(CancelledError):
                engine.decode(b"00", 16000, "fr", lambda: True)

    def test_html_and_csv_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            export_journal([{"text": "=1+1", "message": "<script>"}], Path(folder))
            self.assertIn("'=1+1", (Path(folder) / "events.csv").read_text(encoding="utf-8-sig"))
            self.assertIn(
                "&lt;script&gt;", (Path(folder) / "report.html").read_text(encoding="utf-8")
            )
            self.assertEqual(
                json.loads((Path(folder) / "events.json").read_text(encoding="utf-8"))[0]["text"],
                "=1+1",
            )

    def test_mock_microphone_stops_without_final_flush(self):
        import sounddevice as sd

        cancelled = Event()
        emitted = []

        class Decoder:
            def AcceptWaveform(self, packet):
                cancelled.set()
                return False

            def PartialResult(self):
                return '{"partial":"lecteur"}'

            def FinalResult(self):
                raise AssertionError("Stopped microphone must not execute last partial")

        class Stream:
            def __init__(self, **kwargs):
                self.callback = kwargs["callback"]

            def __enter__(self):
                self.callback(b"00" * 1600, 1600, None, None)
                return self

            def __exit__(self, *args):
                pass

        engine = VoskEngine()
        with (
            patch.object(engine, "prepare"),
            patch.object(engine, "decoder", return_value=Decoder()),
            patch.object(sd, "query_devices", return_value={"default_samplerate": 16000}),
            patch.object(sd, "RawInputStream", Stream),
        ):
            engine.listen("fr", None, emitted.append, lambda _: None, cancelled.is_set, Event())
        self.assertTrue(all(not u.final for u in emitted))
