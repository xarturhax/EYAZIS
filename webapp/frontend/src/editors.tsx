import { useEffect, useState } from "react";
import { Field, Table } from "./components";

export function ContourEditor({
  value,
  onChange,
  method,
}: {
  value: string;
  onChange: (value: string) => void;
  method: string;
}) {
  let model: any = {};
  try {
    model = JSON.parse(value);
  } catch {
    /* Advanced JSON errors are displayed on submit. */
  }
  const update = (key: string, rows: number[][]) =>
    onChange(JSON.stringify({ ...model, [key]: rows }, null, 2));
  const pointTable = (
    key: string,
    title: string,
    heads: string[],
    defaults: number[],
  ) => {
    const rows: number[][] = Array.isArray(model[key]) ? model[key] : [];
    return (
      <div className="contour-table">
        <h3>{title}</h3>
        <Table
          heads={[...heads, ""]}
          rows={rows.map((row, index) => [
            ...row.map((n, column) => (
              <input
                key={column}
                aria-label={title + " · " + heads[column] + " " + (index + 1)}
                type="number"
                step=".01"
                value={n}
                onChange={(e) =>
                  update(
                    key,
                    rows.map((r, i) =>
                      i === index
                        ? r.map((v, j) => (j === column ? +e.target.value : v))
                        : r,
                    ),
                  )
                }
              />
            )),
            <button
              className="text-button"
              onClick={() =>
                update(
                  key,
                  rows.filter((_, i) => i !== index),
                )
              }
            >
              Убрать
            </button>,
          ])}
        />
        <button
          className="text-button"
          onClick={() => {
            const next = [...defaults];
            if (rows.length)
              next[0] = +(rows[rows.length - 1][0] + 0.2).toFixed(3);
            update(key, [...rows, next]);
          }}
        >
          + Добавить точку
        </button>
      </div>
    );
  };
  return (
    <>
      {method === "psola" && (
        <>
          {pointTable(
            "pitch_points",
            "Высота голоса",
            ["Время, с", "F0, Гц"],
            [0, 100],
          )}
          {pointTable(
            "duration_points",
            "Длительность",
            ["Время, с", "Множитель"],
            [0, 1],
          )}
        </>
      )}
      {method === "coupled_contour" &&
        pointTable(
          "rate_points",
          "Скорость",
          ["Время, с", "Множитель"],
          [0, 1],
        )}
      {pointTable(
        "gain",
        "Усиление",
        ["Начало, с", "Конец, с", "Изменение, дБ"],
        [0, 1, 0],
      )}
      <p className="muted">
        Время точек отсчитывается от начала выбранного фрагмента. Интервалы
        усиления относятся к обработанному результату.
      </p>
      <details className="advanced">
        <summary>Расширенный ввод контуров</summary>
        <Field label="Параметры JSON">
          <textarea
            className="code-input"
            value={value}
            onChange={(e) => onChange(e.target.value)}
          />
        </Field>
      </details>
    </>
  );
}

const actions = [
  ["read", "Читать"],
  ["stop", "Остановить"],
  ["next", "Следующий абзац"],
  ["previous", "Предыдущий абзац"],
  ["repeat", "Повторить"],
  ["faster", "Быстрее"],
  ["slower", "Медленнее"],
];
export function CommandEditor({
  value,
  onChange,
  disabled,
}: {
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
}) {
  let model: any = {
    commands: [],
    threshold: 0.75,
    cooldown_seconds: 1.2,
    schema: 1,
  };
  try {
    if (value) model = JSON.parse(value);
  } catch {
    /* The server validates configuration before replacing the saved policy. */
  }
  const update = (next: any) =>
    onChange(JSON.stringify({ ...model, ...next }, null, 2));
  const rows = model.commands || [];
  function change(index: number, key: string, next: any) {
    update({
      commands: rows.map((r: any, i: number) =>
        i === index ? { ...r, [key]: next } : r,
      ),
    });
  }
  return (
    <fieldset disabled={disabled} className="command-editor">
      <div className="form-row">
        <Field label="Порог уверенности">
          <input
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={model.threshold}
            onChange={(e) => update({ threshold: +e.target.value })}
          />
        </Field>
        <Field label="Интервал повторных команд, с">
          <input
            type="number"
            min={0}
            max={10}
            step={0.1}
            value={model.cooldown_seconds}
            onChange={(e) => update({ cooldown_seconds: +e.target.value })}
          />
        </Field>
      </div>
      <Table
        heads={["Включена", "Язык", "Фраза", "Операция", ""]}
        rows={rows.map((row: any, i: number) => [
          <input
            aria-label={"Включить команду " + (i + 1)}
            type="checkbox"
            checked={row.enabled}
            onChange={(e) => change(i, "enabled", e.target.checked)}
          />,
          <select
            aria-label={"Язык команды " + (i + 1)}
            value={row.language}
            onChange={(e) => change(i, "language", e.target.value)}
          >
            <option value="fr">FR</option>
            <option value="en">EN</option>
          </select>,
          <input
            aria-label={"Фраза команды " + (i + 1)}
            value={row.phrase}
            onChange={(e) => change(i, "phrase", e.target.value)}
          />,
          <select
            aria-label={"Действие команды " + (i + 1)}
            value={row.action}
            onChange={(e) => change(i, "action", e.target.value)}
          >
            {actions.map(([key, name]) => (
              <option key={key} value={key}>
                {name}
              </option>
            ))}
          </select>,
          <button
            className="text-button"
            onClick={() =>
              update({
                commands: rows.filter((_: any, index: number) => index !== i),
              })
            }
          >
            Убрать
          </button>,
        ])}
      />
      <button
        className="text-button"
        onClick={() =>
          update({
            commands: [
              ...rows,
              {
                language: "fr",
                phrase: "lecteur nouvelle commande",
                action: "read",
                enabled: true,
              },
            ],
          })
        }
      >
        + Добавить команду
      </button>
      <p className="muted">
        Французская команда начинается с lecteur, английская — с reader.
        Совпасть должна фраза целиком.
      </p>
    </fieldset>
  );
}

export function useDraft<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const saved = sessionStorage.getItem("eyazis-draft-" + key);
      return saved ? JSON.parse(saved) : initial;
    } catch {
      return initial;
    }
  });
  useEffect(() => {
    try {
      sessionStorage.setItem("eyazis-draft-" + key, JSON.stringify(value));
    } catch {
      /* Browsers may restrict session storage. */
    }
  }, [key, value]);
  return [value, setValue] as const;
}
