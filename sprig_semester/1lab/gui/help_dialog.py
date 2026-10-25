import tkinter as tk
from tkinter import ttk
from core.i18n import t, help_text


class HelpDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title(t("help_title"))
        self.resizable(True, True)
        self.geometry("660x540")
        self._build()

    def _build(self):
        frame = ttk.Frame(self, padding=8)
        frame.pack(fill=tk.BOTH, expand=True)

        text = tk.Text(frame, wrap=tk.WORD, font=("Consolas", 10), relief=tk.FLAT)
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        text.insert(tk.END, help_text())
        text.configure(state=tk.DISABLED)

        ttk.Button(self, text=t("help_close"), command=self.destroy).pack(pady=(0, 8))
