import tkinter as tk
from tkinter import ttk, messagebox
from core.i18n import t


class EditDialog(tk.Toplevel):
    """Dialog for adding or editing a dictionary entry."""

    def __init__(self, parent, mode="add", lemma="", wordform="",
                 frequency=1, morphology=""):
        super().__init__(parent)
        title = t("dlg_add_title") if mode == "add" else t("dlg_edit_title")
        self.title(title)
        self.resizable(False, False)
        self.grab_set()

        self.result = None

        self._lemma_var = tk.StringVar(value=lemma)
        self._wordform_var = tk.StringVar(value=wordform)
        self._frequency_var = tk.StringVar(value=str(frequency))
        self._morphology_text = None

        self._build(morphology)
        self._center(parent)

    def _build(self, morphology: str):
        pad = {"padx": 8, "pady": 4}
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=t("dlg_lemma")).grid(row=0, column=0, sticky=tk.W, **pad)
        ttk.Entry(frame, textvariable=self._lemma_var, width=30).grid(
            row=0, column=1, sticky=tk.EW, **pad
        )

        ttk.Label(frame, text=t("dlg_wordform")).grid(row=1, column=0, sticky=tk.W, **pad)
        ttk.Entry(frame, textvariable=self._wordform_var, width=30).grid(
            row=1, column=1, sticky=tk.EW, **pad
        )

        ttk.Label(frame, text=t("dlg_frequency")).grid(row=2, column=0, sticky=tk.W, **pad)
        ttk.Entry(frame, textvariable=self._frequency_var, width=10).grid(
            row=2, column=1, sticky=tk.W, **pad
        )

        ttk.Label(frame, text=t("dlg_morphology")).grid(row=3, column=0, sticky=tk.NW, **pad)
        self._morphology_text = tk.Text(frame, width=30, height=5, wrap=tk.WORD)
        self._morphology_text.grid(row=3, column=1, sticky=tk.EW, **pad)
        self._morphology_text.insert(tk.END, morphology)

        frame.columnconfigure(1, weight=1)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=12, pady=(0, 12))
        ttk.Button(btn_frame, text=t("dlg_ok"), width=10, command=self._on_ok).pack(
            side=tk.RIGHT, padx=4
        )
        ttk.Button(btn_frame, text=t("dlg_cancel"), width=10, command=self.destroy).pack(
            side=tk.RIGHT
        )

        self.bind("<Return>", lambda e: self._on_ok())
        self.bind("<Escape>", lambda e: self.destroy())

    def _on_ok(self):
        lemma = self._lemma_var.get().strip().lower()
        wordform = self._wordform_var.get().strip().lower()
        morphology = self._morphology_text.get("1.0", tk.END).strip()

        if not lemma:
            messagebox.showwarning(t("dlg_val_title"), t("dlg_val_lemma"), parent=self)
            return
        if not wordform:
            messagebox.showwarning(t("dlg_val_title"), t("dlg_val_wordform"), parent=self)
            return

        try:
            freq = int(self._frequency_var.get())
            if freq < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning(t("dlg_val_title"), t("dlg_val_freq"), parent=self)
            return

        self.result = {
            "lemma": lemma,
            "wordform": wordform,
            "frequency": freq,
            "morphology": morphology,
        }
        self.destroy()

    def _center(self, parent):
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
