import { useRef, useState } from "react";
import {
  Action,
  AudioResult,
  Empty,
  ErrorBox,
  Field,
  Files,
  Metrics,
  Panel,
  ResultLinks,
  Table,
} from "./components";
import { ContourEditor, useDraft } from "./editors";
import type { LabProps } from "./types";

export function AudioLabs({ lab, catalog, job, busy, run }: LabProps) {
  const [source, setSource] = useDraft(
      `lab${lab}-source`,
      lab === 6 ? "student" : "vowels",
    ),
    [file, setFile] = useDraft<any>(`lab${lab}-file`, null),
    [start, setStart] = useDraft(`lab${lab}-start`, lab === 6 ? 2.41 : 0),
    [end, setEnd] = useDraft(`lab${lab}-end`, lab === 6 ? 4.49 : 0.24),
    [repeat, setRepeat] = useDraft(`lab${lab}-repeat`, 50),
    [action, setAction] = useDraft(`lab${lab}-action`, "analyze"),
    [seconds, setSeconds] = useDraft(`lab${lab}-seconds`, 5),
    [method, setMethod] = useDraft(`lab${lab}-method`, "psola"),
    [semitones, setSemitones] = useDraft(`lab${lab}-semitones`, 0),
    [prefix, setPrefix] = useDraft(`lab${lab}-prefix`, "word"),
    [controls, setControls] = useDraft(
      `lab${lab}-controls`,
      '{\n  "pitch_points": [[0, 100], [2.08, 130]],\n  "duration_points": [],\n  "gain": []\n}',
    ),
    [recipe, setRecipe] = useDraft(`lab${lab}-recipe`, "ref1_syllables"),
    [crossfade, setCrossfade] = useDraft(`lab${lab}-crossfade`, 0),
    [error, setError] = useState(""),
    [segment, setSegment] = useDraft(
      `lab${lab}-segment`,
      lab === 6 ? "student_phrase" : "",
    );
  const audio = useRef<HTMLAudioElement>(null);
  const result = job?.status === "completed" ? job.result : null;
  const base = { source, upload: file?.id, start, end };
  const segments = (catalog?.segments || []).filter((s: any) =>
    lab === 6 ? s.kind === "word" || s.id === "student_phrase" : true,
  );
  async function submit() {
    setError("");
    try {
      if (lab === 5) await run({ ...base, action, repeat, seconds });
      else if (lab === 6)
        await run({
          ...base,
          action: action === "permutations" ? "permutations" : "prosody",
          method,
          semitones,
          prefix,
          segment,
          controls: JSON.parse(controls),
        });
      else await run({ recipe, crossfade_ms: crossfade });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }
  function selectSegment(id: string) {
    setSegment(id);
    const s = segments.find((s: any) => s.id === id);
    if (s) {
      setSource(s.file.replace(/\.wav$/, ""));
      setStart(+s.start);
      setEnd(+s.end);
      setFile(null);
    }
  }
  return (
    <>
      <div className="workspace-grid">
        <Panel
          title={lab === 7 ? "Сборка фразы" : "Исходная запись"}
          description={
            lab === 7
              ? "Используется подтверждённый банк звуков и слогов."
              : "Выберите сохранённую запись или загрузите свой WAV."
          }
        >
          {lab !== 7 ? (
            <>
              <Files
                accept=".wav"
                onFiles={(files) => {
                  setFile(files[0]);
                  setSegment("");
                }}
              />
              {file ? (
                <p>
                  {file.name}{" "}
                  <button className="text-button" onClick={() => setFile(null)}>
                    Снять выбор
                  </button>
                </p>
              ) : (
                <>
                  <Field label="Запись">
                    <select
                      value={source}
                      onChange={(e) => {
                        setSource(e.target.value);
                        setSegment("");
                      }}
                    >
                      {catalog?.sources.map((s: any) => (
                        <option key={s.id} value={s.id}>
                          {s.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Подтверждённый фрагмент">
                    <select
                      value={segment}
                      onChange={(e) => selectSegment(e.target.value)}
                    >
                      <option value="">Целая запись / свои границы</option>
                      {segments.map((s: any) => (
                        <option key={s.id} value={s.id}>
                          {s.id} · {s.file} · {s.start}–{s.end} с
                        </option>
                      ))}
                    </select>
                  </Field>
                </>
              )}
              <audio
                ref={audio}
                controls
                src={file?.url || "/files/lab5_7/data/raw/" + source + ".wav"}
              />
              <div className="form-row">
                <Field label="Начало, с">
                  <input
                    type="number"
                    min={0}
                    step=".001"
                    value={start}
                    onChange={(e) => setStart(+e.target.value)}
                  />
                </Field>
                <Field label="Конец, с">
                  <input
                    type="number"
                    min={0}
                    step=".001"
                    value={end}
                    onChange={(e) => setEnd(+e.target.value)}
                  />
                </Field>
              </div>
              <button
                className="text-button"
                onClick={() => {
                  if (audio.current) {
                    audio.current.currentTime = start;
                    audio.current.ontimeupdate = () => {
                      if (audio.current && audio.current.currentTime >= end)
                        audio.current.pause();
                    };
                    void audio.current.play().catch((e) => setError(e.message));
                  }
                }}
              >
                Прослушать выбранный диапазон
              </button>
            </>
          ) : (
            <>
              <Field label="Рецепт">
                <select
                  value={recipe}
                  onChange={(e) => setRecipe(e.target.value)}
                >
                  {catalog?.recipes.map((r: any) => (
                    <option key={r.id} value={r.id}>
                      {r.text} · {r.id.endsWith("phones") ? "Фонемы" : "Слоги"}
                    </option>
                  ))}
                </select>
              </Field>
              <Field
                label="Перекрытие стыков, мс"
                hint="0 — прямая склейка. Перекрытие уменьшает длительность и может смазывать согласные."
              >
                <input
                  type="number"
                  min={0}
                  max={50}
                  step=".5"
                  value={crossfade}
                  onChange={(e) => setCrossfade(+e.target.value)}
                />
              </Field>
              <div className="notice">
                Утверждение и вопрос с одинаковыми единицами требуют отдельного
                управления просодикой. Сама склейка не восстанавливает
                интонацию.
              </div>
            </>
          )}
        </Panel>
        <Panel title="Параметры эксперимента">
          {lab === 5 && (
            <>
              <Field label="Операция">
                <select
                  value={action}
                  onChange={(e) => setAction(e.target.value)}
                >
                  <option value="analyze">Полный анализ записи</option>
                  <option value="crop">
                    Вырезать выбранный диапазон и проанализировать
                  </option>
                  <option value="loop">Повторить выбранный диапазон</option>
                  <option value="quality">Сравнить 4–32 кГц и 8/16 бит</option>
                  <option value="record">Новая запись микрофона</option>
                </select>
              </Field>
              {action === "loop" && (
                <Field label="Число повторов">
                  <input
                    type="number"
                    min={1}
                    max={2000}
                    value={repeat}
                    onChange={(e) => setRepeat(+e.target.value)}
                  />
                </Field>
              )}
              {action === "record" && (
                <>
                  <Field label="Длительность записи, с">
                    <input
                      type="number"
                      min={0.5}
                      max={60}
                      value={seconds}
                      onChange={(e) => setSeconds(+e.target.value)}
                    />
                  </Field>
                  <p className="notice">
                    Кнопка ниже включает стандартный микрофон на указанное
                    время. Запись сохраняется в новом опыте.
                  </p>
                </>
              )}
              <p className="muted">
                Короткое окно шума при повторении создаёт искусственную
                периодичность. Его нельзя считать собственным периодом
                фрикативного согласного.
              </p>
            </>
          )}
          {lab === 6 && (
            <>
              <Field label="Операция">
                <select
                  value={action}
                  onChange={(e) => setAction(e.target.value)}
                >
                  <option value="prosody">Изменить просодику</option>
                  <option value="permutations">Шесть перестановок слов</option>
                </select>
              </Field>
              {action === "permutations" ? (
                <Field label="Группа слов">
                  <select
                    value={prefix}
                    onChange={(e) => setPrefix(e.target.value)}
                  >
                    <option value="word">Отдельно произнесённые слова</option>
                    <option value="stress1">Выделено «Саша»</option>
                    <option value="stress2">Выделено «кушал»</option>
                    <option value="stress3">Выделено «кашу»</option>
                  </select>
                </Field>
              ) : (
                <>
                  <Field label="Метод">
                    <select
                      value={method}
                      onChange={(e) => setMethod(e.target.value)}
                    >
                      <option value="psola">
                        Praat PSOLA: высота и длительность отдельно
                      </option>
                      <option value="coupled">
                        Связанное изменение скорости
                      </option>
                      <option value="coupled_contour">
                        Переменная скорость по точкам
                      </option>
                    </select>
                  </Field>
                  {method === "coupled" && (
                    <Field label="Сдвиг, полутоны">
                      <input
                        type="number"
                        min={-12}
                        max={12}
                        step=".5"
                        value={semitones}
                        onChange={(e) => setSemitones(+e.target.value)}
                      />
                    </Field>
                  )}
                  <ContourEditor
                    value={controls}
                    onChange={setControls}
                    method={method}
                  />
                </>
              )}
            </>
          )}
          {lab === 7 && (
            <>
              <h3>Последовательность единиц</h3>
              <div className="tags">
                {catalog?.recipes
                  .find((r: any) => r.id === recipe)
                  ?.units.map((u: string, i: number) => (
                    <span key={i}>{u}</span>
                  ))}
              </div>
              <p className="muted">
                Это упрощённый учебный алфавит. Редукции и межфонемная
                коартикуляция автоматически не восстанавливаются.
              </p>
            </>
          )}
          <ErrorBox error={error} />
          <Action busy={busy} onClick={() => void submit()}>
            {lab === 7
              ? "Собрать и проанализировать"
              : lab === 5 && action === "record"
                ? "Включить микрофон и записать"
                : "Выполнить эксперимент"}
          </Action>
        </Panel>
      </div>
      <Panel title="Результат эксперимента">
        {result ? (
          <>
            {result.kind === "audio" && <AudioResult result={result} />}
            {result.kind === "quality" && (
              <Table
                heads={[
                  "Формат",
                  "Размер, байт",
                  "SNR квантования, дБ",
                  "Прослушивание",
                ]}
                rows={result.data.results.map((r: any) => [
                  r.rate + " Гц / " + r.bits + " бит",
                  r.bytes,
                  r.quantization_snr_db == null
                    ? "—"
                    : r.quantization_snr_db.toFixed(2),
                  <audio controls src={r.audio} />,
                ])}
              />
            )}
            {result.kind === "playlist" &&
              result.rows.map((r: any) => (
                <div className="playlist-item" key={r.audio}>
                  <span>{r.title}</span>
                  <audio controls src={r.audio} />
                </div>
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

export function Lab8({ job, busy, run }: LabProps) {
  const [text, setText] = useDraft(
      "lab8-text",
      "La langue française ouvre les portes de la littérature. Victor Hugo est un grand écrivain français.",
    ),
    [voice, setVoice] = useDraft("lab8-voice", "siwis"),
    [speed, setSpeed] = useDraft("lab8-speed", 1),
    [volume, setVolume] = useDraft("lab8-volume", 0.8),
    [file, setFile] = useDraft<any>("lab8-file", null);
  const result = job?.status === "completed" ? job.result : null;
  return (
    <>
      <div className="workspace-grid">
        <Panel title="Французский текст">
          <Files accept=".txt" onFiles={(files) => setFile(files[0])} />
          {file && (
            <p>
              {file.name}{" "}
              <button className="text-button" onClick={() => setFile(null)}>
                Использовать поле текста
              </button>
            </p>
          )}
          <Field
            label="Текст для чтения"
            hint="До 5000 символов. WAV сохраняется отдельно для каждого опыта."
          >
            <textarea
              lang="fr"
              disabled={!!file}
              value={text}
              onChange={(e) => setText(e.target.value)}
              maxLength={5000}
            />
          </Field>
          <Action
            busy={busy}
            onClick={() =>
              void run({ text, upload: file?.id, voice, speed, volume })
            }
          >
            Синтезировать речь
          </Action>
        </Panel>
        <Panel title="Голос и звучание">
          <Field label="Французский голос">
            <select value={voice} onChange={(e) => setVoice(e.target.value)}>
              <option value="siwis">Siwis</option>
              <option value="tom">Tom</option>
            </select>
          </Field>
          <Field label={"Темп · " + speed.toFixed(2) + "×"}>
            <input
              type="range"
              min={0.5}
              max={2}
              step={0.05}
              value={speed}
              onChange={(e) => setSpeed(+e.target.value)}
            />
          </Field>
          <Field label={"Громкость · " + Math.round(volume * 100) + "%"}>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={volume}
              onChange={(e) => setVolume(+e.target.value)}
            />
          </Field>
          <p>
            Синтез выполняется локально Piper. Первый запуск загружает голос в
            память.
          </p>
        </Panel>
      </div>
      <Panel title="Готовая речь">
        {result ? (
          <>
            <audio controls src={result.audio} />
            <Metrics
              values={[
                ["Длительность", result.data.duration.toFixed(2) + " с"],
                ["Частота", result.data.sample_rate + " Гц"],
                ["Голос", result.data.settings.voice],
                ["Синтез", result.data.synthesis_seconds.toFixed(2) + " с"],
              ]}
            />
            <p lang="fr">{result.data.text}</p>
            <a className="button" href={result.audio} download>
              Скачать WAV
            </a>
            <ResultLinks result={result} />
          </>
        ) : (
          <Empty />
        )}
      </Panel>
    </>
  );
}
