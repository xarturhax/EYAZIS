import unittest
from unittest.mock import patch

from lab8.infrastructure.player import WindowsPlayer


class PlayerTests(unittest.TestCase):
    def test_native_async_playback_and_stop_are_routed_without_actual_audio(self):
        import winsound

        with patch("winsound.PlaySound") as sound:
            player = WindowsPlayer()
            player.play("speech.wav")
            self.assertEqual(sound.call_args.args[0], "speech.wav")
            self.assertTrue(sound.call_args.args[1] & winsound.SND_ASYNC)
            player.stop()
            self.assertEqual(sound.call_args.args, (None, 0))
