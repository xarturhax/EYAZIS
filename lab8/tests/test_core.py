import json
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from lab8.application.service import SpeechService
from lab8.domain.models import Audio, CancelledError, Settings, normalize, split_text
from lab8.infrastructure.export import export


class FakeEngine:
    def __init__(self):
        self.calls = []
        self.ready = False

    def prepare(self, voice):
        self.ready = True
        return {"engine": "test"}

    def synthesize(self, text, settings, cancelled):
        self.calls.append(text)
        t = np.arange(2205) / 22050
        return Audio(
            (0.3 * settings.volume * np.sin(2 * np.pi * 200 * t)).astype(np.float32), 22050
        )


class CoreTests(unittest.TestCase):
    def test_settings_reject_nonfinite_and_invalid_ranges(self):
        for kwargs in (
            {"voice": "en"},
            {"speed": 0},
            {"speed": float("nan")},
            {"volume": -1},
            {"volume": float("inf")},
        ):
            with self.assertRaises(ValueError):
                Settings(**kwargs)

    def test_normalization_preserves_accents_apostrophes_and_paragraphs(self):
        self.assertEqual(
            normalize("  L’e\u0301criture.\r\n\r\nUn héros.  "), "L’écriture.\n\nUn héros."
        )

    def test_invalid_text_is_rejected(self):
        for text in ("", "123 !!!", "x" * 5001, "bonjour\x00"):
            with self.assertRaises(ValueError):
                normalize(text)

    def test_chunks_keep_every_word_and_boundaries(self):
        text = normalize(("La littérature éclaire notre expérience. " * 60).strip())
        chunks = split_text(text)
        self.assertTrue(all(0 < len(p) <= 300 for p in chunks))
        self.assertEqual(" ".join(" ".join(chunks).split()), " ".join(text.split()))

    def test_unicode_whitespace_is_supported(self):
        text = normalize("\u00a0".join(["littérature"] * 50))
        self.assertEqual(" ".join(" ".join(split_text(text)).split()), " ".join(text.split()))

    def test_real_wav_header_and_no_overwrite(self):
        engine = FakeEngine()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "speech.wav"
            result = SpeechService(engine).render("Bonjour.", Settings(), path)
            with wave.open(str(path), "rb") as wav:
                self.assertEqual(
                    (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()), (1, 2, 22050)
                )
                self.assertEqual(wav.getnframes(), 2205)
            self.assertAlmostEqual(result.duration, 0.1)
            with self.assertRaises(ValueError):
                SpeechService(engine).render("Bonjour.", Settings(), Path(directory) / "bad.txt")
            protected = Path(directory) / "original.txt"
            protected.write_text("Keep original source", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                export(result, Path(directory) / "original.wav")
            self.assertEqual(protected.read_text(encoding="utf-8"), "Keep original source")
            with self.assertRaises(FileExistsError):
                SpeechService(engine).render("Bonjour.", Settings(), path)

    def test_cancellation_before_loading_creates_no_file(self):
        engine = FakeEngine()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "speech.wav"
            with self.assertRaises(CancelledError):
                SpeechService(engine).render("Bonjour.", Settings(), path, cancelled=lambda: True)
            self.assertFalse(engine.ready)
            self.assertFalse(path.exists())

    def test_cancellation_after_synthesis_creates_no_partial_wav(self):
        engine = FakeEngine()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "speech.wav"
            with self.assertRaises(CancelledError):
                SpeechService(engine).render(
                    "Bonjour.", Settings(), path, cancelled=lambda: bool(engine.calls)
                )
            self.assertFalse(path.exists())

    def test_invalid_engine_audio_is_rejected(self):
        engine = FakeEngine()
        engine.synthesize = lambda *args: Audio(np.array([np.nan], dtype=np.float32), 22050)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                SpeechService(engine).render("Bonjour.", Settings(), Path(directory) / "bad.wav")

    def test_export_is_portable_and_escapes_text(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            result = SpeechService(FakeEngine()).render(
                "Un <script>héros</script>.", Settings(), base / "source.wav"
            )
            saved = export(result, base / "export" / "français.wav")
            self.assertEqual(saved.wav_path.read_bytes(), result.wav_path.read_bytes())
            html = saved.wav_path.with_suffix(".html").read_text(encoding="utf-8")
            self.assertNotIn("<script>héros</script>", html)
            self.assertIn("&lt;script&gt;", html)
            self.assertIn('src="fran%C3%A7ais.wav"', html)
            meta = json.loads(saved.wav_path.with_suffix(".json").read_text(encoding="utf-8"))
            self.assertEqual(meta["auditory_evaluation"], "PENDING_HUMAN_LISTENING")

    def test_zero_volume_is_valid_silence(self):
        with tempfile.TemporaryDirectory() as directory:
            result = SpeechService(FakeEngine()).render(
                "Bonjour.", Settings(volume=0), Path(directory) / "silence.wav"
            )
            self.assertEqual(result.peak, 0)
            self.assertEqual(result.rms, 0)

    def test_domain_and_application_do_not_import_infrastructure(self):
        import ast

        for folder in ("domain", "application"):
            for path in (Path(__file__).resolve().parents[1] / folder).glob("*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        self.assertFalse((node.module or "").startswith("lab8.infrastructure"))
