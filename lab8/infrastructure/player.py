"""Native asynchronous Windows WAV playback; no microphone or external executable."""


class WindowsPlayer:
    def play(self, path: str) -> None:
        import winsound

        winsound.PlaySound(
            path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
        )

    def stop(self) -> None:
        import winsound

        winsound.PlaySound(None, 0)
