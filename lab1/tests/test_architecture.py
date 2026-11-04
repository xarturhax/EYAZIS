"""Проверяемые ограничения импортов, предотвращающие возврат смешанных слоёв."""

import ast
import unittest
from pathlib import Path

from lab1.ir_system.config import PROJECT_ROOT


def imports(path: Path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


class ArchitectureTests(unittest.TestCase):
    def test_core_has_no_adapter_dependencies(self):
        rules = {
            "domain": (
                "lab1.ir_system.application",
                "lab1.ir_system.infrastructure",
                "lab1.ir_system.presentation",
                "sqlite3",
                "tkinter",
                "urllib.request",
                "matplotlib",
                "numpy",
                "lab1.ir_system.visualization",
            ),
            "application": (
                "lab1.ir_system.infrastructure",
                "lab1.ir_system.presentation",
                "sqlite3",
                "tkinter",
                "urllib.request",
                "matplotlib",
                "numpy",
                "lab1.ir_system.visualization",
            ),
        }
        for layer, forbidden in rules.items():
            for path in (PROJECT_ROOT / "ir_system" / layer).rglob("*.py"):
                for module in imports(path):
                    with self.subTest(path=path.name, module=module):
                        self.assertFalse(
                            any(
                                module == prefix or module.startswith(prefix + ".")
                                for prefix in forbidden
                            )
                        )

    def test_presentation_does_not_access_infrastructure(self):
        for path in (PROJECT_ROOT / "ir_system/presentation").rglob("*.py"):
            for module in imports(path):
                with self.subTest(path=path.name, module=module):
                    self.assertFalse(module.startswith("lab1.ir_system.infrastructure"))
                    self.assertNotIn(module, ("sqlite3", "urllib.request"))

    def test_main_only_delegates_startup(self):
        tree = ast.parse((PROJECT_ROOT / "main.py").read_text(encoding="utf-8"))
        self.assertFalse(
            any(isinstance(node, (ast.FunctionDef, ast.ClassDef)) for node in tree.body)
        )
        self.assertEqual(
            set(imports(PROJECT_ROOT / "main.py")),
            {"sys", "pathlib", "lab1.ir_system.presentation.cli"},
        )
