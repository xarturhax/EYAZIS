import {
  Children,
  cloneElement,
  isValidElement,
  useId,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";
import {
  Upload,
  ArrowUpRight,
  Download,
  LoaderCircle,
  X,
  FileText,
  Play,
} from "lucide-react";
import { api, upload, active, type Job } from "./api";

export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {Children.map(children, (child) =>
        isValidElement(child) &&
        ["input", "select", "textarea"].includes(String(child.type))
          ? cloneElement(child as ReactElement<any>, {
              id,
              "aria-describedby": hint ? id + "-hint" : undefined,
            })
          : child,
      )}
      {hint && <small id={id + "-hint"}>{hint}</small>}
    </div>
  );
}
export function Panel({
  title,
  description,
  children,
  className = "",
}: {
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={"panel " + className}>
      <h2>{title}</h2>
      {description && <p>{description}</p>}
      {children}
    </section>
  );
}
export function Action({
  children,
  busy,
  onClick,
  secondary = false,
  disabled = false,
}: {
  children: ReactNode;
  busy?: boolean;
  onClick: () => void;
  secondary?: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      className={"button " + (secondary ? "" : "primary")}
      disabled={busy || disabled}
      onClick={onClick}
    >
      {busy ? <LoaderCircle className="spin" size={16} /> : <Play size={14} />}{" "}
      {children}
    </button>
  );
}
export function Empty({
  text = "Запустите эксперимент — здесь появятся результаты.",
}: {
  text?: string;
}) {
  return (
    <div className="result-placeholder">
      <FileText size={30} />
      <h3>Пока нет результата</h3>
      <p>{text}</p>
    </div>
  );
}
export function ErrorBox({ error }: { error: string }) {
  return error ? (
    <div className="error" role="alert">
      {error}
    </div>
  ) : null;
}
export function Files({
  accept,
  multiple = false,
  onFiles,
}: {
  accept: string;
  multiple?: boolean;
  onFiles: (files: any[]) => void;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function add(files: FileList | null) {
    if (!files) return;
    setBusy(true);
    setError("");
    try {
      const results = [];
      for (const file of Array.from(files)) {
        const result = await upload(file);
        results.push({
          ...result,
          upload: result.id,
          title: result.name,
          split: "test",
          language: "en",
          domain: "art",
          source_id: "",
        });
      }
      onFiles(results);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <label
        className={"file-drop " + (busy ? "uploading" : "")}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          if (!busy) void add(e.dataTransfer.files);
        }}
      >
        <Upload size={23} />
        <strong>
          {busy ? "Загрузка…" : "Выберите файл или перетащите сюда"}
        </strong>
        <span>{accept.replaceAll(".", "").toUpperCase()} · до 50 МиБ</span>
        <input
          type="file"
          accept={accept}
          multiple={multiple}
          disabled={busy}
          onChange={(e) => {
            void add(e.target.files);
            e.target.value = "";
          }}
        />
      </label>
      <ErrorBox error={error} />
    </>
  );
}
export function Progress({
  job,
  onChange,
}: {
  job?: Job;
  onChange: () => void;
}) {
  const [error, setError] = useState("");
  if (!job) return null;
  return (
    <>
      <div className={"job-strip " + job.status} role="status">
        {active(job) ? (
          <LoaderCircle className="spin" size={18} />
        ) : (
          <span className="status-dot" />
        )}
        <div>
          <strong>{job.message}</strong>
          <small>Опыт {job.id.slice(0, 8)}</small>
        </div>
        {active(job) && (
          <button
            className="icon-button"
            aria-label="Отменить операцию"
            onClick={() => {
              api("/api/jobs/" + job.id + "/cancel", {})
                .then(onChange)
                .catch((e) => setError(e.message));
            }}
          >
            <X size={18} />
          </button>
        )}
        {job.status === "completed" && (
          <a className="button" href={"/api/jobs/" + job.id + "/archive"}>
            <Download size={14} /> Скачать всё
          </a>
        )}
      </div>
      <ErrorBox error={job.error || error} />
    </>
  );
}
export function ResultLinks({ result }: { result: any }) {
  if (!result) return null;
  return (
    <div className="result-links">
      {result.report && (
        <a
          className="button"
          href={result.report}
          target="_blank"
          rel="noopener"
        >
          Отчёт и печать <ArrowUpRight size={15} />
        </a>
      )}
      {result.json && (
        <a className="button" href={result.json} download>
          <Download size={14} /> JSON
        </a>
      )}
    </div>
  );
}
export function Metrics({ values }: { values: [string, ReactNode][] }) {
  return (
    <div className="metrics">
      {values.map(([name, value]) => (
        <div className="metric" key={name}>
          <span>{name}</span>
          <strong>{value}</strong>
        </div>
      ))}
    </div>
  );
}
export function Table({
  heads,
  rows,
}: {
  heads: string[];
  rows: ReactNode[][];
}) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {heads.map((h, i) => (
              <th key={i}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((value, j) => (
                <td key={j}>{value}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && (
        <p className="table-empty">Нет данных для отображения.</p>
      )}
    </div>
  );
}
export function AudioResult({ result }: { result: any }) {
  return (
    <>
      <div className="audio-pair">
        {result.source_audio && (
          <div>
            <span className="eyebrow">ИСХОДНИК / ЭТАЛОН</span>
            <audio controls src={result.source_audio} />
          </div>
        )}
        <div>
          <span className="eyebrow">РЕЗУЛЬТАТ</span>
          <audio controls src={result.audio} />
        </div>
      </div>
      <Metrics
        values={[
          ["Длительность", Number(result.data.duration).toFixed(3) + " с"],
          [
            "F0, медиана",
            result.data.f0_median_hz == null
              ? "Не определена"
              : Number(result.data.f0_median_hz).toFixed(2) + " Гц",
          ],
        ]}
      />
      {result.report && (
        <img
          className="analysis-image"
          src={result.report.replace("report.html", "contours.png")}
          alt="Осциллограмма, спектрограмма, F0 и RMS"
        />
      )}
      <p className="muted">
        RMS dBFS — цифровой уровень, а не физическая громкость. Отсутствие F0 не
        означает 0 Гц.
      </p>
    </>
  );
}
