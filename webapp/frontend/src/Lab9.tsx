import { useEffect, useRef, useState } from "react";
import { api, active, downloadJson, type Job } from "./api";
import {
  Action,
  Empty,
  ErrorBox,
  Field,
  Files,
  Metrics,
  Panel,
  ResultLinks,
  Table,
} from "./components";
import { CommandEditor, useDraft } from "./editors";
import type { LabProps } from "./types";

export function Lab9({ busy, job, run }: LabProps) {
  const [language, setLanguage] = useDraft("lab9-language", "fr"),
    [device, setDevice] = useState(""),
    [devices, setDevices] = useState<any[]>([]),
    [live, setLive] = useState<any>({
      active: false,
      message: "Микрофон выключен",
    }),
    [events, setEvents] = useState<any[]>([]),
    [execute, setExecute] = useState(false),
    [file, setFile] = useState<any>(null),
    [reference, setReference] = useState(""),
    [error, setError] = useState(""),
    [policy, setPolicy] = useState(""),
    [notice, setNotice] = useState(""),
    [text, setText] = useDraft(
      "lab9-text",
      "La littérature nous aide à comprendre le monde.\n\nVictor Hugo est un grand écrivain français.",
    ),
    [position, setPosition] = useState(0),
    [speed, setSpeed] = useDraft("lab9-speed", 1),
    [voice, setVoice] = useDraft("lab9-voice", "siwis"),
    [speaking, setSpeaking] = useState(false),
    [playerUrl, setPlayerUrl] = useState("");
  const player = useRef<HTMLAudioElement>(null),
    epoch = useRef(0),
    pending = useRef<string | null>(null),
    paused = useRef(false),
    after = useRef(0),
    mounted = useRef(true),
    applyRef = useRef<(action: string) => void>(() => {});
  const result = job?.status === "completed" ? job.result : null;
  const paragraphs = text
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean);
  function stopReading() {
    epoch.current++;
    player.current?.pause();
    paused.current = false;
    setSpeaking(false);
    if (pending.current) {
      void api("/api/jobs/" + pending.current + "/cancel", {}).catch(() => {});
      pending.current = null;
    }
  }
  async function speak() {
    stopReading();
    const version = epoch.current;
    if (!paragraphs[position]) {
      setNotice("Добавьте текст для чтения.");
      return;
    }
    paused.current = true;
    setSpeaking(true);
    try {
      if (live.active) await api("/api/live/heartbeat", { paused: true });
      const created = await run(
        { text: paragraphs[position], voice, speed, volume: 0.8 },
        8,
      );
      if (!created) {
        paused.current = false;
        setSpeaking(false);
        return;
      }
      pending.current = created.id;
      let state: Job = created;
      while (active(state) && mounted.current && epoch.current === version) {
        await new Promise((resolve) => setTimeout(resolve, 600));
        state = await api<Job>("/api/jobs/" + created.id);
      }
      if (epoch.current !== version || !mounted.current) {
        void api("/api/jobs/" + created.id + "/cancel", {}).catch(() => {});
        return;
      }
      pending.current = null;
      if (state.status !== "completed")
        throw new Error(state.error || state.message);
      setPlayerUrl(state.result.audio);
      if (player.current) {
        player.current.src = state.result.audio;
        await player.current.play();
      }
    } catch (e) {
      if (mounted.current && epoch.current === version) {
        setError(e instanceof Error ? e.message : String(e));
        paused.current = false;
        setSpeaking(false);
      }
    }
  }
  applyRef.current = (action: string) => {
    if (action === "stop") {
      stopReading();
      setNotice("Чтение остановлено.");
      return;
    }
    if (action === "read" || action === "repeat") {
      void speak();
      return;
    }
    stopReading();
    if (action === "next")
      setPosition((p) => Math.min(Math.max(0, paragraphs.length - 1), p + 1));
    if (action === "previous") setPosition((p) => Math.max(0, p - 1));
    if (action === "faster")
      setSpeed((s) => Math.min(2, +(s + 0.1).toFixed(2)));
    if (action === "slower")
      setSpeed((s) => Math.max(0.5, +(s - 0.1).toFixed(2)));
    setNotice("Команда выполнена: " + action);
  };
  const executeRef = useRef(execute);
  executeRef.current = execute;
  useEffect(() => {
    mounted.current = true;
    let polling = false;
    api("/api/commands")
      .then((p) => {
        if (mounted.current) setPolicy(JSON.stringify(p, null, 2));
      })
      .catch((e) => setError(e.message));
    async function poll() {
      if (polling) return;
      polling = true;
      try {
        const state = await api("/api/live?after=" + after.current);
        if (!mounted.current) return;
        setLive(state);
        after.current = state.sequence;
        if (state.events.length) {
          setEvents((old) => [...old, ...state.events].slice(-300));
          for (const event of state.events) {
            if (
              event.final &&
              event.status === "ACCEPTED" &&
              event.action &&
              executeRef.current
            )
              applyRef.current(event.action);
          }
        }
        if (state.active)
          await api("/api/live/heartbeat", { paused: paused.current });
      } catch (e) {
        if (mounted.current)
          setError(e instanceof Error ? e.message : String(e));
      } finally {
        polling = false;
      }
    }
    void poll();
    const timer = setInterval(() => void poll(), 700);
    return () => {
      mounted.current = false;
      clearInterval(timer);
      epoch.current++;
      player.current?.pause();
      if (pending.current)
        void api("/api/jobs/" + pending.current + "/cancel", {}).catch(
          () => {},
        );
      void api("/api/live/stop", {}).catch(() => {});
    };
  }, []);
  async function toggle() {
    setError("");
    try {
      if (live.active) {
        const state = await api("/api/live/stop", {});
        setLive(state);
      } else {
        const previous = await api("/api/live");
        after.current = previous.sequence;
        const state = await api("/api/live/start", {
          language,
          device: device === "" ? null : +device,
        });
        setLive(state);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }
  return (
    <>
      <ErrorBox error={error} />
      <div className="workspace-grid">
        <Panel title="Распознавание речи">
          <div className="form-row">
            <Field label="Язык ASR">
              <select
                value={language}
                disabled={live.active}
                onChange={(e) => setLanguage(e.target.value)}
              >
                <option value="fr">Французский</option>
                <option value="en">Английский</option>
              </select>
            </Field>
            <Field label="Микрофон">
              <select
                value={device}
                disabled={live.active}
                onChange={(e) => setDevice(e.target.value)}
              >
                <option value="">Устройство Windows по умолчанию</option>
                {devices.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <button
            className="text-button"
            onClick={() => {
              api("/api/devices")
                .then(setDevices)
                .catch((e) => setError(e.message));
            }}
          >
            Обновить список микрофонов
          </button>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={execute}
              onChange={(e) => setExecute(e.target.checked)}
            />{" "}
            Выполнять принятые голосовые команды
          </label>
          <div className={"microphone-state " + (live.active ? "on" : "")}>
            <span className="status-dot" />
            {live.message}
            {live.active && live.paused && " · пауза на время чтения"}
          </div>
          <Action onClick={() => void toggle()}>
            {live.active ? "Прекратить распознавание" : "Включить микрофон"}
          </Action>
          <p className="muted">
            Аудио микрофона в файл не записывается. Во время синтеза и
            воспроизведения распознавание приостанавливается. Закрытие страницы
            остановит микрофон автоматически.
          </p>
          <details className="advanced">
            <summary>Проверить WAV без выполнения команд</summary>
            <Files accept=".wav" onFiles={(files) => setFile(files[0])} />
            <p>
              {file?.name ||
                "Без файла будет использован подготовленный синтетический пример tom_read.wav."}
            </p>
            <Field label="Эталонная расшифровка для WER (необязательно)">
              <input
                value={reference}
                onChange={(e) => setReference(e.target.value)}
              />
            </Field>
            <Action
              busy={busy}
              onClick={() =>
                void run({ upload: file?.id, language, reference })
              }
            >
              Распознать WAV
            </Action>
          </details>
        </Panel>
        <Panel title="Чтение по голосовым командам">
          <Field label="Французский текст — пустая строка разделяет абзацы">
            <textarea
              value={text}
              maxLength={5000}
              onChange={(e) => {
                stopReading();
                setText(e.target.value);
                setPosition(0);
              }}
            />
          </Field>
          <div className="form-row">
            <Field label="Голос">
              <select
                value={voice}
                onChange={(e) => {
                  stopReading();
                  setVoice(e.target.value);
                }}
              >
                <option value="siwis">Siwis</option>
                <option value="tom">Tom</option>
              </select>
            </Field>
            <Field label="Темп">
              <input
                type="number"
                min={0.5}
                max={2}
                step={0.1}
                value={speed}
                onChange={(e) => {
                  stopReading();
                  setSpeed(+e.target.value);
                }}
              />
            </Field>
          </div>
          <Field
            label={
              "Абзац " +
              (paragraphs.length ? position + 1 : 0) +
              " / " +
              paragraphs.length
            }
          >
            <select
              value={position}
              onChange={(e) => {
                stopReading();
                setPosition(+e.target.value);
              }}
            >
              {paragraphs.map((p, i) => (
                <option key={i} value={i}>
                  {i + 1}. {p.slice(0, 80)}
                </option>
              ))}
            </select>
          </Field>
          <div className="button-row">
            <Action busy={speaking} onClick={() => void speak()}>
              Прочитать
            </Action>
            <button className="button" onClick={stopReading}>
              Стоп
            </button>
            <button
              className="button"
              onClick={() => applyRef.current("previous")}
            >
              ← Абзац
            </button>
            <button className="button" onClick={() => applyRef.current("next")}>
              Абзац →
            </button>
          </div>
          <audio
            ref={player}
            controls
            src={playerUrl || undefined}
            onPlay={() => {
              paused.current = true;
              setSpeaking(true);
            }}
            onPause={() => {
              paused.current = false;
              setSpeaking(false);
            }}
            onEnded={() => {
              paused.current = false;
              setSpeaking(false);
            }}
          />
          {notice && <p role="status">{notice}</p>}
        </Panel>
      </div>
      <Panel title="Журнал и команды">
        <Table
          heads={["Фраза", "Уверенность", "Решение", "Команда"]}
          rows={events.map((e) => [
            e.text,
            e.confidence == null ? "—" : e.confidence.toFixed(3),
            e.final ? e.status : "Промежуточно",
            e.action || "—",
          ])}
        />
        <div className="button-row">
          <button
            className="button"
            onClick={() => downloadJson(events, "live-recognition.json")}
          >
            Скачать журнал JSON
          </button>
          <Action
            secondary
            busy={busy}
            onClick={() => void run({ action: "journal", rows: events })}
          >
            Экспорт HTML / CSV
          </Action>
          <button className="button" onClick={() => setEvents([])}>
            Очистить экран
          </button>
        </div>
        <details className="advanced">
          <summary>Настроить фразы, операции и порог уверенности</summary>
          <CommandEditor
            value={policy}
            onChange={setPolicy}
            disabled={live.active}
          />
          <button
            className="button"
            disabled={live.active}
            onClick={() => {
              try {
                api("/api/commands", JSON.parse(policy))
                  .then(() => setNotice("Настройки команд сохранены."))
                  .catch((e) => setError(e.message));
              } catch (e) {
                setError(String(e));
              }
            }}
          >
            Сохранить настройки
          </button>
          <p className="muted">
            Перед изменением настроек остановите распознавание. Изменения
            сохраняются в рабочем каталоге веб-приложения.
          </p>
        </details>
      </Panel>
      <Panel title="Результат проверки WAV / экспорт">
        {result ? (
          <>
            {result.kind === "recognition" && (
              <>
                <p className="transcript">
                  {result.text || "Речь не распознана."}
                </p>
                {result.audio && <audio controls src={result.audio} />}
                {result.wer && (
                  <Metrics
                    values={[
                      ["WER", (result.wer.wer * 100).toFixed(1) + "%"],
                      ["Ошибки", result.wer.errors],
                      ["Слов в эталоне", result.wer.reference_words],
                    ]}
                  />
                )}
                <Table
                  heads={["Фраза", "Уверенность", "Решение", "Пояснение"]}
                  rows={result.rows.map((r: any) => [
                    r.text,
                    r.confidence == null ? "—" : r.confidence.toFixed(3),
                    r.status,
                    r.message,
                  ])}
                />
                <p className="muted">
                  Проверка WAV не выполняет голосовые команды.
                </p>
              </>
            )}
            <ResultLinks result={result} />
          </>
        ) : (
          <Empty />
        )}
      </Panel>
    </>
  );
}
