import tkinter as tk
from tkinter import ttk
from core.i18n import t

COLUMNS = ("lemma", "wordform", "frequency", "morphology")
COL_WIDTHS = (120, 120, 80, 300)


class DictionaryView(ttk.Frame):
    """Treeview widget displaying dictionary rows."""

    def __init__(self, parent, on_double_click=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._on_double_click = on_double_click
        self._sort_reverse: dict[str, bool] = {c: False for c in COLUMNS}
        self._rows: list[tuple] = []
        self._edit_cb = None
        self._delete_cb = None
        self._build()

    def _build(self):
        self._tree = ttk.Treeview(
            self,
            columns=COLUMNS,
            show="headings",
            selectmode="browse",
        )

        for col, width in zip(COLUMNS, COL_WIDTHS):
            self._tree.heading(col, text=self._col_label(col),
                               command=lambda c=col: self._sort_by(c))
            self._tree.column(col, width=width, minwidth=50)

        vsb = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self._tree.yview)
        hsb = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._tree.grid(row=0, column=0, sticky=tk.NSEW)
        vsb.grid(row=0, column=1, sticky=tk.NS)
        hsb.grid(row=1, column=0, sticky=tk.EW)

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self._ctx_menu = tk.Menu(self, tearoff=0)
        self._ctx_menu.add_command(label=t("ctx_edit"), command=self._ctx_edit)
        self._ctx_menu.add_command(label=t("ctx_delete"), command=self._ctx_delete)

        self._tree.bind("<Double-1>", self._on_double)
        self._tree.bind("<Button-3>", self._show_ctx_menu)

    def refresh_language(self):
        for col in COLUMNS:
            self._tree.heading(col, text=self._col_label(col))
        self._ctx_menu.entryconfig(0, label=t("ctx_edit"))
        self._ctx_menu.entryconfig(1, label=t("ctx_delete"))

    def _col_label(self, col: str) -> str:
        mapping = {
            "lemma": "col_lemma",
            "wordform": "col_wordform",
            "frequency": "col_frequency",
            "morphology": "col_morphology",
        }
        return t(mapping[col])

    def set_callbacks(self, edit_cb=None, delete_cb=None):
        self._edit_cb = edit_cb
        self._delete_cb = delete_cb

    def populate(self, rows: list[tuple]):
        self._rows = rows
        self._refresh(rows)

    def _refresh(self, rows):
        self._tree.delete(*self._tree.get_children())
        for row in rows:
            self._tree.insert("", tk.END, values=row)

    def _sort_by(self, col: str):
        idx = COLUMNS.index(col)
        reverse = self._sort_reverse[col]
        sorted_rows = sorted(
            self._rows,
            key=lambda r: (r[idx] if r[idx] is not None else ""),
            reverse=reverse,
        )
        self._sort_reverse[col] = not reverse
        self._refresh(sorted_rows)

    def get_selected(self) -> tuple | None:
        sel = self._tree.selection()
        if not sel:
            return None
        return self._tree.item(sel[0], "values")

    def _on_double(self, event):
        if self._on_double_click and self.get_selected():
            self._on_double_click()

    def _show_ctx_menu(self, event):
        item = self._tree.identify_row(event.y)
        if item:
            self._tree.selection_set(item)
            self._ctx_menu.post(event.x_root, event.y_root)

    def _ctx_edit(self):
        if self._edit_cb and self.get_selected():
            self._edit_cb()

    def _ctx_delete(self):
        if self._delete_cb and self.get_selected():
            self._delete_cb()
