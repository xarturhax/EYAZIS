from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict
from html import escape
from pathlib import Path
from statistics import mean
from tempfile import TemporaryDirectory

from lab3.files import source_url
from lab3.logic import METHOD_LABELS, Experiment

ALGORITHM_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="570" viewBox="0 0 1000 570" role="img" aria-label="Алгоритм реферирования"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8" fill="#456175"/></marker></defs><rect width="1000" height="570" fill="#fff"/><rect x="180" y="15" width="640" height="70" rx="9" fill="#eef4f8" stroke="#456175"/><text x="500" y="43" text-anchor="middle" font-family="sans-serif" font-size="17" fill="#162c3e">TXT / PDF · язык и предметная область</text><text x="500" y="66" text-anchor="middle" font-family="sans-serif" font-size="14" fill="#3b5366">Загрузка корпуса и проверка дубликатов</text><rect x="180" y="105" width="640" height="70" rx="9" fill="#eef4f8" stroke="#456175"/><text x="500" y="133" text-anchor="middle" font-family="sans-serif" font-size="17" fill="#162c3e">Нормализация и анализ spaCy</text><text x="500" y="156" text-anchor="middle" font-family="sans-serif" font-size="14" fill="#3b5366">Абзацы, предложения, символьные позиции, леммы</text><rect x="180" y="390" width="640" height="70" rx="9" fill="#eef4f8" stroke="#456175"/><text x="500" y="418" text-anchor="middle" font-family="sans-serif" font-size="17" fill="#162c3e">Выбор K предложений и восстановление порядка</text><text x="500" y="441" text-anchor="middle" font-family="sans-serif" font-size="14" fill="#3b5366">Общие ключевые слова: положительные веса терминов</text><rect x="180" y="480" width="640" height="70" rx="9" fill="#eef4f8" stroke="#456175"/><text x="500" y="508" text-anchor="middle" font-family="sans-serif" font-size="17" fill="#162c3e">Рефераты, сравнение и сохранение</text><text x="500" y="531" text-anchor="middle" font-family="sans-serif" font-size="14" fill="#3b5366">GUI · HTML / JSON / CSV · ссылки · печать</text><rect x="35" y="250" width="440" height="70" rx="9" fill="#e2f1e9" stroke="#456175"/><text x="255" y="278" text-anchor="middle" font-family="sans-serif" font-size="17" fill="#162c3e">TF-IDF × позиции</text><text x="255" y="301" text-anchor="middle" font-family="sans-serif" font-size="14" fill="#3b5366">IDF отдельно по языку; позиции в документе и абзаце</text><rect x="525" y="250" width="440" height="70" rx="9" fill="#e2f1e9" stroke="#456175"/><text x="745" y="278" text-anchor="middle" font-family="sans-serif" font-size="17" fill="#162c3e">TextRank</text><text x="745" y="301" text-anchor="middle" font-family="sans-serif" font-size="14" fill="#3b5366">Граф лексических связей → взвешенный PageRank</text><path d="M500 85V103" fill="none" stroke="#456175" stroke-width="2" marker-end="url(#arrow)"/><path d="M500 175V205H255V248" fill="none" stroke="#456175" stroke-width="2" marker-end="url(#arrow)"/><path d="M500 205H745V248" fill="none" stroke="#456175" stroke-width="2" marker-end="url(#arrow)"/><path d="M255 320V355H500V388" fill="none" stroke="#456175" stroke-width="2" marker-end="url(#arrow)"/><path d="M745 320V355H500" fill="none" stroke="#456175" stroke-width="2" marker-end="url(#arrow)"/><path d="M500 460V478" fill="none" stroke="#456175" stroke-width="2" marker-end="url(#arrow)"/></svg>'


STYLE = """
body{font:16px/1.55 system-ui,sans-serif;color:#182635;max-width:1100px;margin:32px auto;padding:0 24px}
svg{max-width:100%;height:auto}
h1,h2,h3{line-height:1.25} a{color:#125c96} table{border-collapse:collapse;width:100%;margin:16px 0}
td,th{border:1px solid #cbd4dd;padding:7px;text-align:left} th{background:#eef3f7}
.note{background:#fff4d5;padding:12px} .summary{border-left:4px solid #1c786c;padding-left:20px}
small{color:#42566a} button{padding:10px 18px;cursor:pointer} pre{white-space:pre-wrap}
@media print{button,details{display:none}body{max-width:none;margin:0}h2,h3{break-after:avoid}}
"""


def grouped_rows(experiment: Experiment) -> list[dict[str, str | int | float]]:
    groups: dict[tuple[str, str, str], list[tuple[float, float, float, float]]] = {}
    for result in experiment.documents:
        source = result.analyzed.document.source
        for summary in result.summaries:
            groups.setdefault((source.language, source.domain, summary.method), []).append(
                (
                    result.analyzed.preprocessing_seconds,
                    summary.ranking_seconds,
                    summary.word_ratio,
                    summary.sentence_ratio,
                )
            )
    return [
        dict(
            language=key[0],
            domain=key[1],
            method=key[2],
            documents=len(values),
            preprocessing_ms=mean(v[0] for v in values) * 1000,
            ranking_ms=mean(v[1] for v in values) * 1000,
            word_ratio=mean(v[2] for v in values),
            sentence_ratio=mean(v[3] for v in values),
        )
        for key, values in sorted(groups.items())
    ]


def render(experiment: Experiment) -> str:
    parts = [
        '<!doctype html><html lang="ru"><meta charset="utf-8">',
        "<title>Лабораторная 3 · вариант 27</title>",
        f"<style>{STYLE}</style>",
        '<body><button onclick="window.print()">Печать / сохранить PDF</button>',
        "<h1>Автоматическое реферирование · вариант 27</h1>",
        f"<p>Размер реферата: {experiment.requested_sentences} предложений. "
        f"Ключевых слов: {experiment.requested_keywords}. "
        f"Инициализация моделей и библиотек: {experiment.initialization_seconds:.3f} с; "
        f"построение IDF: {experiment.idf_seconds:.4f} с.</p>",
        "<p>Время предобработки включает сегментацию и лемматизацию; инициализация "
        "и построение IDF измерены отдельно. Время ранжирования включает выбор предложений. "
        "Один запуск, без статистической оценки разброса.</p>",
        '<p class="note">Совпадение выбранных предложений — согласие методов, а не точность. '
        "Доля сохранённых слов — характеристика сжатия, а не качества. "
        "Экспертные оценки и эталонные рефераты ещё не собраны.</p>",
    ]
    for warning in experiment.warnings:
        parts.append(f'<p class="note">{escape(warning)}</p>')
    rows = grouped_rows(experiment)
    parts.append("<h2>Схема алгоритма</h2>" + ALGORITHM_SVG)
    parts.append(
        "<h2>Сравнение по языкам и областям</h2><table><tr>"
        "<th>Язык / область</th><th>Метод</th><th>N</th><th>NLP, мс</th>"
        "<th>Ранжирование, мс</th><th>Доля слов</th></tr>"
    )
    for row in rows:
        parts.append(
            f"<tr><td>{row['language']} / {row['domain']}</td>"
            f"<td>{METHOD_LABELS[str(row['method'])]}</td><td>{row['documents']}</td>"
            f"<td>{row['preprocessing_ms']:.2f}</td><td>{row['ranking_ms']:.2f}</td>"
            f"<td>{row['word_ratio']:.1%}</td></tr>"
        )
    parts.append("</table>")
    for number, result in enumerate(experiment.documents, 1):
        analyzed = result.analyzed
        source = analyzed.document.source
        parts.append(
            f"<h2>{number}. {escape(source.title)}</h2>"
            f"<p>{source.language} / {source.domain}; "
            f"{len(analyzed.document.text)} символов; "
            f"{len(analyzed.sentences)} предложений. "
            f"Jaccard выбранных предложений: {result.agreement:.3f}.</p>"
            f'<p><a href="sources/document-{number:03d}.txt">Входной текст</a> · '
            f'<a href="{escape(source.path.resolve().as_uri(), quote=True)}">'
            "Локальный оригинал</a>"
        )
        if source.url:
            parts.append(
                f' · <a href="{escape(source_url(source.url), quote=True)}">Источник публикации</a>'
            )
        parts.append(f"</p><small>{escape(source.attribution)} · {escape(source.license)}</small>")
        for summary in result.summaries:
            parts.append(f"<h3>{METHOD_LABELS[summary.method]}</h3>")
            for note in summary.warnings:
                parts.append(f'<p class="note">{escape(note)}</p>')
            parts.append('<h4>Классический реферат</h4><div class="summary">')
            for i in summary.selected:
                parts.append(f"<p>{escape(analyzed.sentences[i].text)}</p>")
            parts.append("</div><h4>Ключевые слова</h4><p>")
            parts.append(
                "; ".join(f"{escape(word)} ({weight:.4f})" for word, weight in summary.keywords)
                or "Положительные веса отсутствуют."
            )
            parts.append(
                "</p><details><summary>Веса и выбор предложений</summary><table>"
                "<tr><th>№</th><th>Вес</th><th>Выбрано</th><th>Предложение</th></tr>"
            )
            for sentence, score in zip(analyzed.sentences, summary.scores, strict=True):
                parts.append(
                    f"<tr><td>{sentence.index + 1}</td><td>{score:.6f}</td>"
                    f"<td>{'✓' if sentence.index in summary.selected else ''}</td>"
                    f"<td>{escape(sentence.text)}</td></tr>"
                )
            parts.append("</table></details>")
    parts.append(
        "<h2>Параметры и воспроизводимость</h2><p>"
        "IDF: ln(N/df), отдельно по языку, включая обрабатываемые документы. "
        "Методичка: 0.5(1+tf/tf_max)·IDF; сумма по вхождениям терминов; "
        "множители (1−BD/|D|)(1−BP/|P|). "
        "TextRank: граф совпадений лемм, PageRank α=0.85, tol=1e−8, max_iter=200. "
        "При равенстве весов предпочтение более раннему предложению. "
        "Ключевые слова: положительные веса терминов методички для обоих режимов.</p>"
        "<pre>"
        + escape(json.dumps(experiment.versions, ensure_ascii=False, indent=2))
        + "</pre><p>Алгоритм TextRank: "
        '<a href="https://aclanthology.org/W04-3252/">Mihalcea &amp; Tarau, 2004</a>. '
        "Подробная методика и ограничения: lab3/reports/REPORT.md.</p></body></html>"
    )
    return "\n".join(parts)


def export_report(experiment: Experiment, output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output, prefix=".report-") as directory:
        stage = Path(directory)
        (stage / "sources").mkdir()
        (stage / "algorithm.svg").write_text(ALGORITHM_SVG, encoding="utf-8")
        for number, result in enumerate(experiment.documents, 1):
            (stage / "sources" / f"document-{number:03d}.txt").write_text(
                result.analyzed.document.text, encoding="utf-8"
            )
        payload = asdict(experiment)
        (stage / "results.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        rows = grouped_rows(experiment)
        with (stage / "comparison.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        # Bind annotations to the exact input texts AND selected summaries.
        signatures = [
            hashlib.sha256(
                (
                    r.analyzed.document.text
                    + repr([(s.method, s.selected, s.keywords) for s in r.summaries])
                ).encode("utf-8")
            ).hexdigest()
            for r in experiment.documents
        ]
        assessment = (
            "expert_assessment-"
            + hashlib.sha256("".join(signatures).encode("ascii")).hexdigest()[:12]
            + ".csv"
        )
        if not (output / assessment).exists():
            with (stage / assessment).open("w", encoding="utf-8-sig", newline="") as stream:
                assessment_writer = csv.writer(stream)
                assessment_writer.writerow(
                    [
                        "signature",
                        "document",
                        "language",
                        "domain",
                        "method",
                        "informativeness_1_5",
                        "coherence_1_5",
                        "nonredundancy_1_5",
                        "reviewer",
                        "comment",
                    ]
                )
                for number, result in enumerate(experiment.documents, 1):
                    source = result.analyzed.document.source
                    for summary in result.summaries:
                        assessment_writer.writerow(
                            [
                                signatures[number - 1],
                                number,
                                source.language,
                                source.domain,
                                summary.method,
                                "",
                                "",
                                "",
                                "",
                                "",
                            ]
                        )
        (stage / "report.html").write_text(render(experiment), encoding="utf-8")
        for file in stage.rglob("*"):
            if file.is_file() and file.name != "report.html":
                target = output / file.relative_to(stage)
                target.parent.mkdir(parents=True, exist_ok=True)
                file.replace(target)
        (stage / "report.html").replace(output / "report.html")
    return output / "report.html"
