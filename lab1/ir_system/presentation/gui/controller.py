"""Координатор GUI-событий: вызывает сервисы и управляет состоянием экрана."""

import logging
from collections.abc import Callable
from functools import partial

from lab1.ir_system.application.services import Services
from lab1.ir_system.domain.errors import ApplicationError, ValidationError
from lab1.ir_system.domain.models import DocumentDraft, EvaluationReport
from lab1.ir_system.domain.text import normalize_query

from .tasks import TaskRunner
from .window import MainWindow

logger = logging.getLogger(__name__)


class GuiController:
    def __init__(
        self, window: MainWindow, services: Services, tasks: TaskRunner[DocumentDraft]
    ) -> None:
        self.window, self.services, self.tasks = window, services, tasks
        self.report: EvaluationReport | None = None
        self._judgment_query: str | None = None

    def bind(self) -> None:
        collection, search, quality = (
            self.window.collection,
            self.window.search,
            self.window.quality,
        )
        collection.demo_button.configure(command=self.callback(self.demo))
        collection.fetch_button.configure(command=self.callback(self.fetch))
        collection.delete_button.configure(command=self.callback(self.delete))
        collection.details_button.configure(
            command=self.callback(lambda: self.details(collection.table.first_id()))
        )
        collection.table.tree.bind(
            "<Double-1>", self.callback(lambda: self.details(collection.table.first_id()))
        )
        search.search_button.configure(command=self.callback(self.search))
        search.query.bind("<Return>", self.callback(self.search))
        search.open_button.configure(command=self.callback(self.open_result))
        search.table.tree.bind("<Double-1>", self.callback(self.open_result))
        search.details_button.configure(
            command=self.callback(lambda: self.details(search.table.first_id()))
        )
        search.table.tree.bind("<<TreeviewSelect>>", self.callback(self.snippet))
        search.judge_button.configure(command=self.callback(self.judge_search))
        quality.load_button.configure(command=self.callback(self.load_judgments))
        quality.query.bind("<<ComboboxSelected>>", self.callback(self.load_judgments))
        quality.query_text.trace_add("write", self.callback(self.query_changed))
        quality.table.tree.bind(
            "<Double-1>", self.callback(lambda: self.details(quality.table.first_id()))
        )
        for grade, button in quality.grade_buttons.items():
            action = self.callback(partial(self.grade, grade))
            button.configure(command=action)
            quality.table.tree.bind(str(grade), action)
        quality.evaluate_button.configure(command=self.callback(self.evaluate))
        quality.all_button.configure(command=self.callback(lambda: self.evaluate(all_queries=True)))
        quality.export_button.configure(command=self.callback(self.export))
        self.window.bind_menu(
            self.callback(lambda: self.evaluate(all_queries=True)),
            self.callback(self.window.show_help),
        )
        self.window.root.protocol("WM_DELETE_WINDOW", self.close)

    def callback(self, action: Callable[[], None]) -> Callable[..., None]:
        def invoke(*event_args: object) -> None:
            try:
                action()
            except Exception as exc:
                self.handle_error(exc)

        return invoke

    def handle_error(self, error: Exception) -> None:
        if isinstance(error, (ApplicationError, OSError)):
            self.window.show_error(str(error))
        else:
            logger.error(
                "Неожиданная ошибка GUI", exc_info=(type(error), error, error.__traceback__)
            )
            self.window.show_error("Неожиданная ошибка приложения; подробности в терминале")

    def invalidate_report(self) -> None:
        self.report = None
        self.window.quality.show_report(None)

    def refresh(self) -> None:
        documents = self.services.collection.documents()
        self.window.collection.show_documents(documents)
        self.window.quality.query["values"] = self.services.judgments.queries()
        self.window.search.show_results(())
        self.invalidate_report()
        if self.window.quality.query.get().strip():
            self.load_judgments()
        self.window.status.set(f"В коллекции {len(documents)} документов")

    def demo(self) -> None:
        result = self.services.collection.import_demo()
        self.window.quality.query.set(result.queries[0])
        self.refresh()

    def fetch(self) -> None:
        url = self.window.collection.url.get().strip()
        if not url:
            raise ValidationError("Введите адрес интернет-страницы")
        started = self.tasks.start(
            lambda: self.services.collection.fetch(url), self._fetch_success, self._fetch_failure
        )
        if started:
            self.window.collection.set_busy(True)
            self.window.status.set("Загрузка страницы…")

    def _fetch_success(self, draft: DocumentDraft) -> None:
        self.window.collection.set_busy(False)
        self.callback(lambda: self._save_fetched(draft))()

    def _save_fetched(self, draft: DocumentDraft) -> None:
        self.services.collection.add(draft)
        self.refresh()
        self.window.status.set("Страница загружена и проиндексирована")

    def _fetch_failure(self, error: Exception) -> None:
        self.window.collection.set_busy(False)
        self.window.status.set("Страница не загружена")
        self.handle_error(error)

    def delete(self) -> None:
        selected = self.window.collection.table.selected_ids()
        if selected and self.window.confirm_delete(len(selected)):
            self.services.collection.delete_many(selected)
            self.refresh()

    def details(self, document_id: int | None) -> None:
        if document_id is not None:
            document = self.services.collection.get_document(document_id)
            self.window.show_document(document, self.services.search.keywords(document_id))

    def open_result(self) -> None:
        document_id = self.window.search.table.first_id()
        if document_id is not None:
            self.window.open_url(self.services.collection.get_document(document_id).url)

    def search(self) -> None:
        results = self.services.search.search(self.window.search.query.get())
        self.window.search.show_results(results)
        self.window.status.set(f"Найдено: {len(results)}. Двойной щелчок открывает ссылку.")

    def snippet(self) -> None:
        document_id = self.window.search.table.first_id()
        text = (
            self.services.collection.get_document(document_id).text[:300]
            if document_id is not None
            else ""
        )
        self.window.search.snippet.show(text)

    def query_changed(self) -> None:
        self._judgment_query = None
        self.window.quality.table.clear()
        self.invalidate_report()

    def judge_search(self) -> None:
        self.window.quality.query.set(self.window.search.query.get())
        self.window.select_quality()
        self.load_judgments()

    def load_judgments(self) -> None:
        query = normalize_query(self.window.quality.query.get())
        grades = self.services.judgments.judgments(query)
        self.window.quality.show_judgments(self.services.collection.documents(), grades)
        self._judgment_query = query

    def grade(self, grade: int) -> None:
        query = normalize_query(self.window.quality.query.get())
        if query != self._judgment_query:
            raise ValidationError("Откройте разметку изменённого запроса перед сохранением оценок")
        selected = self.window.quality.table.selected_ids()
        if selected:
            self.services.judgments.grade_many(query, selected, grade)
            self.window.quality.query["values"] = self.services.judgments.queries()
            self.load_judgments()
            self.window.quality.table.tree.selection_set(tuple(str(item) for item in selected))
            self.invalidate_report()

    def evaluate(self, all_queries: bool = False) -> None:
        queries = (
            self.services.judgments.queries() if all_queries else (self.window.quality.query.get(),)
        )
        self.invalidate_report()
        self.report = self.services.evaluation.evaluate(queries)
        self.window.quality.show_report(self.report)
        self.window.select_quality()
        self.window.status.set(
            f"Оценено: {len(self.report.rows)}; исключено с R=0: {len(self.report.excluded_queries)}. "
            "Выберите подстраницу «Графики» для просмотра диаграмм."
        )

    def export(self) -> None:
        if self.report is None:
            raise ValidationError("Сначала рассчитайте метрики")
        directory = self.window.choose_report_directory()
        if directory:
            path = self.services.reports.export(self.report, directory)
            self.window.status.set(f"Отчёт сохранён: {path}")
            self.window.open_url(path.resolve().as_uri())

    def close(self) -> None:
        self.tasks.close()
        self.window.root.destroy()
