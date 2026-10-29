import { useState } from "react";
import {
  Action,
  Empty,
  Field,
  Files,
  Metrics,
  Panel,
  ResultLinks,
  Table,
} from "./components";
import { useDraft } from "./editors";
import type { LabProps } from "./types";

function Documents({
  rows,
  setRows,
  lab,
}: {
  rows: any[];
  setRows: (rows: any[]) => void;
  lab: number;
}) {
  return (
    <>
      <Files
        accept={lab === 2 ? ".pdf" : ".txt,.pdf"}
        multiple
        onFiles={(files) => setRows([...rows, ...files])}
      />
      {rows.length > 0 && (
        <Table
          heads={
            lab === 2
              ? ["Файл", "Роль", "Язык", "Источник", ""]
              : ["Файл", "Язык", "Область", ""]
          }
          rows={rows.map((row, index) => {
            const change = (key: string, value: string) =>
              setRows(
                rows.map((r, i) => (i === index ? { ...r, [key]: value } : r)),
              );
            const language = (
              <select
                aria-label={"Язык " + row.name}
                value={row.language}
                onChange={(e) => change("language", e.target.value)}
              >
                <option value="en">EN</option>
                <option value="es">ES</option>
                {lab === 2 && <option value="">Неизвестен</option>}
              </select>
            );
            return lab === 2
              ? [
                  row.name,
                  <select
                    aria-label="Роль документа"
                    value={row.split}
                    onChange={(e) => change("split", e.target.value)}
                  >
                    <option value="train">Обучение</option>
                    <option value="test">Тест</option>
                  </select>,
                  language,
                  <input
                    aria-label="Идентификатор источника"
                    placeholder="Произведение"
                    value={row.source_id}
                    onChange={(e) => change("source_id", e.target.value)}
                  />,
                  <button
                    className="text-button"
                    onClick={() => setRows(rows.filter((_, i) => i !== index))}
                  >
                    Убрать
                  </button>,
                ]
              : [
                  row.name,
                  language,
                  <select
                    aria-label="Область"
                    value={row.domain}
                    onChange={(e) => change("domain", e.target.value)}
                  >
                    <option value="art">Искусство</option>
                    <option value="medicine">Медицина</option>
                  </select>,
                  <button
                    className="text-button"
                    onClick={() => setRows(rows.filter((_, i) => i !== index))}
                  >
                    Убрать
                  </button>,
                ];
          })}
        />
      )}
    </>
  );
}

export function Lab2({ busy, job, run }: LabProps) {
  const [demo, setDemo] = useDraft("lab2-demo", true),
    [documents, setDocuments] = useDraft<any[]>("lab2-documents", []),
    [settings, setSettings] = useDraft("lab2-settings", {
      max_word_length: 5,
      min_word_frequency: 4,
      smoothing: 0.5,
      repetitions: 5,
      neural_iterations: 300,
      neural_hidden: 32,
      neural_features: 3000,
      chunk_words: 80,
      seed: 36,
    });
  const labels: Record<string, string> = {
    max_word_length: "Максимальная длина короткого слова",
    min_word_frequency: "Минимальная частота",
    smoothing: "Сглаживание",
    repetitions: "Повторы замера времени",
    neural_iterations: "Итерации нейросети",
    neural_hidden: "Скрытые нейроны",
    neural_features: "Признаки нейросети",
    chunk_words: "Слов в обучающем блоке",
    seed: "Seed",
  };
  const result = job?.status === "completed" ? job.result : null;
  return (
    <>
      <Panel
        title="Корпус PDF"
        description="Сравнение коротких слов, алфавитного метода и нейросети на английских и испанских документах."
      >
        <label className="checkbox">
          <input
            type="checkbox"
            checked={demo}
            onChange={(e) => setDemo(e.target.checked)}
          />{" "}
          Использовать подготовленный корпус: 32 обучающих и 16 тестовых PDF
        </label>
        <Documents rows={documents} setRows={setDocuments} lab={2} />
        <details className="advanced">
          <summary>Параметры методов</summary>
          <div className="form-grid">
            {Object.entries(settings).map(([key, value]) => (
              <Field key={key} label={labels[key]}>
                <input
                  type="number"
                  step={key === "smoothing" ? ".1" : "1"}
                  min={key === "seed" ? 0 : key === "smoothing" ? 0.01 : 1}
                  value={value}
                  onChange={(e) =>
                    setSettings({ ...settings, [key]: +e.target.value })
                  }
                />
              </Field>
            ))}
          </div>
        </details>
        <Action
          busy={busy}
          onClick={() => void run({ demo, documents, settings })}
        >
          Обучить и сравнить
        </Action>
      </Panel>
      <Panel title="Сравнение методов">
        {result ? (
          <>
            <Metrics
              values={Object.entries(result.data.metrics).map(
                ([method, value]: [string, any]) => [
                  method,
                  value.accuracy == null
                    ? "Нет разметки"
                    : (value.accuracy * 100).toFixed(1) + "%",
                ],
              )}
            />
            <Table
              heads={["Метод", "Accuracy", "Macro F1", "Время, мс", "Отказы"]}
              rows={Object.entries(result.data.metrics).map(
                ([method, m]: [string, any]) => [
                  method,
                  m.accuracy == null ? "—" : m.accuracy.toFixed(4),
                  m.macro_f1 == null ? "—" : m.macro_f1.toFixed(4),
                  m.mean_ms.toFixed(3),
                  m.abstentions,
                ],
              )}
            />
            <img
              className="analysis-image"
              src={result.report.replace("report.html", "comparison.svg")}
              alt="Точность и время методов"
            />
            <Table
              heads={[
                "Документ",
                "Эталон",
                "Короткие слова",
                "Алфавит",
                "Нейросеть",
              ]}
              rows={result.data.rows.map((row: any) => [
                row.title,
                row.expected || "—",
                ...["short_words", "alphabet", "neural"].map((m) => (
                  <details>
                    <summary>
                      {row.predictions[m].language || "Не определён"}
                    </summary>
                    <p>{row.predictions[m].explanation}</p>
                    <pre>
                      {JSON.stringify(row.predictions[m].scores, null, 2)}
                    </pre>
                  </details>
                )),
              ])}
            />
            {result.data.warnings.map((w: string, i: number) => (
              <p className="notice" key={i}>
                {w}
              </p>
            ))}
            <ResultLinks result={result} />
          </>
        ) : (
          <Empty />
        )}
      </Panel>
    </>
  );
}

export function Lab3({ busy, job, run }: LabProps) {
  const [text, setText] = useDraft("lab3-text", ""),
    [language, setLanguage] = useDraft("lab3-language", "en"),
    [domain, setDomain] = useDraft("lab3-domain", "art"),
    [demo, setDemo] = useDraft("lab3-demo", true),
    [documents, setDocuments] = useDraft<any[]>("lab3-documents", []),
    [sentences, setSentences] = useDraft("lab3-sentences", 10),
    [keywords, setKeywords] = useDraft("lab3-keywords", 10),
    [selected, setSelected] = useState(0);
  const result = job?.status === "completed" ? job.result : null;
  const doc =
    result?.data.documents[
      Math.min(selected, result.data.documents.length - 1)
    ];
  return (
    <>
      <Panel title="Документы для реферирования">
        <label className="checkbox">
          <input
            type="checkbox"
            checked={demo}
            onChange={(e) => setDemo(e.target.checked)}
          />{" "}
          Добавить демонстрационный корпус EN/ES: медицина и искусство
        </label>
        <Documents rows={documents} setRows={setDocuments} lab={3} />
        <Field label="Или вставьте текст">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Вставьте документ на английском или испанском…"
          />
        </Field>
        <div className="form-grid">
          <Field label="Язык текста">
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
            >
              <option value="en">Английский</option>
              <option value="es">Испанский</option>
            </select>
          </Field>
          <Field label="Область">
            <select value={domain} onChange={(e) => setDomain(e.target.value)}>
              <option value="art">Искусство</option>
              <option value="medicine">Медицина</option>
            </select>
          </Field>
          <Field label="Предложений в реферате">
            <input
              type="number"
              min={1}
              max={100}
              value={sentences}
              onChange={(e) => setSentences(+e.target.value)}
            />
          </Field>
          <Field label="Ключевых слов">
            <input
              type="number"
              min={1}
              max={100}
              value={keywords}
              onChange={(e) => setKeywords(+e.target.value)}
            />
          </Field>
        </div>
        <Action
          busy={busy}
          onClick={() =>
            void run({
              text,
              language,
              domain,
              demo,
              documents,
              sentences,
              keywords,
            })
          }
        >
          Создать и сравнить рефераты
        </Action>
      </Panel>
      <Panel title="Два метода — один документ">
        {doc ? (
          <>
            <Field label="Документ">
              <select
                value={Math.min(selected, result.data.documents.length - 1)}
                onChange={(e) => setSelected(+e.target.value)}
              >
                {result.data.documents.map((d: any, i: number) => (
                  <option value={i} key={i}>
                    {d.analyzed.document.source.title}
                  </option>
                ))}
              </select>
            </Field>
            <Metrics
              values={[
                [
                  "Совпадение выбранных предложений",
                  (doc.agreement * 100).toFixed(1) + "%",
                ],
                ["Предложений в исходнике", doc.analyzed.sentences.length],
              ]}
            />
            <div className="workspace-grid">
              {doc.summaries.map((s: any) => (
                <div className="summary-card" key={s.method}>
                  <h3>
                    {s.method === "position" ? "TF-IDF + позиции" : "TextRank"}
                  </h3>
                  <div className="tags">
                    {s.keywords.map(([word, weight]: [string, number]) => (
                      <span key={word} title={"Вес " + weight.toFixed(4)}>
                        {word}
                      </span>
                    ))}
                  </div>
                  {s.selected.map((i: number) => (
                    <p key={i}>{doc.analyzed.sentences[i].text}</p>
                  ))}
                  <small className="muted">
                    Сжатие по словам: {(s.word_ratio * 100).toFixed(1)}% ·
                    Ранжирование: {(s.ranking_seconds * 1000).toFixed(2)} мс
                  </small>
                  {s.warnings.map((w: string, i: number) => (
                    <p className="notice" key={i}>
                      {w}
                    </p>
                  ))}
                </div>
              ))}
            </div>
            <details className="advanced">
              <summary>Исходный текст и оценки предложений</summary>
              <Table
                heads={["Предложение", "TF-IDF + позиции", "TextRank"]}
                rows={doc.analyzed.sentences.map((s: any, i: number) => [
                  s.text,
                  ...doc.summaries.map((m: any) =>
                    Number(m.scores[i]).toFixed(5),
                  ),
                ])}
              />
            </details>
            {result.data.warnings.map((w: string, i: number) => (
              <p className="notice" key={i}>
                {w}
              </p>
            ))}
            <ResultLinks result={result} />
          </>
        ) : (
          <Empty />
        )}
      </Panel>
    </>
  );
}

export function Lab4({ busy, job, run }: LabProps) {
  const [text, setText] = useDraft(
      "lab4-text",
      "Language connects people and makes knowledge accessible. Literature preserves our cultural memory.",
    ),
    [domain, setDomain] = useDraft("lab4-domain", "art"),
    [file, setFile] = useDraft<any>("lab4-file", null),
    [sentence, setSentence] = useState(0),
    [edits, setEdits] = useState<Record<string, string>>({});
  const result = job?.status === "completed" ? job.result : null;
  const data = result?.data;
  const send = (extra: any = {}) =>
    run({ text, domain, upload: file?.id, ...extra });
  return (
    <>
      <Panel title="Перевод с английского на французский">
        <Files accept=".txt" onFiles={(files) => setFile(files[0])} />
        {file && (
          <p>
            {file.name}{" "}
            <button className="text-button" onClick={() => setFile(null)}>
              Использовать введённый текст
            </button>
          </p>
        )}
        <Field label="Английский текст">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={!!file}
          />
        </Field>
        <Field label="Предметная область">
          <select value={domain} onChange={(e) => setDomain(e.target.value)}>
            <option value="art">Искусство</option>
            <option value="medicine">Медицина</option>
          </select>
        </Field>
        <Action busy={busy} onClick={() => void send()}>
          Перевести и разобрать
        </Action>
      </Panel>
      <Panel title="Перевод и анализ">
        {data ? (
          <>
            <Metrics
              values={[
                ["Исходных слов", data.source_words],
                ["Покрыто словарём", data.translated_source_words],
                ["Слов в переводе", data.target_words],
              ]}
            />
            <div className="translation-output" lang="fr">
              {data.translation}
            </div>
            <h3>Частотный словарь</h3>
            <Table
              heads={[
                "Лемма",
                "Часть речи",
                "Частота",
                "Перевод",
                "Источник",
                "",
              ]}
              rows={data.entries.map((e: any) => {
                const key = e.lemma + "|" + e.pos;
                return [
                  e.lemma,
                  e.pos,
                  e.frequency,
                  <input
                    aria-label={"Перевод " + e.lemma}
                    value={edits[key] ?? e.translation}
                    onChange={(v) =>
                      setEdits({ ...edits, [key]: v.target.value })
                    }
                  />,
                  e.origin,
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={() =>
                      void run({
                        action: "correct",
                        text: data.analysis.text,
                        domain: result.domain,
                        correction: {
                          lemma: e.lemma,
                          pos: e.pos,
                          model:
                            data.versions.model + "@" + data.versions.revision,
                          translation: edits[key] ?? e.translation,
                        },
                      })
                    }
                  >
                    Сохранить правку
                  </button>,
                ];
              })}
            />
            <Field label="Предложение для грамматического разбора">
              <select
                value={Math.min(sentence, data.analysis.sentences.length - 1)}
                onChange={(e) => setSentence(+e.target.value)}
              >
                {data.analysis.sentences.map((s: any, i: number) => (
                  <option key={i} value={i}>
                    {s.text}
                  </option>
                ))}
              </select>
            </Field>
            <img
              className="analysis-image"
              src={
                result.trees[
                  Math.min(sentence, data.analysis.sentences.length - 1)
                ]
              }
              alt="Дерево зависимостей выбранного предложения"
            />
            <Table
              heads={[
                "Слово",
                "Лемма",
                "POS",
                "Морфология",
                "Связь",
                "Вершина",
              ]}
              rows={data.analysis.sentences[
                Math.min(sentence, data.analysis.sentences.length - 1)
              ].tokens.map((t: any) => [
                t.text,
                t.lemma,
                t.pos,
                t.morphology,
                t.dependency,
                t.head,
              ])}
            />
            {data.warnings.map((w: string, i: number) => (
              <p className="notice" key={i}>
                {w}
              </p>
            ))}
            <ResultLinks result={result} />
          </>
        ) : (
          <Empty />
        )}
      </Panel>
    </>
  );
}
