from collections.abc import Callable
from dataclasses import replace
from time import perf_counter

from lab4.application.ports import Analyzer, Lexicon, Translator
from lab4.domain.models import Analysis, Entry, Result, dictionary


class CancelledError(Exception):
    pass


class TranslationService:
    def __init__(self, analyzer: Analyzer, translator: Translator, lexicon: Lexicon) -> None:
        self.analyzer, self.translator, self.lexicon = analyzer, translator, lexicon

    def populate(
        self,
        analysis: Analysis,
        domain: str,
        model: str,
        refresh: bool,
        progress: Callable[[str], None],
        cancelled: Callable[[], bool],
    ) -> tuple[Entry, ...]:
        entries = dictionary(analysis)
        pending = []
        for entry in entries:
            value, origin = self.lexicon.get(entry.lemma, entry.pos, domain, model)
            if not value or (refresh and origin != "manual"):
                pending.append(entry)
        # Small groups permit cancellation and preserve all-or-nothing DB updates.
        rows: list[tuple[str, str, str]] = []
        for start in range(0, len(pending), 8):
            if cancelled():
                raise CancelledError("Операция отменена; текущая группа завершена.")
            batch = pending[start : start + 8]
            progress(f"Словарь: {start}/{len(pending)} новых эквивалентов")
            values = self.translator.translate([e.lemma for e in batch])
            if len(values) != len(batch) or any(not v.strip() for v in values):
                raise ValueError("Некорректный ответ переводчика для словаря.")
            rows.extend((e.lemma, e.pos, value) for e, value in zip(batch, values, strict=True))
        if cancelled():
            raise CancelledError("Операция отменена.")
        self.lexicon.store_auto(rows, domain, model)
        return tuple(
            replace(e, translation=value, origin=origin)
            for e in entries
            for value, origin in [self.lexicon.get(e.lemma, e.pos, domain, model)]
        )

    def run(
        self,
        text: str,
        domain: str,
        progress: Callable[[str], None] = lambda _: None,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> Result:
        if domain not in {"medicine", "art"}:
            raise ValueError("Выберите medicine или art.")
        if cancelled():
            raise CancelledError("Операция отменена.")
        progress("Загрузка моделей EN→FR…")
        start = perf_counter()
        versions = self.analyzer.prepare() | self.translator.prepare()
        timings = {"initialization": perf_counter() - start}
        start = perf_counter()
        analysis = self.analyzer.analyze(text)
        timings["analysis"] = perf_counter() - start
        translations = []
        start = perf_counter()
        for sentence in analysis.sentences:
            if cancelled():
                raise CancelledError("Операция отменена.")
            progress(f"Перевод предложения {sentence.index + 1}/{len(analysis.sentences)}")
            values = self.translator.translate([sentence.text])
            if len(values) != 1 or not values[0].strip():
                raise ValueError("Пустой перевод предложения.")
            translations.append(values[0])
        timings["translation"] = perf_counter() - start
        start = perf_counter()
        model = versions["model"] + "@" + versions["revision"]
        entries = self.populate(analysis, domain, model, False, progress, cancelled)
        timings["dictionary"] = perf_counter() - start
        paragraphs: dict[int, list[str]] = {}
        for sentence, translated in zip(analysis.sentences, translations, strict=True):
            paragraphs.setdefault(sentence.paragraph, []).append(translated)
        translation = "\n\n".join(" ".join(parts) for parts in paragraphs.values())
        source_words = sum(e.frequency for e in entries)
        import re

        target_words = len(re.findall(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*", translation))
        return Result(
            analysis,
            tuple(translations),
            translation,
            entries,
            source_words,
            sum(e.frequency for e in entries if e.covered),
            target_words,
            timings,
            versions,
            (
                "Автоматические словарные эквиваленты получены изолированно, "
                "требуют проверки и не являются выравниванием полного перевода.",
                "Число переведённых слов — число исходных словоупотреблений с "
                "эквивалентом в словаре; совпавшие с исходником автопереводы требуют ручного подтверждения и не входят в покрытие. Это не оценка качества.",
                "Длинные предложения делятся по 384 токена модели; возможна потеря "
                "контекста на границе. Исходный текст не обрезается.",
            ),
        )
