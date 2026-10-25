import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import core.i18n as i18n
from core.i18n import t
from core.dictionary import Dictionary
from core.lexical_analyzer import analyze
from core.text_reader import read_file
from gui.dictionary_view import DictionaryView
from gui.edit_dialog import EditDialog
from gui.help_dialog import HelpDialog


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self._dictionary = Dictionary()
        self._current_dict_path: str | None = None

        self._build_ui()
        self._bind_shortcuts()
        self._refresh_view()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.title(t("app_title"))
        self.geometry("960x620")
        self.minsize(700, 400)
        self._build_menu()
        self._build_toolbar()
        self._build_search_bar()
        self._build_main_area()
        self._build_status_bar()

    def _build_menu(self):
        self._menubar = tk.Menu(self)

        # File
        self._file_menu = tk.Menu(self._menubar, tearoff=0)
        self._file_menu.add_command(label=t("menu_open"), accelerator="Ctrl+O",
                                    command=self._open_file)
        self._file_menu.add_separator()
        self._file_menu.add_command(label=t("menu_save"), accelerator="Ctrl+S",
                                    command=self._save_dict)
        self._file_menu.add_command(label=t("menu_save_as"), command=self._save_dict_as)
        self._file_menu.add_command(label=t("menu_load"), command=self._load_dict)
        self._file_menu.add_separator()
        self._file_menu.add_command(label=t("menu_export_csv"), command=self._export_csv)
        self._file_menu.add_separator()
        self._file_menu.add_command(label=t("menu_exit"), command=self.quit)
        self._menubar.add_cascade(label=t("menu_file"), menu=self._file_menu)

        # Edit
        self._edit_menu = tk.Menu(self._menubar, tearoff=0)
        self._edit_menu.add_command(label=t("menu_add"), command=self._add_entry)
        self._edit_menu.add_command(label=t("menu_edit_entry"), command=self._edit_entry)
        self._edit_menu.add_command(label=t("menu_delete"), accelerator="Delete",
                                    command=self._delete_entry)
        self._edit_menu.add_separator()
        self._edit_menu.add_command(label=t("menu_clear"), command=self._clear_dict)
        self._menubar.add_cascade(label=t("menu_edit"), menu=self._edit_menu)

        # Search
        self._search_menu = tk.Menu(self._menubar, tearoff=0)
        self._search_menu.add_command(label=t("menu_search_cmd"), accelerator="Ctrl+F",
                                      command=self._focus_search)
        self._search_menu.add_command(label=t("menu_filter_freq"),
                                      command=self._filter_frequency)
        self._search_menu.add_command(label=t("menu_show_all"), command=self._show_all)
        self._menubar.add_cascade(label=t("menu_search"), menu=self._search_menu)

        # View → Language
        self._view_menu = tk.Menu(self._menubar, tearoff=0)
        self._lang_menu = tk.Menu(self._view_menu, tearoff=0)
        self._lang_var = tk.StringVar(value=i18n.get_language())
        self._lang_menu.add_radiobutton(label="English", value="en",
                                        variable=self._lang_var,
                                        command=lambda: self._switch_language("en"))
        self._lang_menu.add_radiobutton(label="Русский", value="ru",
                                        variable=self._lang_var,
                                        command=lambda: self._switch_language("ru"))
        self._view_menu.add_cascade(label=t("menu_language"), menu=self._lang_menu)
        self._menubar.add_cascade(label=t("menu_view"), menu=self._view_menu)

        # Help
        self._help_menu = tk.Menu(self._menubar, tearoff=0)
        self._help_menu.add_command(label=t("menu_guide"), accelerator="F1",
                                    command=self._show_help)
        self._help_menu.add_command(label=t("menu_about"), command=self._show_about)
        self._menubar.add_cascade(label=t("menu_help"), menu=self._help_menu)

        self.config(menu=self._menubar)

    def _build_toolbar(self):
        self._tb_frame = ttk.Frame(self, relief=tk.FLAT)
        self._tb_frame.pack(side=tk.TOP, fill=tk.X, padx=2, pady=2)
        self._tb_buttons: dict[str, ttk.Button] = {}
        self._tb_seps: list[ttk.Separator] = []
        self._render_toolbar()

    def _render_toolbar(self):
        for w in self._tb_frame.winfo_children():
            w.destroy()
        self._tb_buttons.clear()
        self._tb_seps.clear()

        specs = [
            ("tb_open", self._open_file),
            ("tb_save", self._save_dict),
            ("tb_load", self._load_dict),
            ("tb_export", self._export_csv),
            ("|", None),
            ("tb_add", self._add_entry),
            ("tb_edit", self._edit_entry),
            ("tb_delete", self._delete_entry),
            ("|", None),
            ("tb_show_all", self._show_all),
            ("tb_help", self._show_help),
        ]
        for key, cmd in specs:
            if key == "|":
                sep = ttk.Separator(self._tb_frame, orient=tk.VERTICAL)
                sep.pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=2)
                self._tb_seps.append(sep)
            else:
                label = t(key)
                btn = ttk.Button(self._tb_frame, text=label,
                                 width=len(label) + 2, command=cmd)
                btn.pack(side=tk.LEFT, padx=2)
                self._tb_buttons[key] = btn

    def _build_search_bar(self):
        self._search_frame = ttk.Frame(self)
        self._search_frame.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(0, 2))

        self._search_label = ttk.Label(self._search_frame, text=t("search_label"))
        self._search_label.pack(side=tk.LEFT)

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search_change)
        self._search_entry = ttk.Entry(self._search_frame,
                                       textvariable=self._search_var, width=30)
        self._search_entry.pack(side=tk.LEFT, padx=4)

        self._clear_btn = ttk.Button(self._search_frame, text=t("search_clear"),
                                     command=self._show_all)
        self._clear_btn.pack(side=tk.LEFT)

    def _build_main_area(self):
        self._dict_view = DictionaryView(self)
        self._dict_view.pack(fill=tk.BOTH, expand=True, padx=6, pady=2)
        self._dict_view.set_callbacks(
            edit_cb=self._edit_entry,
            delete_cb=self._delete_entry,
        )
        self._dict_view._on_double_click = self._edit_entry

    def _build_status_bar(self):
        self._status_var = tk.StringVar(value=t("status_ready"))
        status = ttk.Label(self, textvariable=self._status_var,
                           relief=tk.SUNKEN, anchor=tk.W)
        status.pack(side=tk.BOTTOM, fill=tk.X)

    # ------------------------------------------------------------------
    # Language switch
    # ------------------------------------------------------------------

    def _switch_language(self, lang: str):
        i18n.set_language(lang)
        self._lang_var.set(lang)
        self._rebuild_ui_text()

    def _rebuild_ui_text(self):
        self.title(t("app_title"))
        # Rebuild menu (simplest way to update all labels at once)
        self._menubar.destroy()
        self._build_menu()
        # Toolbar
        self._render_toolbar()
        # Search bar
        self._search_label.config(text=t("search_label"))
        self._clear_btn.config(text=t("search_clear"))
        # Table column headers + context menu
        self._dict_view.refresh_language()
        # Status
        self._set_status(t("status_ready"))

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def _bind_shortcuts(self):
        self.bind("<Control-o>", lambda e: self._open_file())
        self.bind("<Control-s>", lambda e: self._save_dict())
        self.bind("<Control-f>", lambda e: self._focus_search())
        self.bind("<Delete>", lambda e: self._delete_entry())
        self.bind("<F1>", lambda e: self._show_help())

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _open_file(self):
        path = filedialog.askopenfilename(
            title=t("menu_open"),
            filetypes=[("Text and RTF files", "*.txt *.rtf"),
                       ("Text files", "*.txt"),
                       ("RTF files", "*.rtf"),
                       ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self._set_status(f"{t('status_reading')} {os.path.basename(path)}...")
            self.update_idletasks()
            text = read_file(path)
            self._set_status(t("status_analysing"))
            self.update_idletasks()
            analysis = analyze(text)
            self._dictionary.build_from_analysis(analysis)
            self._refresh_view()
            self._set_status(
                f"{t('status_loaded_file')} '{os.path.basename(path)}' — "
                f"{self._dictionary.count()} {t('status_wordforms')} / "
                f"{self._dictionary.lemma_count()} {t('status_lemmas')}"
            )
        except Exception as exc:
            messagebox.showerror(t("msg_error_title"), str(exc))
            self._set_status(t("msg_error_open"))

    def _save_dict(self):
        if not self._current_dict_path:
            self._save_dict_as()
            return
        try:
            self._dictionary.save(self._current_dict_path)
            self._set_status(f"{t('status_saved')} {self._current_dict_path}")
        except Exception as exc:
            messagebox.showerror(t("msg_error_title"), str(exc))

    def _save_dict_as(self):
        path = filedialog.asksaveasfilename(
            title=t("menu_save_as"),
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="dictionary.json",
        )
        if not path:
            return
        self._current_dict_path = path
        self._save_dict()

    def _load_dict(self):
        path = filedialog.askopenfilename(
            title=t("menu_load"),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self._dictionary.load(path)
            self._current_dict_path = path
            self._refresh_view()
            self._set_status(
                f"{t('status_loaded_file')} '{os.path.basename(path)}' — "
                f"{self._dictionary.count()} {t('status_wordforms')}"
            )
        except Exception as exc:
            messagebox.showerror(t("msg_error_title"), str(exc))

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            title=t("menu_export_csv"),
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="dictionary.csv",
        )
        if not path:
            return
        try:
            self._dictionary.export_csv(path)
            self._set_status(f"{t('status_exported')} {path}")
            messagebox.showinfo(t("msg_export_title"),
                                f"{t('msg_export_done')}\n{path}")
        except Exception as exc:
            messagebox.showerror(t("msg_error_title"), str(exc))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def _add_entry(self):
        dlg = EditDialog(self, mode="add")
        self.wait_window(dlg)
        if dlg.result:
            r = dlg.result
            self._dictionary.add_entry(
                r["lemma"], r["wordform"], r["frequency"], r["morphology"]
            )
            self._refresh_view()
            self._set_status(f"{t('status_added')}: {r['lemma']} / {r['wordform']}")

    def _edit_entry(self):
        row = self._dict_view.get_selected()
        if not row:
            messagebox.showinfo(t("msg_edit_title"), t("msg_edit_select"))
            return
        lemma, wordform, freq, morphology = row
        dlg = EditDialog(self, mode="edit", lemma=lemma, wordform=wordform,
                         frequency=int(freq), morphology=morphology)
        self.wait_window(dlg)
        if dlg.result:
            r = dlg.result
            if r["lemma"] != lemma or r["wordform"] != wordform:
                self._dictionary.delete_wordform(lemma, wordform)
            self._dictionary.add_entry(
                r["lemma"], r["wordform"], r["frequency"], r["morphology"]
            )
            self._refresh_view()
            self._set_status(f"{t('status_updated')}: {r['lemma']} / {r['wordform']}")

    def _delete_entry(self):
        row = self._dict_view.get_selected()
        if not row:
            return
        lemma, wordform, _, _ = row
        if messagebox.askyesno(
            t("msg_delete_title"),
            f"{t('msg_delete_confirm')} '{wordform}' "
            f"{t('msg_delete_of')} '{lemma}'{t('msg_delete_q')}",
        ):
            self._dictionary.delete_wordform(lemma, wordform)
            self._refresh_view()
            self._set_status(f"{t('status_deleted')}: {lemma} / {wordform}")

    def _clear_dict(self):
        if messagebox.askyesno(t("msg_clear_title"), t("msg_clear_confirm")):
            self._dictionary.clear()
            self._refresh_view()
            self._set_status(t("status_cleared"))

    # ------------------------------------------------------------------
    # Search / Filter
    # ------------------------------------------------------------------

    def _on_search_change(self, *_):
        query = self._search_var.get()
        rows = self._dictionary.search(query) if query else self._dictionary.get_sorted()
        self._dict_view.populate(rows)
        self._update_count_status(len(rows))

    def _focus_search(self):
        self._search_entry.focus_set()

    def _filter_frequency(self):
        dlg = _FrequencyFilterDialog(self)
        self.wait_window(dlg)
        if dlg.result is not None:
            min_f, max_f = dlg.result
            rows = self._dictionary.filter_by_frequency(min_f, max_f)
            self._dict_view.populate(rows)
            self._update_count_status(len(rows))

    def _show_all(self):
        self._search_var.set("")
        self._refresh_view()

    # ------------------------------------------------------------------
    # Help
    # ------------------------------------------------------------------

    def _show_help(self):
        HelpDialog(self)

    def _show_about(self):
        messagebox.showinfo(t("msg_about_title"), t("msg_about_body"))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _refresh_view(self):
        rows = self._dictionary.get_sorted()
        self._dict_view.populate(rows)
        self._update_count_status(len(rows))

    def _update_count_status(self, shown: int):
        total = self._dictionary.count()
        lemmas = self._dictionary.lemma_count()
        self._set_status(
            f"{t('status_showing')} {shown} {t('status_of')} {total} "
            f"{t('status_wordforms')} | {lemmas} {t('status_lemmas')}"
            + (f" | {self._current_dict_path}" if self._current_dict_path else "")
        )

    def _set_status(self, msg: str):
        self._status_var.set(msg)


class _FrequencyFilterDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title(t("flt_title"))
        self.resizable(False, False)
        self.grab_set()
        self.result = None
        self._build()
        self._center(parent)

    def _build(self):
        f = ttk.Frame(self, padding=12)
        f.pack()

        ttk.Label(f, text=t("flt_min")).grid(row=0, column=0, sticky=tk.W, pady=4)
        self._min_var = tk.StringVar()
        ttk.Entry(f, textvariable=self._min_var, width=10).grid(row=0, column=1, padx=8)

        ttk.Label(f, text=t("flt_max")).grid(row=1, column=0, sticky=tk.W, pady=4)
        self._max_var = tk.StringVar()
        ttk.Entry(f, textvariable=self._max_var, width=10).grid(row=1, column=1, padx=8)

        ttk.Label(f, text=t("flt_hint")).grid(row=2, column=0, columnspan=2, sticky=tk.W)

        btn = ttk.Frame(self, padding=(12, 0, 12, 12))
        btn.pack()
        ttk.Button(btn, text=t("flt_apply"), command=self._apply).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(btn, text=t("dlg_cancel"), command=self.destroy).pack(side=tk.LEFT)

    def _apply(self):
        def parse(val):
            val = val.strip()
            if not val:
                return None
            try:
                return int(val)
            except ValueError:
                messagebox.showwarning(t("flt_input_err"),
                                       f"'{val}' {t('flt_not_int')}", parent=self)
                return "error"

        min_f = parse(self._min_var.get())
        max_f = parse(self._max_var.get())
        if min_f == "error" or max_f == "error":
            return
        self.result = (min_f, max_f)
        self.destroy()

    def _center(self, parent):
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
