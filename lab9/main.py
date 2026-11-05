"""Самостоятельное окно лабораторной. Запуск: python lab9/main.py."""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import queue
import re
import threading
import time
import tkinter as tk
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime
from threading import Event
from tkinter import filedialog, messagebox, ttk

import sounddevice as sd
import soundfile as sf

from lab8.logic import ROOT as SPEECH_ROOT
from lab8.logic import Settings, build_service
from lab9.logic import (
    DEFAULT_COMMANDS,
    ROOT,
    Action,
    Command,
    Policy,
    RecognitionService,
    Router,
    VoskEngine,
    load_pcm,
    load_policy,
    save_policy,
    word_error_rate,
)
from lab9.report import export_journal


class App:
    def __init__(self, root, policy_path=DEFAULT_COMMANDS):
        self.root = root
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.cancel = Event()
        self.events = queue.Queue()
        self.future = self.result = None
        self.status = tk.StringVar(value="Готово к работе.")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.title("Лабораторная №9 — французская речь и команды · вариант 8")
        root.geometry("1200x870")
        self.policy_path = Path(policy_path)
        self.policy = load_policy(self.policy_path)
        self.router = Router(self.policy)
        self.engine, self.speech = VoskEngine(), build_service()
        self.live_events = queue.Queue()
        self.listen_stop, self.paused = Event(), Event()
        self.listener = None
        self.journal = []
        self.paragraph, self.generation = 0, 0
        self.language, self.voice = tk.StringVar(value="fr"), tk.StringVar(value="siwis")
        self.speed, self.volume = tk.DoubleVar(value=1), tk.DoubleVar(value=0.8)
        self.device, self.partial = tk.StringVar(value="По умолчанию"), tk.StringVar()
        self.execute_commands = tk.BooleanVar(value=False)
        self.position = tk.StringVar(value="Абзац 1")
        bar = ttk.Frame(root, padding=8)
        bar.pack(fill="x")
        for name, action in (
            ("Пример: Гюго", self.example),
            ("Открыть TXT", self.open_text),
            ("Настроить команды", self.settings),
            ("Сохранить журнал", self.save),
        ):
            ttk.Button(bar, text=name, command=action).pack(side="left", padx=4)
        ttk.Label(bar, text="ASR:").pack(side="left", padx=(10, 2))
        ttk.Combobox(
            bar, textvariable=self.language, values=("fr", "en"), state="readonly", width=4
        ).pack(side="left")
        self.text = tk.Text(root, wrap="word", height=10)
        self.text.pack(fill="both", expand=True, padx=8)
        reader = ttk.Frame(root, padding=8)
        reader.pack(fill="x")
        ttk.Label(reader, textvariable=self.position).pack(side="left", padx=4)
        for name, action in (
            ("Читать", Action.READ),
            ("Стоп", Action.STOP),
            ("Предыдущий", Action.PREVIOUS),
            ("Следующий", Action.NEXT),
            ("Повторить", Action.REPEAT),
        ):
            ttk.Button(reader, text=name, command=lambda a=action: self.action(a)).pack(
                side="left", padx=2
            )
        ttk.Combobox(
            reader, textvariable=self.voice, values=("siwis", "tom"), width=7, state="readonly"
        ).pack(side="left", padx=5)
        ttk.Label(reader, text="Темп").pack(side="left")
        ttk.Spinbox(reader, textvariable=self.speed, from_=0.5, to=2, increment=0.1, width=5).pack(
            side="left", padx=4
        )
        ttk.Label(reader, text="Громкость").pack(side="left")
        ttk.Scale(reader, variable=self.volume, from_=0, to=1, length=100).pack(side="left")
        microphone = ttk.Frame(root, padding=8)
        microphone.pack(fill="x")
        self.devices = ttk.Combobox(
            microphone,
            textvariable=self.device,
            values=("По умолчанию",),
            width=35,
            state="readonly",
        )
        self.devices.pack(side="left")
        ttk.Button(microphone, text="Обновить устройства", command=self.refresh_devices).pack(
            side="left", padx=4
        )
        ttk.Button(microphone, text="Включить микрофон", command=self.listen).pack(side="left")
        ttk.Button(microphone, text="Остановить микрофон", command=self.listen_stop.set).pack(
            side="left", padx=4
        )
        ttk.Checkbutton(microphone, text="Выполнять команды", variable=self.execute_commands).pack(
            side="left"
        )
        ttk.Label(root, textvariable=self.partial, padding=8, wraplength=1150).pack(fill="x")
        wav = ttk.Frame(root, padding=8)
        wav.pack(fill="x")
        ttk.Button(wav, text="Распознать WAV (без действий)", command=self.recognize_file).pack(
            side="left"
        )
        ttk.Label(wav, text="Эталон для WER (необязательно):").pack(side="left", padx=8)
        self.reference = ttk.Entry(wav)
        self.reference.pack(side="left", fill="x", expand=True)
        self.events_tree = ttk.Treeview(
            root,
            columns=("time", "text", "confidence", "status", "action", "message"),
            show="headings",
            height=11,
        )
        for col, title in zip(
            ("time", "text", "confidence", "status", "action", "message"),
            ("Время", "Распознано", "Уверенность", "Решение", "Действие", "Пояснение"),
        ):
            self.events_tree.heading(col, text=title)
            self.events_tree.column(col, width=150)
        self.events_tree.pack(fill="both", expand=True, padx=8)
        ttk.Label(root, textvariable=self.status, padding=8, wraplength=1150).pack(fill="x")
        self.example()
        root.after(100, self.poll_live)

    def example(self):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", (SPEECH_ROOT / "data/essai_hugo.txt").read_text(encoding="utf-8"))
        self.paragraph = 0

    def open_text(self):
        path = filedialog.askopenfilename(filetypes=[("TXT", "*.txt")], parent=self.root)
        if path:
            self.text.delete("1.0", "end")
            self.text.insert("1.0", Path(path).read_text(encoding="utf-8-sig"))
            self.paragraph = 0

    def refresh_devices(self):
        try:
            names = [
                f"{i}: {d['name']}"
                for i, d in enumerate(sd.query_devices())
                if d["max_input_channels"] > 0
            ]
            self.devices.configure(values=["По умолчанию", *names])
        except Exception as error:
            messagebox.showerror("Микрофоны", str(error), parent=self.root)

    def listen(self):
        if self.listener and self.listener.is_alive():
            return
        if self.future and not self.future.done():
            messagebox.showinfo("Распознавание", "Дождитесь текущей обработки.", parent=self.root)
            return
        language = self.language.get()
        device = (
            None if self.device.get() == "По умолчанию" else int(self.device.get().split(":", 1)[0])
        )
        self.listen_stop.clear()

        def work():
            try:
                self.engine.listen(
                    language,
                    device,
                    lambda u: self.live_events.put(("speech", (u, language))),
                    lambda m: self.live_events.put(("status", m)),
                    self.listen_stop.is_set,
                    self.paused,
                )
            except Exception as error:
                self.live_events.put(("error", str(error)))
            finally:
                self.live_events.put(("status", "Микрофон остановлен."))

        self.listener = threading.Thread(target=work, daemon=True)
        self.listener.start()

    def poll_live(self):
        try:
            while True:
                kind, value = self.live_events.get_nowait()
                if kind == "speech":
                    utterance, language = value
                    self.partial.set(utterance.text)
                    if utterance.final:
                        decision = self.router.resolve(utterance, language, time.monotonic())
                        self.log(decision, language, "microphone", self.execute_commands.get())
                else:
                    self.status.set(value)
        except queue.Empty:
            pass
        self.root.after(100, self.poll_live)

    def log(self, decision, language, source, execute=False):
        message = decision.reason
        if decision.action is not None:
            if execute:
                self.action(decision.action)
            else:
                message += " Только проверка; действие не выполнено."
        row = asdict(decision) | {
            "time": datetime.now().isoformat(timespec="seconds"),
            "source": source,
            "language": language,
            "message": message,
            "executed": bool(execute and decision.action is not None),
        }
        self.journal.append(row)
        self.events_tree.insert(
            "",
            "end",
            values=(
                row["time"],
                row["text"],
                row["confidence"],
                row["status"],
                row["action"] or "",
                message,
            ),
        )

    def recognize_file(self):
        if self.listener and self.listener.is_alive():
            messagebox.showinfo("WAV", "Сначала остановите микрофон.", parent=self.root)
            return
        path = filedialog.askopenfilename(
            initialdir=ROOT / "reports/demo/audio", filetypes=[("WAV", "*.wav")], parent=self.root
        )
        if path:
            language, reference = self.language.get(), self.reference.get()

            def task():
                pcm, metadata = load_pcm(Path(path))
                result = RecognitionService(self.engine).run(
                    pcm, 16000, language, self.cancel.is_set
                )
                return {
                    "kind": "recognition",
                    "result": result,
                    "language": language,
                    "reference": reference,
                    "input": metadata,
                }

            self.start(task)

    def action(self, action):
        if action == Action.STOP:
            self.generation += 1
            self.cancel.set()
            sd.stop()
            self.status.set("Чтение остановлено.")
            return
        paragraphs = [
            p.strip() for p in re.split(r"\n\s*\n", self.text.get("1.0", "end-1c")) if p.strip()
        ]
        if not paragraphs:
            self.status.set("Введите сочинение.")
            return
        self.paragraph = min(self.paragraph, len(paragraphs) - 1)
        if action == Action.NEXT:
            self.paragraph = min(self.paragraph + 1, len(paragraphs) - 1)
        elif action == Action.PREVIOUS:
            self.paragraph = max(0, self.paragraph - 1)
        elif action == Action.FASTER:
            self.speed.set(round(min(2, self.speed.get() + 0.1), 1))
        elif action == Action.SLOWER:
            self.speed.set(round(max(0.5, self.speed.get() - 0.1), 1))
        elif action in (Action.READ, Action.REPEAT):
            try:
                settings = Settings(self.voice.get(), self.speed.get(), self.volume.get())
                text = paragraphs[self.paragraph]
                token = self.generation
                target = ROOT / "reports/local" / f"read_{datetime.now():%Y%m%d_%H%M%S_%f}.wav"
                self.start(
                    lambda: {
                        "kind": "speech",
                        "token": token,
                        "result": self.speech.render(
                            text, settings, target, self.events.put, self.cancel.is_set
                        ),
                    }
                )
            except Exception as error:
                self.status.set(str(error))
        self.position.set(f"Абзац {self.paragraph + 1} из {len(paragraphs)}")

    def show_result(self):
        if self.result["kind"] == "speech":
            if self.result["token"] == self.generation:
                audio, rate = sf.read(self.result["result"].wav_path, dtype="float32")
                sd.play(audio, rate)
                self.status.set("Чтение абзаца. Микрофон управляется отдельно.")
        else:
            value = self.result
            router = Router(self.policy)
            for utterance in value["result"].utterances:
                self.log(
                    router.resolve(
                        utterance,
                        value["language"],
                        utterance.words[-1].end if utterance.words else 0,
                    ),
                    value["language"],
                    "wav",
                    False,
                )
            hypothesis = " ".join(u.text for u in value["result"].utterances)
            self.partial.set(hypothesis)
            self.status.set(
                f"WAV распознан: {value['result'].recognition_seconds:.3f} с. Действия не выполнялись."
            )
            if value["reference"].strip():
                self.status.set(
                    self.status.get()
                    + " WER: "
                    + str(word_error_rate(value["reference"], hypothesis))
                )

    def settings(self):
        window = tk.Toplevel(self.root)
        window.title("Фразы команд")
        window.geometry("950x550")
        commands = list(self.policy.commands)
        tree = ttk.Treeview(
            window, columns=("language", "phrase", "action", "enabled"), show="headings", height=12
        )
        for col, title in zip(
            ("language", "phrase", "action", "enabled"),
            ("Язык", "Фраза целиком", "Операция", "Включена"),
        ):
            tree.heading(col, text=title)
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        language, phrase, action = (
            tk.StringVar(value="fr"),
            tk.StringVar(),
            tk.StringVar(value="read"),
        )
        enabled = tk.BooleanVar(value=True)
        threshold, cooldown = (
            tk.DoubleVar(value=self.policy.threshold),
            tk.DoubleVar(value=self.policy.cooldown_seconds),
        )
        row = ttk.Frame(window, padding=8)
        row.pack(fill="x")
        ttk.Combobox(
            row, textvariable=language, values=("fr", "en"), width=4, state="readonly"
        ).pack(side="left")
        ttk.Entry(row, textvariable=phrase, width=35).pack(side="left", padx=4)
        ttk.Combobox(
            row, textvariable=action, values=[a.value for a in Action], width=11, state="readonly"
        ).pack(side="left")
        ttk.Checkbutton(row, text="Включена", variable=enabled).pack(side="left")

        def refresh():
            tree.delete(*tree.get_children())
            for i, command in enumerate(commands):
                tree.insert(
                    "",
                    "end",
                    iid=str(i),
                    values=(
                        command.language,
                        command.phrase,
                        command.action.value,
                        command.enabled,
                    ),
                )

        def select(_=None):
            if tree.selection():
                command = commands[int(tree.selection()[0])]
                language.set(command.language)
                phrase.set(command.phrase)
                action.set(command.action.value)
                enabled.set(command.enabled)

        def apply(add=False):
            try:
                command = Command(language.get(), phrase.get(), Action(action.get()), enabled.get())
                if add:
                    commands.append(command)
                elif tree.selection():
                    commands[int(tree.selection()[0])] = command
                refresh()
            except Exception as error:
                messagebox.showerror("Команда", str(error), parent=window)

        def remove():
            if tree.selection():
                commands.pop(int(tree.selection()[0]))
                refresh()

        def save():
            try:
                policy = Policy(tuple(commands), threshold.get(), cooldown.get())
                save_policy(self.policy_path, policy)
                self.policy, self.router = policy, Router(policy)
                window.destroy()
            except Exception as error:
                messagebox.showerror("Настройки", str(error), parent=window)

        tree.bind("<<TreeviewSelect>>", select)
        controls = ttk.Frame(window, padding=8)
        controls.pack(fill="x")
        for name, function in (
            ("Добавить", lambda: apply(True)),
            ("Изменить строку", apply),
            ("Удалить", remove),
            ("Сохранить настройки", save),
        ):
            ttk.Button(controls, text=name, command=function).pack(side="left", padx=3)
        ttk.Label(controls, text="Порог").pack(side="left", padx=4)
        ttk.Spinbox(controls, textvariable=threshold, from_=0, to=1, increment=0.05, width=5).pack(
            side="left"
        )
        ttk.Label(controls, text="Интервал повторов, с").pack(side="left", padx=4)
        ttk.Spinbox(controls, textvariable=cooldown, from_=0, to=10, increment=0.1, width=5).pack(
            side="left"
        )
        refresh()

    def save(self):
        folder = filedialog.askdirectory(parent=self.root)
        if folder:
            export_journal(self.journal, Path(folder))
            webbrowser.open((Path(folder) / "report.html").as_uri())

    def start(self, function):
        if self.future is not None and not self.future.done():
            return
        self.cancel.clear()
        self.result = None
        self.status.set("Выполняется…")
        self.future = self.pool.submit(function)
        self.root.after(100, self.poll)

    def poll(self):
        try:
            while True:
                self.status.set(self.events.get_nowait())
        except queue.Empty:
            pass
        if not self.future.done():
            self.root.after(100, self.poll)
            return
        try:
            self.result = self.future.result()
            self.show_result()
        except Exception as error:
            self.status.set(str(error))
            messagebox.showerror("Выполнение", str(error), parent=self.root)

    def close(self):
        self.listen_stop.set()
        sd.stop()
        self.cancel.set()
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


if __name__ == "__main__":
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    root = tk.Tk()
    App(root)
    root.mainloop()
