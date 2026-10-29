"""Web adapters reuse application services; no Tkinter imports or copied algorithms."""

import json
from pathlib import Path
from threading import RLock
from typing import Any

from webapp.jobs import Job
from webapp.workspace import ROOT, Workspace, plain, write_json


class Experiments:
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.cache: dict[str, Any] = {}
        # The legacy repository initializes its schema on every connection.
        # Serialize those transactions across HTTP reader and model-worker threads.
        self.collection_lock = RLock()

    def execute(self, lab: int, body: dict[str, Any], job: Job) -> dict[str, Any]:
        job.checkpoint()
        write_json(job.folder / "request.json", body)
        result = getattr(self, f"lab{lab}")(body, job)
        result = plain(result)
        write_json(job.folder / "result.json", result)
        result["json"] = self.workspace.url(job.folder / "result.json")
        return result

    def audio_report(self, source: Path, folder: Path) -> str:
        """Adapt the existing standalone report's file URI for HTTP playback."""
        from html import escape

        report = folder / "report.html"
        report.write_text(
            report.read_text(encoding="utf-8").replace(
                escape(source.resolve().as_uri(), quote=True),
                self.workspace.url(source),
            ),
            encoding="utf-8",
        )
        return self.workspace.url(report)

    def lab1_data(self, query: str = "") -> dict[str, Any]:
        with self.collection_lock:
            return self._lab1_data(query)

    def _lab1_data(self, query: str) -> dict[str, Any]:
        from lab1.ir_system.bootstrap import application_runtime
        from lab1.ir_system.config import AppConfig

        with application_runtime(
            AppConfig(database=self.workspace.folder / "search.sqlite3")
        ) as app:
            return plain(
                {
                    "documents": app.collection.documents(),
                    "queries": app.judgments.queries(),
                    "judgments": app.judgments.judgments(query)
                    if query.strip()
                    else {},
                }
            )

    def lab1(self, body: dict[str, Any], job: Job) -> dict[str, Any]:
        with self.collection_lock:
            return self._lab1(body, job)

    def _lab1(self, body: dict[str, Any], job: Job) -> dict[str, Any]:
        from lab1.ir_system.bootstrap import application_runtime
        from lab1.ir_system.config import AppConfig
        from lab1.ir_system.domain.models import BM25Parameters, DocumentDraft

        config = AppConfig(
            database=self.workspace.folder / "search.sqlite3",
            bm25=BM25Parameters(float(body.get("k1", 1.5)), float(body.get("b", 0.75))),
        )
        action = body.get("action", "search")
        with application_runtime(config) as app:
            if action == "demo":
                added = app.collection.import_demo()
                return {
                    "kind": "collection",
                    "message": f"Демо загружено: {len(added.document_ids)} документов",
                    **self.lab1_data(),
                }
            if action == "import":
                draft = app.collection.fetch(body["url"])
                job.checkpoint()
                ident = app.collection.add(draft)
                return {
                    "kind": "document",
                    "document": app.collection.get_document(ident),
                }
            if action == "add":
                ident = app.collection.add(
                    DocumentDraft(body["url"], body["title"], body["text"])
                )
                return {
                    "kind": "document",
                    "document": app.collection.get_document(ident),
                }
            if action == "delete":
                app.collection.delete_many([int(i) for i in body["ids"]])
                return {
                    "kind": "collection",
                    "message": "Выбранные документы удалены",
                    **self.lab1_data(),
                }
            if action == "grade":
                app.judgments.grade_many(
                    body["query"], [int(i) for i in body["ids"]], int(body["grade"])
                )
                return {
                    "kind": "collection",
                    "message": "Оценки сохранены",
                    **self.lab1_data(body["query"]),
                }
            if action == "evaluate":
                queries = body.get("queries") or list(app.judgments.queries())
                report = app.evaluation.evaluate(queries)
                path = app.reports.export(report, job.folder / "report")
                return {
                    "kind": "evaluation",
                    "data": report,
                    "report": self.workspace.url(path),
                }
            if action == "document":
                ident = int(body["id"])
                return {
                    "kind": "document",
                    "document": app.collection.get_document(ident),
                    "keywords": app.search.keywords(ident, 20),
                }
            if action != "search":
                raise ValueError("Неизвестная операция поиска.")
            query = str(body.get("query", "")).strip()
            if not query:
                raise ValueError("Введите поисковый запрос на английском.")
            return {
                "kind": "search",
                "query": query,
                "rows": app.search.search(query),
                "parameters": config.bm25,
            }

    def lab2(self, body: dict[str, Any], job: Job) -> dict[str, Any]:
        from lab2.bootstrap import DEMO_MANIFEST, build_experiment
        from lab2.domain.models import CorpusEntry, Settings
        from lab2.infrastructure.corpus import load_manifest
        from lab2.infrastructure.export import export_report

        settings = Settings(**body.get("settings", {}))
        if (
            settings.neural_iterations > 2000
            or settings.neural_features > 30000
            or settings.repetitions > 30
        ):
            raise ValueError(
                "Для локального интерфейса: до 2000 итераций, 30000 признаков и 30 повторов."
            )
        entries = load_manifest(DEMO_MANIFEST) if body.get("demo", True) else []
        for row in body.get("documents", []):
            entries.append(
                CorpusEntry(
                    self.workspace.upload(row["upload"]),
                    row["split"],
                    row.get("language") or None,
                    row.get("source_id", ""),
                    title=row.get("title", ""),
                )
            )
        report = build_experiment(settings).run(
            entries, job.progress, job.cancel.is_set
        )
        job.checkpoint()
        path = export_report(report, job.folder / "report")
        return {"kind": "languages", "data": report, "report": self.workspace.url(path)}

    def lab3(self, body: dict[str, Any], job: Job) -> dict[str, Any]:
        from lab3.bootstrap import DEMO, build_summarizer
        from lab3.domain.models import Document, Source
        from lab3.infrastructure.documents import load_corpus, normalize, read_manifest
        from lab3.infrastructure.export import export_report

        sources = read_manifest(DEMO) if body.get("demo", False) else []
        for row in body.get("documents", []):
            sources.append(
                Source(
                    self.workspace.upload(row["upload"]),
                    row["language"],
                    row["domain"],
                    row.get("title", "Документ"),
                )
            )
        documents = load_corpus(sources) if sources else []
        text = normalize(str(body.get("text", "")))
        if text:
            if len(text) > 200000 or not any(c.isalpha() for c in text):
                raise ValueError(
                    "Текст должен содержать буквы, максимум 200000 символов."
                )
            source = job.folder / "input.txt"
            source.write_text(text, encoding="utf-8")
            documents.append(
                Document(
                    Source(
                        source,
                        body.get("language", "en"),
                        body.get("domain", "art"),
                        "Введённый текст",
                    ),
                    text,
                )
            )
        if "summarizer" not in self.cache:
            self.cache["summarizer"] = build_summarizer()
        result = self.cache["summarizer"].run(
            documents,
            int(body.get("sentences", 10)),
            int(body.get("keywords", 10)),
            job.progress,
            job.cancel.is_set,
        )
        job.checkpoint()
        report = export_report(result, job.folder / "report")
        return {"kind": "summary", "data": result, "report": self.workspace.url(report)}

    def lab4(self, body: dict[str, Any], job: Job) -> dict[str, Any]:
        from lab4.bootstrap import build_service
        from lab4.infrastructure.export import export_report

        if "translator" not in self.cache:
            self.cache["translator"] = build_service(
                self.workspace.folder / "lexicon.sqlite3"
            )
        service, lexicon = self.cache["translator"]
        text = str(body.get("text", ""))
        if body.get("upload"):
            text = self.workspace.upload(body["upload"]).read_text(encoding="utf-8-sig")
        if not text.strip() or len(text) > 100000:
            raise ValueError("Введите текст на английском, не более 100000 символов.")
        domain = body.get("domain", "art")
        if body.get("action") == "correct":
            correction = body["correction"]
            lexicon.correct(
                correction["lemma"],
                correction["pos"],
                domain,
                correction["model"],
                correction["translation"],
            )
        result = service.run(text, domain, job.progress, job.cancel.is_set)
        job.checkpoint()
        path = export_report(
            result, job.folder / "report", int(body.get("sentence", 0))
        )
        from lab4.infrastructure.export import tree_svg

        trees = []
        for sentence in result.analysis.sentences:
            tree = job.folder / f"sentence-{sentence.index}.svg"
            tree.write_text(tree_svg(sentence), encoding="utf-8")
            trees.append(self.workspace.url(tree))
        return {
            "kind": "translation",
            "data": result,
            "domain": domain,
            "trees": trees,
            "report": self.workspace.url(path),
        }

    def audio_source(self, body: dict[str, Any]) -> Path:
        if body.get("upload"):
            return self.workspace.upload(body["upload"])
        from lab5_7.application.project import recording_path

        return recording_path(str(body.get("source", "vowels")))

    def lab5(self, body: dict[str, Any], job: Job) -> dict[str, Any]:
        from lab5_7.application.experiments import quality
        from lab5_7.domain.audio import crop, loop
        from lab5_7.infrastructure.analysis import export_analysis
        from lab5_7.infrastructure.wav import load, save

        action = body.get("action", "analyze")
        if action == "record":
            from lab5_7.infrastructure.capture import record

            seconds = float(body.get("seconds", 5))
            if not 1 <= seconds <= 60:
                raise ValueError("Длительность записи: от 1 до 60 секунд.")
            job.progress(f"Идёт запись микрофона: {seconds:g} с")
            source = job.folder / "recording.wav"
            record(
                source,
                seconds,
                int(body.get("rate", 48000)),
                int(body.get("bits", 16)),
                body.get("device"),
            )
        else:
            source = self.audio_source(body)
        audio, metadata = load(source)
        job.checkpoint()
        if action == "quality":
            quality(source, job.folder / "quality", "recording")
            raw = json.loads(
                (job.folder / "quality/experiment.json").read_text(encoding="utf-8")
            )
            for row in raw["results"]:
                row["audio"] = self.workspace.url(job.folder / "quality" / row["file"])
            return {
                "kind": "quality",
                "data": raw,
                "source_audio": self.workspace.url(source),
            }
        if action in {"crop", "loop"}:
            audio = crop(
                audio,
                float(body.get("start", 0)),
                float(body.get("end", audio.duration)),
            )
            if action == "loop":
                count = int(body.get("repeat", 50))
                if not 1 <= count <= 2000 or audio.duration * count > 300:
                    raise ValueError("Повтор: 1–2000 раз, результат до 300 секунд.")
                audio = loop(audio, count)
            source = job.folder / "fragment.wav"
            save(audio, source)
        data = export_analysis(source, job.folder / "analysis")
        return {
            "kind": "audio",
            "data": data,
            "source": metadata,
            "audio": self.workspace.url(source),
            "report": self.audio_report(source, job.folder / "analysis"),
        }

    def lab6(self, body: dict[str, Any], job: Job) -> dict[str, Any]:
        from lab5_7.application.experiments import permutations
        from lab5_7.domain.audio import crop, gain
        from lab5_7.infrastructure.analysis import export_analysis
        from lab5_7.infrastructure.prosody import (
            coupled_contour,
            coupled_shift,
            manipulate,
        )
        from lab5_7.infrastructure.wav import load, save

        if body.get("action") == "permutations":
            bank = ROOT / "lab5_7/reports/local/lab7_reference3_mama_v1/bank"
            permutations(bank, job.folder / "permutations", body.get("prefix", "word"))
            return {
                "kind": "playlist",
                "rows": [
                    {"title": p.stem, "audio": self.workspace.url(p)}
                    for p in sorted((job.folder / "permutations").glob("*.wav"))
                ],
            }
        source = self.audio_source({"source": "student", **body})
        audio, metadata = load(source)
        if body.get("segment"):
            from lab5_7.application.project import segments

            row = next(
                (
                    s
                    for s in segments()
                    if s["id"] == body["segment"] and s["reviewed"] == "yes"
                ),
                None,
            )
            if row is None or body.get("upload") or row["file"] != source.name:
                raise ValueError("Выберите подтверждённый фрагмент исходной записи.")
            start, end = (
                float(body.get("start", row["start"])),
                float(body.get("end", row["end"])),
            )
            audio = crop(audio, start, end)
            metadata["selected_interval_s"] = [start, end]
            source = job.folder / "original-fragment.wav"
            save(audio, source)
        elif "start" in body and "end" in body:
            start, end = float(body["start"]), float(body["end"])
            audio = crop(audio, start, end)
            metadata["selected_interval_s"] = [start, end]
            source = job.folder / "original-fragment.wav"
            save(audio, source)
        controls = body.get("controls", {})
        method = body.get("method", "psola")
        if method == "psola":
            result = manipulate(
                audio,
                controls.get("pitch_points", []),
                controls.get("duration_points", []),
            )
        elif method == "coupled":
            semitones = float(body.get("semitones", 0))
            if not -12 <= semitones <= 12:
                raise ValueError("Сдвиг высоты: от −12 до +12 полутонов.")
            result = coupled_shift(audio, semitones)
        elif method == "coupled_contour":
            result = coupled_contour(audio, controls.get("rate_points", []))
        else:
            raise ValueError("Неизвестный метод обработки.")
        for interval in controls.get("gain", []):
            result = gain(result, *interval)
        job.checkpoint()
        target = job.folder / "processed.wav"
        save(result, target)
        data = export_analysis(target, job.folder / "analysis")
        return {
            "kind": "audio",
            "audio": self.workspace.url(target),
            "source_audio": self.workspace.url(source),
            "data": data,
            "source": metadata,
            "controls": controls,
            "report": self.audio_report(target, job.folder / "analysis"),
        }

    def lab7(self, body: dict[str, Any], job: Job) -> dict[str, Any]:
        from lab5_7.application.experiments import assemble
        from lab5_7.infrastructure.analysis import export_analysis

        bank = ROOT / "lab5_7/reports/local/lab7_reference3_mama_v1/bank"
        crossfade = float(body.get("crossfade_ms", 0))
        if not 0 <= crossfade <= 50:
            raise ValueError("Сглаживание: 0–50 мс.")
        recipe = str(body.get("recipe", "ref1_syllables"))
        target = job.folder / "synthesis.wav"
        assemble(recipe, bank, target, crossfade)
        job.checkpoint()
        data = export_analysis(target, job.folder / "analysis")
        return {
            "kind": "audio",
            "audio": self.workspace.url(target),
            "source_audio": self.workspace.url(
                bank / (recipe.split("_")[0].replace("ref", "ref_") + ".wav")
            ),
            "data": data,
            "recipe": recipe,
            "crossfade_ms": crossfade,
            "report": self.audio_report(target, job.folder / "analysis"),
        }

    def lab8(self, body: dict[str, Any], job: Job) -> dict[str, Any]:
        from lab8.bootstrap import build_service
        from lab8.domain.models import Settings
        from lab8.infrastructure.export import report

        if "speech" not in self.cache:
            self.cache["speech"] = build_service()
        text = str(body.get("text", ""))
        if body.get("upload"):
            text = self.workspace.upload(body["upload"]).read_text(encoding="utf-8-sig")
        settings = Settings(
            str(body.get("voice", "siwis")),
            float(body.get("speed", 1)),
            float(body.get("volume", 0.8)),
        )
        target = job.folder / "speech.wav"
        result = self.cache["speech"].render(
            text, settings, target, job.progress, job.cancel.is_set
        )
        job.checkpoint()
        report(result)
        return {
            "kind": "speech",
            "audio": self.workspace.url(target),
            "data": result,
            "report": self.workspace.url(target.with_suffix(".html")),
        }

    def lab9(self, body: dict[str, Any], job: Job) -> dict[str, Any]:
        from lab9.application.recognition import RecognitionService
        from lab9.domain.commands import Router, word_error_rate
        from lab9.infrastructure.audio import load_pcm
        from lab9.infrastructure.config import load_policy
        from lab9.infrastructure.export import export_journal
        from lab9.infrastructure.recognizer import VoskEngine

        if body.get("action") == "journal":
            rows = body.get("rows", [])
            if not isinstance(rows, list) or len(rows) > 300:
                raise ValueError("Журнал содержит до 300 событий.")
            export_journal(rows, job.folder / "report")
            return {
                "kind": "journal",
                "rows": rows,
                "report": self.workspace.url(job.folder / "report/report.html"),
            }

        if "recognizer" not in self.cache:
            self.cache["recognizer"] = RecognitionService(VoskEngine())
        language = str(body.get("language", "fr"))
        source = (
            self.workspace.upload(body["upload"])
            if body.get("upload")
            else ROOT / "lab9/reports/demo/audio/tom_read.wav"
        )
        pcm, metadata = load_pcm(source)
        result = self.cache["recognizer"].run(pcm, 16000, language, job.cancel.is_set)
        router = Router(load_policy(self.workspace.folder / "commands.json"))
        rows = []
        for index, utterance in enumerate(result.utterances):
            timestamp = utterance.words[0].start if utterance.words else 0.0
            decision = router.resolve(utterance, language, timestamp)
            rows.append(
                {
                    "time": index,
                    "source": source.name,
                    "language": language,
                    "text": utterance.text,
                    "confidence": utterance.confidence,
                    "status": decision.status,
                    "action": decision.action,
                    "message": decision.reason,
                    "executed": False,
                }
            )
        job.checkpoint()
        export_journal(rows, job.folder / "report")
        transcript = " ".join(u.text for u in result.utterances)
        return {
            "kind": "recognition",
            "text": transcript,
            "rows": rows,
            "data": result,
            "source": metadata,
            "audio": self.workspace.url(source),
            "wer": word_error_rate(body["reference"], transcript)
            if body.get("reference", "").strip()
            else None,
            "report": self.workspace.url(job.folder / "report/report.html"),
        }
