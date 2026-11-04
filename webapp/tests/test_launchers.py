"""Individual labs delegate default startup to their web workspace, without models or devices."""

import importlib
import unittest
from unittest.mock import patch


class LauncherTests(unittest.TestCase):
    def test_all_default_launchers_open_the_matching_web_workspace(self):
        for module, entry, lab in [
            ("lab1.ir_system.presentation.cli", "run", 1),
            ("lab2.presentation.cli", "run", 2),
            ("lab3.presentation.cli", "main", 3),
            ("lab4.presentation.cli", "main", 4),
            ("lab5_7.presentation.cli", "main", 5),
            ("lab8.presentation.cli", "main", 8),
            ("lab9.presentation.cli", "main", 9),
        ]:
            with (
                self.subTest(lab=lab),
                patch("sys.argv", ["lab"]),
                patch("webapp.__main__.main") as launch,
            ):
                function = getattr(importlib.import_module(module), entry)
                self.assertEqual(function(), 0)
                launch.assert_called_once_with(["--lab", str(lab)])

    def test_existing_server_opens_the_selected_lab_without_starting_another_server(
        self,
    ):
        import io

        from webapp.__main__ import main

        response = io.BytesIO(b'{"app":"eyazis-web"}')
        with (
            patch("urllib.request.urlopen", return_value=response),
            patch("webbrowser.open") as browser,
            patch("uvicorn.Server") as server,
            patch("sys.stdout", io.StringIO()),
        ):
            main(["--lab", "7"])
            browser.assert_called_once_with("http://127.0.0.1:8765/#lab-7")
            server.assert_not_called()
