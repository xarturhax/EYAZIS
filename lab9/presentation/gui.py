"""GUI coordination: Vosk worker, command routing, and the reader from lab8."""

import logging
import tkinter as tk
from collections.abc import Callable
from datetime import datetime
from functools import partial
from pathlib import Path
from queue import Empty, Queue
from threading import Event
from time import monotonic
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Protocol
from uuid import uuid4

from lab2.presentation.tasks import TaskRunner
from lab8.bootstrap import ROOT as TTS_ROOT
from lab8.bootstrap import build_service as build_tts
from lab8.domain.models import CancelledError as TtsCancelled
from lab8.domain.models import Result as SpeechResult
from lab8.domain.models import Settings as SpeechSettings
from lab8.infrastructure.player import WindowsPlayer

from lab9.application.recognition import RecognitionResult, RecognitionService
from lab9.bootstrap import DEFAULT_COMMANDS, ROOT
from lab9.domain.commands import LABELS, LANGUAGES, Action, Command, Policy, Router, Utterance
from lab9.domain.reader import Reader
from lab9.infrastructure.audio import load_pcm
from lab9.infrastructure.config import load_policy, save_policy
from lab9.infrastructure.export import export_journal
from lab9.infrastructure.recognizer import CancelledError, VoskEngine

HELP = """Лабораторная №9 · Вариант 8

Французская речь и голосовое управление чтением сочинений.
Язык fr — основной; en — дополнительная проверка реального выбора модели.
Язык команд не переводит введённый французский текст.

1. Введите текст или загрузите пример.
2. На вкладке команд задайте фразы, операции и включённость, сохраните настройки.
   Французские команды начинаются с lecteur, английские — с reader.
3. «Включить микрофон» явно начинает прослушивание.
   Итоговые фразы автоматически сопоставляются с командами.
   Частичные результаты, неизвестные и неуверенные фразы не выполняются.
4. «Выключить микрофон» прекращает захват. Звук микрофона в файлы не пишется.
5. «Проверить WAV» распознаёт запись и показывает решения БЕЗ выполнения действий.
6. Журнал уведомляет о распознанном тексте, уверенности и причине решения.

По умолчанию во время синтеза/чтения микрофон приостанавливается.
«Слушать при чтении (наушники)» позволяет голосовую остановку во время WAV.
Без этого режима для прерывания чтения используйте кнопку «Стоп чтение».
Физическое эхо без наушников может мешать; акустическое эхоподавление не реализовано.

lecteur commence / lecteur stop / lecteur suivant / lecteur précédent /
lecteur répète / lecteur plus vite / lecteur plus lentement.

Следующий/предыдущий меняют выбранный абзац; commence читает его.
Темп действует при следующем чтении. Изменение текста останавливает старое чтение.
Голоса Siwis/Tom и синтез взяты из lab8.
"""


class Player(Protocol):
    def play(self, path: str) -> None: ...
    def stop(self) -> None: ...


class Application:
    def __init__(
        self, root: tk.Tk, commands_path: Path = DEFAULT_COMMANDS, player: Player | None = None
    ) -> None:
        self.root = root
        root.title("ЕЯЗиС · Лабораторная 9 · Голосовые команды")
        root.geometry("1240x880")
        root.minsize(1000, 700)
        self.commands_path = commands_path
        self.policy = load_policy(commands_path)
        self.commands = list(self.policy.commands)
        self.router = Router(self.policy)
        self.reader = Reader()
        self.engine = VoskEngine()
        self.recognizer = RecognitionService(self.engine)
        self.tts = build_tts()
        self.player = player or WindowsPlayer()
        self.asr_runner = TaskRunner(root)
        self.tts_runner = TaskRunner(root)
        self.paused = Event()
        self.events: Queue[tuple[int, Utterance]] = Queue()
        self.epoch = 0
        self.live = False
        self.closed = False
        self.playing = False
        self.play_timer: str | None = None
        self.poll_timer: str | None = None
        self.journal: list[dict[str, object]] = []
        self.language = tk.StringVar(value="fr")
        self.device = tk.StringVar(value="По умолчанию")
        self.device_ids: dict[str, int | None] = {"По умолчанию": None}
        self.status = tk.StringVar(value="Микрофон выключен.")
        self.partial = tk.StringVar()
        self.duplex = tk.BooleanVar(value=False)
        self.auto = tk.BooleanVar(value=True)
        self.threshold = tk.DoubleVar(value=self.policy.threshold)
        self.speed = tk.DoubleVar(value=1)
        self.volume = tk.DoubleVar(value=0.8)
        self.voice = tk.StringVar(value="siwis")
        self.paragraph = tk.StringVar()
        self.phrase = tk.StringVar()
        self.operation = tk.StringVar(value=Action.READ.value)
        self.enabled = tk.BooleanVar(value=True)
        self.asr_controls: list[tuple[ttk.Widget, str]] = []
        self.speech_controls: list[tuple[ttk.Widget, str]] = []
        self._build()
        self.language.trace_add("write", self.language_changed)
        self.duplex.trace_add("write", lambda *_: self.update_pause())
        self.speed.trace_add("write", self.settings_changed)
        self.volume.trace_add("write", self.settings_changed)
        self.voice.trace_add("write", self.settings_changed)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<F1>", lambda _: self.help())
        self.load_example()
        self.refresh_commands()
        self.poll()

    def _build(self) -> None:
        bar = ttk.Frame(self.root, padding=6)
        bar.pack(fill="x")
        ttk.Label(bar, text="Язык ASR").pack(side="left")
        lang = ttk.Combobox(
            bar, textvariable=self.language, values=list(LANGUAGES), width=5, state="readonly"
        )
        lang.pack(side="left", padx=4)
        device = ttk.Combobox(
            bar, textvariable=self.device, values=list(self.device_ids), width=28, state="readonly"
        )
        device.pack(side="left", padx=4)
        self.device_combo = device
        refresh = ttk.Button(bar, text="Микрофоны", command=self.refresh_devices)
        refresh.pack(side="left", padx=4)
        self.listen_button = ttk.Button(
            bar, text="Включить микрофон", command=self.toggle_listening
        )
        self.listen_button.pack(side="left", padx=4)
        wav = ttk.Button(bar, text="Проверить WAV", command=self.open_wav)
        wav.pack(side="left", padx=4)
        ttk.Button(bar, text="F1 · Справка", command=self.help).pack(side="right")
        self.asr_controls.extend(
            [(lang, "readonly"), (device, "readonly"), (refresh, "normal"), (wav, "normal")]
        )
        options = ttk.Frame(self.root, padding=6)
        options.pack(fill="x")
        ttk.Checkbutton(options, text="Выполнять команды", variable=self.auto).pack(side="left")
        ttk.Checkbutton(options, text="Слушать при чтении (наушники)", variable=self.duplex).pack(
            side="left", padx=10
        )
        ttk.Label(options, text="Порог уверенности").pack(side="left")
        scale = ttk.Scale(options, variable=self.threshold, from_=0, to=1, length=120)
        scale.pack(side="left")
        self.asr_controls.append((scale, "normal"))
        tabs = ttk.Notebook(self.root)
        tabs.pack(fill="both", expand=True, padx=8)
        text_tab = ttk.Frame(tabs)
        tabs.add(text_tab, text="Чтение · литература")
        tools = ttk.Frame(text_tab, padding=5)
        tools.pack(fill="x")
        ttk.Button(tools, text="Пример", command=self.load_example).pack(side="left")
        ttk.Button(tools, text="Открыть TXT", command=self.open_text).pack(side="left", padx=5)
        ttk.Button(tools, text="Вставить", command=self.paste).pack(side="left")
        self.para_combo = ttk.Combobox(
            tools, textvariable=self.paragraph, state="readonly", width=65
        )
        self.para_combo.pack(side="right", fill="x", expand=True, padx=5)
        self.para_combo.bind("<<ComboboxSelected>>", self.select_paragraph)
        self.text = ScrolledText(text_tab, wrap="word", font=("Segoe UI", 12), height=10)
        self.text.pack(fill="both", expand=True)
        self.text.bind("<<Modified>>", self.text_modified)
        controls = ttk.Frame(text_tab, padding=6)
        controls.pack(fill="x")
        for label, action in (
            ("Читать", Action.READ),
            ("Повтор", Action.REPEAT),
            ("Предыдущий", Action.PREVIOUS),
            ("Следующий", Action.NEXT),
        ):
            button = ttk.Button(controls, text=label, command=partial(self.perform, action))
            button.pack(side="left", padx=3)
            self.speech_controls.append((button, "normal"))
        ttk.Button(controls, text="Стоп чтение", command=lambda: self.perform(Action.STOP)).pack(
            side="left", padx=3
        )
        voice = ttk.Combobox(
            controls, textvariable=self.voice, values=["siwis", "tom"], width=8, state="readonly"
        )
        voice.pack(side="left", padx=5)
        self.speech_controls.append((voice, "readonly"))
        for label, var, low, high in (
            ("Темп", self.speed, 0.5, 2),
            ("Громкость", self.volume, 0, 1),
        ):
            ttk.Label(controls, text=label).pack(side="left", padx=3)
            slider = ttk.Scale(controls, variable=var, from_=low, to=high, length=100)
            slider.pack(side="left")
            self.speech_controls.append((slider, "normal"))
        command_tab = ttk.Frame(tabs)
        tabs.add(command_tab, text="Список операций")
        self.command_tree = ttk.Treeview(
            command_tab,
            columns=("phrase", "action", "enabled"),
            show="headings",
            selectmode="browse",
        )
        for key, title, width in (
            ("phrase", "Фраза целиком", 480),
            ("action", "Операция", 200),
            ("enabled", "Включена", 80),
        ):
            self.command_tree.heading(key, text=title)
            self.command_tree.column(key, width=width)
        self.command_tree.pack(fill="both", expand=True)
        self.command_tree.bind("<<TreeviewSelect>>", self.command_selected)
        edit = ttk.Frame(command_tab, padding=6)
        edit.pack(fill="x")
        entry = ttk.Entry(edit, textvariable=self.phrase, width=45)
        entry.pack(side="left", fill="x", expand=True)
        operation = ttk.Combobox(
            edit,
            textvariable=self.operation,
            values=[a.value for a in Action],
            state="readonly",
            width=12,
        )
        operation.pack(side="left", padx=4)
        check = ttk.Checkbutton(edit, text="Включена", variable=self.enabled)
        check.pack(side="left", padx=4)
        self.asr_controls.extend([(entry, "normal"), (operation, "readonly"), (check, "normal")])
        buttons = ttk.Frame(command_tab, padding=5)
        buttons.pack(fill="x")
        for label, callback in (
            ("Новая строка", self.new_command),
            ("Применить строку", self.edit_command),
            ("Удалить", self.delete_command),
            ("Открыть настройки", self.open_config),
            ("Сохранить настройки", self.save_config),
        ):
            button = ttk.Button(buttons, text=label, command=callback)
            button.pack(side="left", padx=3)
            self.asr_controls.append((button, "normal"))
        log_tab = ttk.Frame(tabs)
        tabs.add(log_tab, text="Уведомления и распознавание")
        self.log = ScrolledText(log_tab, wrap="word", font=("Consolas", 10))
        self.log.pack(fill="both", expand=True)
        ttk.Button(log_tab, text="Экспорт журнала", command=self.save_journal).pack(
            anchor="w", pady=5
        )
        ttk.Label(self.root, textvariable=self.partial, padding=5, wraplength=1180).pack(fill="x")
        ttk.Label(self.root, textvariable=self.status, padding=8, wraplength=1180).pack(fill="x")

    def current_policy(self) -> Policy:
        return Policy(tuple(self.commands), self.threshold.get(), self.policy.cooldown_seconds)

    def language_changed(self, *_: object) -> None:
        self.router = Router(self.current_policy())
        self.refresh_commands()

    def refresh_commands(self) -> None:
        self.command_tree.delete(*self.command_tree.get_children())
        for i, command in enumerate(self.commands):
            if command.language == self.language.get():
                self.command_tree.insert(
                    "",
                    "end",
                    iid=str(i),
                    values=(
                        command.phrase,
                        LABELS[command.action],
                        "да" if command.enabled else "нет",
                    ),
                )

    def new_command(self) -> None:
        self.command_tree.selection_remove(*self.command_tree.selection())
        self.phrase.set("lecteur " if self.language.get() == "fr" else "reader ")
        self.operation.set(Action.READ.value)
        self.enabled.set(True)

    def command_selected(self, _: object = None) -> None:
        if self.command_tree.selection():
            value = self.commands[int(self.command_tree.selection()[0])]
            self.phrase.set(value.phrase)
            self.operation.set(value.action.value)
            self.enabled.set(value.enabled)

    def edit_command(self) -> None:
        try:
            command = Command(
                self.language.get(),
                self.phrase.get(),
                Action(self.operation.get()),
                self.enabled.get(),
            )
            updated = list(self.commands)
            if self.command_tree.selection():
                updated[int(self.command_tree.selection()[0])] = command
            else:
                updated.append(command)
            policy = Policy(tuple(updated), self.threshold.get(), self.policy.cooldown_seconds)
            self.commands = updated
            self.policy = policy
            self.router = Router(policy)
            self.refresh_commands()
            self.status.set("Список изменён. Сохраните настройки для следующего запуска.")
        except ValueError as error:
            self.error(error)

    def delete_command(self) -> None:
        if not self.command_tree.selection():
            return
        index = int(self.command_tree.selection()[0])
        updated = [c for i, c in enumerate(self.commands) if i != index]
        try:
            policy = Policy(tuple(updated), self.threshold.get(), self.policy.cooldown_seconds)
            self.commands = updated
            self.policy = policy
            self.router = Router(policy)
            self.refresh_commands()
        except ValueError as error:
            self.error(error)

    def save_config(self) -> None:
        try:
            policy = self.current_policy()
            save_policy(self.commands_path, policy)
            self.policy = policy
            self.status.set(f"Настройки сохранены: {self.commands_path}")
        except (ValueError, OSError) as error:
            self.error(error)

    def open_config(self) -> None:
        chosen = filedialog.askopenfilename(filetypes=[("Настройки JSON", "*.json")])
        if chosen:
            try:
                policy = load_policy(Path(chosen))
                self.commands_path = Path(chosen)
                self.policy = policy
                self.commands = list(policy.commands)
                self.threshold.set(policy.threshold)
                self.router = Router(policy)
                self.refresh_commands()
            except (ValueError, OSError) as error:
                self.error(error)

    def refresh_devices(self) -> None:
        import sounddevice as sd

        try:
            devices = sd.query_devices()
            self.device_ids = {"По умолчанию": None}
            self.device_ids.update(
                {
                    f"{i}: {d['name']}": i
                    for i, d in enumerate(devices)
                    if d["max_input_channels"] > 0
                }
            )
            self.device_combo.configure(values=list(self.device_ids))
            if self.device.get() not in self.device_ids:
                self.device.set(next(iter(self.device_ids)))
        except sd.PortAudioError as error:
            self.error(ValueError(str(error)))

    def set_asr_busy(self, value: bool) -> None:
        for widget, state in self.asr_controls:
            widget.configure({"state": "disabled" if value else state})
        self.listen_button.configure(
            text="Прекратить распознавание" if value else "Включить микрофон"
        )

    def toggle_listening(self) -> None:
        if self.asr_runner.busy:
            self.epoch += 1
            self.live = False
            self.asr_runner.cancelled.set()
            self.status.set("Остановка распознавания…")
            return
        try:
            self.router = Router(self.current_policy())
        except ValueError as error:
            self.error(error)
            return
        self.epoch += 1
        token = self.epoch
        self.live = True
        language = self.language.get()
        device = self.device_ids.get(self.device.get())
        self.set_asr_busy(True)
        self.asr_runner.start(
            lambda progress, cancelled: self.engine.listen(
                language,
                device,
                lambda u: self.events.put((token, u)),
                progress,
                cancelled,
                self.paused,
            ),
            self.asr_finished,
            self.asr_failed,
            self.status.set,
        )

    def asr_finished(self, _: object) -> None:
        self.live = False
        self.set_asr_busy(False)
        self.partial.set("")
        self.status.set("Распознавание выключено.")

    def asr_failed(self, error: Exception) -> None:
        self.asr_finished(None)
        self.error(error)

    def open_wav(self, path: Path | None = None) -> None:
        if self.asr_runner.busy:
            return
        if path is None:
            chosen = filedialog.askopenfilename(filetypes=[("Речь WAV", "*.wav")])
            if not chosen:
                return
            path = Path(chosen)
        language = self.language.get()
        self.set_asr_busy(True)
        self.status.set("Распознавание WAV, действия выполняться не будут.")

        def job(
            progress: Callable[[str], None], cancelled: Callable[[], bool]
        ) -> RecognitionResult:
            assert path is not None
            pcm, _ = load_pcm(path)
            progress("Распознавание файла…")
            return self.recognizer.run(pcm, 16000, language, cancelled)

        def done(value: object) -> None:
            assert isinstance(value, RecognitionResult)
            self.set_asr_busy(False)
            if self.asr_runner.cancelled.is_set():
                return
            router = Router(self.current_policy())
            for utterance in value.utterances:
                when = utterance.words[-1].end if utterance.words else 0
                self.handle(utterance, "WAV_TEST", router, when, False)
            self.status.set("WAV распознан; решения записаны в журнал без выполнения.")

        self.asr_runner.start(job, done, self.asr_failed, self.status.set)

    def poll(self) -> None:
        if self.closed:
            return
        try:
            while True:
                token, utterance = self.events.get_nowait()
                if token != self.epoch or not self.live or self.paused.is_set():
                    continue
                if utterance.final:
                    self.handle(utterance, "MICROPHONE", self.router, monotonic(), self.auto.get())
                else:
                    self.partial.set("Промежуточно: " + utterance.text)
        except Empty:
            pass
        self.poll_timer = self.root.after(60, self.poll)

    def handle(
        self, utterance: Utterance, source: str, router: Router, now: float, execute: bool
    ) -> None:
        decision = router.resolve(utterance, self.language.get(), now)
        message = decision.reason
        status = decision.status
        if decision.action is not None:
            if execute:
                message = self.perform(decision.action)
            else:
                status = "TEST_ONLY"
                message = "Команда распознана без выполнения."
        row: dict[str, object] = dict(
            time=datetime.now().isoformat(timespec="seconds"),
            source=source,
            language=self.language.get(),
            text=utterance.text,
            confidence=utterance.confidence,
            status=status,
            action=decision.action.value if decision.action else "",
            message=message,
        )
        self.journal.append(row)
        self.log.insert(
            "end",
            f"{row['time']} [{source}] {utterance.text}\n"
            f"  {status} · {row['action']} · {message}\n",
        )
        self.log.see("end")
        self.status.set(message)

    def set_text(self, text: str) -> None:
        self.stop_speech()
        self.reader.set_text(text)
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.text.edit_modified(False)
        self.update_paragraphs()

    def load_example(self) -> None:
        self.set_text(
            (TTS_ROOT / "data/essai_hugo.txt").read_text(encoding="utf-8").strip()
            + "\n\n"
            + (TTS_ROOT / "data/essai_fable.txt").read_text(encoding="utf-8").strip()
        )

    def open_text(self) -> None:
        chosen = filedialog.askopenfilename(filetypes=[("Unicode TXT", "*.txt")])
        if chosen:
            try:
                path = Path(chosen)
                if path.stat().st_size > 1024 * 1024:
                    raise ValueError("TXT больше 1 МиБ.")
                self.set_text(path.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError) as error:
                self.error(error)

    def paste(self) -> None:
        try:
            self.set_text(self.root.clipboard_get())
        except (tk.TclError, ValueError) as error:
            self.error(ValueError(str(error)))

    def text_modified(self, _: object = None) -> None:
        if self.text.edit_modified():
            self.stop_speech()
            try:
                self.reader.set_text(self.text.get("1.0", "end-1c"))
            except ValueError as error:
                self.reader.set_text("")
                self.status.set(str(error))
            self.update_paragraphs()
            self.text.edit_modified(False)

    def update_paragraphs(self) -> None:
        self.para_combo.configure(
            values=[f"{i + 1}. {p[:90]}" for i, p in enumerate(self.reader.paragraphs)]
        )
        if self.reader.paragraphs:
            self.para_combo.current(self.reader.position)
        else:
            self.paragraph.set("")

    def select_paragraph(self, _: object = None) -> None:
        self.stop_speech()
        if self.para_combo.current() >= 0:
            self.reader.position = self.para_combo.current()

    def settings_changed(self, *_: object) -> None:
        self.stop_speech()
        self.reader.speed = self.speed.get()

    def update_pause(self) -> None:
        if self.tts_runner.busy or (self.playing and not self.duplex.get()):
            self.paused.set()
        else:
            self.paused.clear()

    def stop_speech(self) -> None:
        self.tts_runner.cancelled.set()
        self.player.stop()
        self.playing = False
        if self.play_timer is not None:
            self.root.after_cancel(self.play_timer)
            self.play_timer = None
        self.update_pause()

    def perform(self, action: Action) -> str:
        if self.tts_runner.busy and action != Action.STOP:
            return "Синтез занят. Текущую операцию можно остановить."
        self.stop_speech()
        effect = self.reader.apply(action)
        if action in (Action.FASTER, Action.SLOWER):
            self.speed.set(self.reader.speed)
        self.update_paragraphs()
        self.status.set(effect.message)
        if effect.speak:
            self.read_current()
        return effect.message

    def read_current(self) -> None:
        if not self.reader.current or self.tts_runner.busy:
            return
        text = self.reader.current
        settings = SpeechSettings(self.voice.get(), self.reader.speed, self.volume.get())
        target = ROOT / "work" / f"reading-{uuid4().hex}.wav"
        for widget, _ in self.speech_controls:
            widget.configure({"state": "disabled"})
        self.text.configure(state="disabled")

        def job(progress: Callable[[str], None], cancelled: Callable[[], bool]) -> SpeechResult:
            return self.tts.render(text, settings, target, progress, cancelled)

        self.tts_runner.start(job, self.speech_ready, self.speech_failed, self.status.set)
        self.update_pause()

    def speech_ready(self, value: object) -> None:
        assert isinstance(value, SpeechResult)
        self.speech_idle()
        if self.tts_runner.cancelled.is_set():
            self.update_pause()
            return
        try:
            self.player.play(str(value.wav_path.resolve()))
        except Exception as error:
            self.speech_failed(error)
            return
        self.playing = True
        self.update_pause()
        self.status.set(
            "Чтение. Микрофон приостановлен." if self.paused.is_set() else "Чтение и прослушивание."
        )

        def finished() -> None:
            self.play_timer = None
            self.player.stop()
            self.playing = False
            self.update_pause()
            self.status.set("Чтение завершено.")

        self.play_timer = self.root.after(round(value.duration * 1000) + 200, finished)

    def speech_idle(self) -> None:
        for widget, state in self.speech_controls:
            widget.configure({"state": state})
        self.text.configure(state="normal")

    def speech_failed(self, error: Exception) -> None:
        self.speech_idle()
        self.update_pause()
        self.error(error)

    def save_journal(self) -> None:
        chosen = filedialog.askdirectory(title="Папка журнала")
        if chosen:
            try:
                export_journal(list(self.journal), Path(chosen))
                self.status.set("Журнал сохранён.")
            except OSError as error:
                self.error(error)

    def error(self, error: Exception) -> None:
        self.status.set(str(error))
        if isinstance(error, (CancelledError, TtsCancelled)):
            return
        logging.getLogger("lab9").error("%s", error, exc_info=error)
        messagebox.showerror("Лабораторная 9", str(error), parent=self.root)

    def help(self) -> None:
        messagebox.showinfo("Справка", HELP, parent=self.root)

    def close(self) -> None:
        self.closed = True
        self.epoch += 1
        self.live = False
        self.stop_speech()
        self.asr_runner.close()
        self.tts_runner.close()
        if self.poll_timer:
            self.root.after_cancel(self.poll_timer)
        self.root.destroy()


def launch() -> None:
    root = tk.Tk()
    Application(root)
    root.mainloop()
