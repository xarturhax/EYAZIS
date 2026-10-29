import { useEffect, useState } from "react";
import { api } from "./api";
import {
  Action,
  Empty,
  ErrorBox,
  Field,
  Metrics,
  Panel,
  ResultLinks,
  Table,
} from "./components";
import { useDraft } from "./editors";
import type { LabProps } from "./types";

export function Lab1({ job, busy, run }: LabProps) {
  const [mode, setMode] = useDraft("lab1-mode", "search"),
    [query, setQuery] = useDraft("lab1-query", "python programming"),
    [data, setData] = useState<any>({
      documents: [],
      queries: [],
      judgments: {},
    }),
    [selected, setSelected] = useState<number[]>([]),
    [url, setUrl] = useDraft("lab1-url", ""),
    [title, setTitle] = useDraft("lab1-title", ""),
    [text, setText] = useDraft("lab1-text", ""),
    [error, setError] = useState(""),
    [k1, setK1] = useDraft("lab1-k1", 1.5),
    [b, setB] = useDraft("lab1-b", 0.75);
  useEffect(() => {
    let current = true;
    api("/api/lab1/data?query=" + encodeURIComponent(query))
      .then((v) => {
        if (current) {
          setData(v);
          setError("");
        }
      })
      .catch((e) => {
        if (current) setError(e.message);
      });
    return () => {
      current = false;
    };
  }, [job?.status, query]);
  const result = job?.status === "completed" ? job.result : null;
  const doRun = (body: any) => run({ ...body, k1, b });
  const check = (id: number, on: boolean) =>
    setSelected((old) => (on ? [...old, id] : old.filter((v) => v !== id)));
  return (
    <>
      <div className="subnav">
        {[
          ["search", "Поиск"],
          ["collection", "Коллекция"],
          ["quality", "Оценка качества"],
        ].map(([id, name]) => (
          <button
            key={id}
            className={mode === id ? "active" : ""}
            onClick={() => setMode(id)}
          >
            {name}
          </button>
        ))}
      </div>
      <ErrorBox error={error} />
      {mode === "search" && (
        <Panel
          title="Поиск в коллекции"
          description="BM25 ранжирует документы по английскому запросу."
        >
          <div className="search-row">
            <input
              aria-label="Поисковый запрос"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void doRun({ action: "search", query });
              }}
            />
            <Action
              busy={busy}
              onClick={() => void doRun({ action: "search", query })}
            >
              Найти
            </Action>
          </div>
          <details className="advanced">
            <summary>Параметры BM25</summary>
            <div className="form-row">
              <Field label="k1">
                <input
                  type="number"
                  min="0.1"
                  max="10"
                  step="0.1"
                  value={k1}
                  onChange={(e) => setK1(+e.target.value)}
                />
              </Field>
              <Field label="b">
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.05"
                  value={b}
                  onChange={(e) => setB(+e.target.value)}
                />
              </Field>
            </div>
          </details>
          <p className="muted">
            В коллекции {data.documents.length} документов. Для первого опыта
            загрузите демо.
          </p>
          <Action
            secondary
            busy={busy}
            onClick={() => void doRun({ action: "demo" })}
          >
            Загрузить демо-коллекцию
          </Action>
        </Panel>
      )}
      {mode === "collection" && (
        <>
          <div className="workspace-grid">
            <Panel title="Добавить интернет-страницу">
              <Field label="URL страницы">
                <input
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://example.org/article"
                />
              </Field>
              <Action
                busy={busy}
                onClick={() => void doRun({ action: "import", url })}
              >
                Загрузить страницу
              </Action>
              <details className="advanced">
                <summary>Добавить текст вручную</summary>
                <Field label="Заголовок">
                  <input
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                  />
                </Field>
                <Field label="Текст на английском">
                  <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                  />
                </Field>
                <Action
                  busy={busy}
                  onClick={() =>
                    void doRun({ action: "add", url, title, text })
                  }
                >
                  Добавить документ
                </Action>
              </details>
            </Panel>
            <Panel title="Ваша коллекция">
              <Metrics
                values={[
                  ["Документы", data.documents.length],
                  ["Размеченные запросы", data.queries.length],
                ]}
              />
              <Action
                busy={busy}
                onClick={() => void doRun({ action: "demo" })}
              >
                Загрузить демо
              </Action>
              <p>
                Демо добавляет 12 документов и экспертные оценки для пяти
                запросов.
              </p>
            </Panel>
          </div>
          <Panel title="Документы">
            <Table
              heads={["", "Документ", "Слов", "Действие"]}
              rows={data.documents.map((d: any) => [
                <input
                  aria-label={"Выбрать " + d.title}
                  type="checkbox"
                  checked={selected.includes(d.id)}
                  onChange={(e) => check(d.id, e.target.checked)}
                />,
                <div>
                  <strong>{d.title}</strong>
                  <small className="block muted">{d.url}</small>
                </div>,
                d.length,
                <button
                  className="text-button"
                  disabled={busy}
                  onClick={() => void doRun({ action: "document", id: d.id })}
                >
                  Текст и ключевые слова
                </button>,
              ])}
            />
            <button
              className="button danger"
              disabled={busy || !selected.length}
              onClick={() => {
                if (confirm("Удалить выбранные документы и их оценки?")) {
                  void doRun({ action: "delete", ids: selected });
                  setSelected([]);
                }
              }}
            >
              Удалить выбранные ({selected.length})
            </button>
          </Panel>
        </>
      )}
      {mode === "quality" && (
        <Panel
          title="Экспертная оценка и метрики"
          description="Для расчёта оцените всю коллекцию по выбранному запросу: 0 — нерелевантен, 1 — частично, 2 — релевантен."
        >
          <Field label="Запрос">
            <input
              list="queries"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <datalist id="queries">
              {data.queries.map((q: string) => (
                <option key={q} value={q} />
              ))}
            </datalist>
          </Field>
          <Table
            heads={["Документ", "Оценка"]}
            rows={data.documents.map((d: any) => [
              d.title,
              <select
                aria-label={"Оценка " + d.title}
                disabled={busy}
                value={data.judgments[d.id] ?? ""}
                onChange={(e) =>
                  void doRun({
                    action: "grade",
                    query,
                    ids: [d.id],
                    grade: +e.target.value,
                  })
                }
              >
                <option value="" disabled>
                  Не оценён
                </option>
                {[0, 1, 2].map((g) => (
                  <option key={g}>{g}</option>
                ))}
              </select>,
            ])}
          />
          <div className="button-row">
            <Action
              busy={busy}
              onClick={() =>
                void doRun({ action: "evaluate", queries: [query] })
              }
            >
              Оценить запрос
            </Action>
            <Action
              secondary
              busy={busy}
              onClick={() => void doRun({ action: "evaluate" })}
            >
              Оценить все запросы
            </Action>
          </div>
        </Panel>
      )}
      <Panel title="Результат">
        {!result ? (
          <Empty />
        ) : (
          <>
            {result.message && <p>{result.message}</p>}
            {result.kind === "search" && (
              <>
                {result.rows.length ? (
                  result.rows.map((row: any, i: number) => (
                    <article className="search-result" key={row.document.id}>
                      <div className="result-rank">{i + 1}</div>
                      <div>
                        <button
                          className="result-title"
                          onClick={() =>
                            void doRun({
                              action: "document",
                              id: row.document.id,
                            })
                          }
                        >
                          {row.document.title}
                        </button>
                        <a
                          className="source-link"
                          href={row.document.url}
                          target="_blank"
                          rel="noopener"
                        >
                          {row.document.url}
                        </a>
                        <p>{row.document.text.slice(0, 320)}…</p>
                        <div className="tags">
                          {row.matched_words.map((word: string) => (
                            <span key={word}>{word}</span>
                          ))}
                          <small>BM25: {Number(row.score).toFixed(4)}</small>
                        </div>
                      </div>
                    </article>
                  ))
                ) : (
                  <p>По запросу ничего не найдено.</p>
                )}
              </>
            )}
            {result.document && (
              <>
                <h3>{result.document.title}</h3>
                <a
                  className="source-link"
                  href={result.document.url}
                  target="_blank"
                  rel="noopener"
                >
                  Открыть источник ↗
                </a>
                {result.keywords && (
                  <div className="tags">
                    {result.keywords.map((k: any) => (
                      <span title={"Вес " + k.weight} key={k.term}>
                        {k.term}
                      </span>
                    ))}
                  </div>
                )}
                <pre className="document-text">{result.document.text}</pre>
              </>
            )}
            {result.kind === "evaluation" && (
              <>
                <Metrics
                  values={Object.entries(result.data.averages).map(
                    ([name, value]) => [name, Number(value).toFixed(4)],
                  )}
                />
                <img
                  className="analysis-image"
                  src={result.report.replace("report.html", "mean_pr.svg")}
                  alt="Средняя precision-recall кривая"
                />
                <Table
                  heads={["Запрос", "Порядок документов"]}
                  rows={result.data.rows.map((r: any) => [
                    r.query,
                    r.ranking.join(" → "),
                  ])}
                />
              </>
            )}
            <ResultLinks result={result} />
          </>
        )}
      </Panel>
    </>
  );
}
