import { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlignLeft,
  ArrowLeft,
  ArrowLeftRight,
  ArrowUpRight,
  AudioLines,
  BookOpen,
  FlaskConical,
  Grid2X2,
  Layers,
  Mic,
  Search,
  SunMoon,
  Volume2,
  History,
  ExternalLink,
} from "lucide-react";
import { api, active, type Job } from "./api";
import { labs } from "./catalog";
import { ErrorBox, Progress, Table } from "./components";
import { Lab1 } from "./Lab1";
import { Lab2, Lab3, Lab4 } from "./TextLabs";
import { AudioLabs, Lab8 } from "./AudioLabs";
import { Lab9 } from "./Lab9";
import "./styles.css";

const icons = [
  Search,
  LanguagesIcon,
  AlignLeft,
  ArrowLeftRight,
  AudioLines,
  Activity,
  Layers,
  Volume2,
  Mic,
];
function LanguagesIcon({ size = 21 }: { size?: number }) {
  return (
    <span style={{ fontSize: size, fontWeight: 600, lineHeight: 1 }}>Aa</span>
  );
}
const number = (value: number) => String(value).padStart(2, "0");

function App() {
  const [route, setRoute] = useState(location.hash || "#home"),
    [catalog, setCatalog] = useState<any>(null),
    [error, setError] = useState(""),
    [online, setOnline] = useState(false),
    [theme, setTheme] = useState(() => {
      try {
        return localStorage.getItem("eyazis-theme") || "light";
      } catch {
        return "light";
      }
    }),
    [jobs, setJobs] = useState<Record<number, Job>>({}),
    [history, setHistory] = useState<Job[]>([]),
    [tab, setTab] = useState("experiment"),
    [category, setCategory] = useState("all"),
    [query, setQuery] = useState(""),
    [requesting, setRequesting] = useState(false);
  const jobsRef = useRef(jobs);
  jobsRef.current = jobs;
  const requestLock = useRef(false);
  const labMatch = /^#lab-([1-9])$/.exec(route),
    lab = labMatch ? Number(labMatch[1]) : 0;
  const meta = labs.find((item) => item.id === lab);
  const current = jobs[lab];
  const busy = requesting || active(current);
  const refreshHistory = useCallback(
    () =>
      api<Job[]>("/api/jobs")
        .then(setHistory)
        .catch((e) => setError(e.message)),
    [],
  );
  useEffect(() => {
    const changed = () => {
      setRoute(location.hash || "#home");
      setTab("experiment");
      setError("");
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", changed);
    return () => window.removeEventListener("hashchange", changed);
  }, []);
  useEffect(() => {
    document.body.classList.toggle("dark", theme === "dark");
    try {
      localStorage.setItem("eyazis-theme", theme);
    } catch {
      /* Private browser storage may be disabled. */
    }
  }, [theme]);
  useEffect(() => {
    let valid = true;
    api("/api/catalog")
      .then((c) => {
        if (valid) {
          setCatalog(c);
          setOnline(true);
        }
      })
      .catch((e) => {
        if (valid) setError(e.message);
      });
    api<Job[]>("/api/jobs")
      .then(async (rows) => {
        if (!valid) return;
        setHistory(rows);
        const latest: Record<number, Job> = {};
        for (const row of rows) {
          if (!latest[row.lab])
            latest[row.lab] = await api<Job>("/api/jobs/" + row.id);
        }
        if (valid) setJobs(latest);
      })
      .catch((e) => {
        if (valid) setError(e.message);
      });
    return () => {
      valid = false;
    };
  }, []);
  useEffect(() => {
    let valid = true,
      polling = false;
    const timer = setInterval(async () => {
      if (polling) return;
      polling = true;
      try {
        for (const job of Object.values(jobsRef.current)) {
          if (active(job)) {
            const state = await api<Job>("/api/jobs/" + job.id);
            if (!valid) return;
            setJobs((old) =>
              old[job.lab]?.id === state.id
                ? { ...old, [job.lab]: state }
                : old,
            );
            if (!active(state)) void refreshHistory();
          }
        }
        if (valid) setOnline(true);
      } catch (e) {
        if (valid) {
          setOnline(false);
          setError(e instanceof Error ? e.message : String(e));
        }
      } finally {
        polling = false;
      }
    }, 800);
    return () => {
      valid = false;
      clearInterval(timer);
    };
  }, [refreshHistory]);
  const run = async (body: any, targetLab = lab) => {
    if (requestLock.current) return undefined;
    requestLock.current = true;
    setRequesting(true);
    setError("");
    try {
      const job = await api<Job>("/api/labs/" + targetLab + "/run", body);
      setJobs((old) => ({ ...old, [targetLab]: job }));
      void refreshHistory();
      return job;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return undefined;
    } finally {
      requestLock.current = false;
      setRequesting(false);
    }
  };
  const props = { lab, catalog, job: current, busy, run };
  const selected = labs.filter(
    (l) =>
      (category === "all" || l.group === category) &&
      `${l.id} ${l.title} ${l.description} ${l.tags}`
        .toLocaleLowerCase("ru")
        .includes(query.toLocaleLowerCase("ru").trim()),
  );
  const Workspace =
    lab === 1
      ? Lab1
      : lab === 2
        ? Lab2
        : lab === 3
          ? Lab3
          : lab === 4
            ? Lab4
            : lab === 8
              ? Lab8
              : lab === 9
                ? Lab9
                : AudioLabs;
  return (
    <>
      <aside className="sidebar">
        <a className="brand" href="#home">
          <span className="brand-mark">е.</span>
          <span>
            ЕЯЗиС<small>Язык. Данные. Голос.</small>
          </span>
        </a>
        <div className="nav-label">РАБОЧЕЕ ПРОСТРАНСТВО</div>
        <a className="home-link" href="#home">
          <Grid2X2 size={19} /> Обзор лабораторных
        </a>
        <div className="nav-label labs-label">ЛАБОРАТОРНЫЕ РАБОТЫ</div>
        <nav aria-label="Лабораторные">
          {labs.map((item) => (
            <a
              key={item.id}
              href={"#lab-" + item.id}
              aria-current={item.id === lab ? "page" : undefined}
              title={item.title}
            >
              <span className="nav-num">{number(item.id)}</span>
              <span className="nav-title">{item.short}</span>
              {active(jobs[item.id]) && <span className="nav-running" />}
            </a>
          ))}
        </nav>
        <a className="history-link" href="#history">
          <History size={16} /> История экспериментов
        </a>
        <div className="sidebar-bottom">
          <span className={"status-dot " + (!online ? "offline" : "")} />
          <div>
            {online ? "Сервер доступен" : "Подключение к серверу…"}
            <small>Локально на вашем компьютере</small>
          </div>
        </div>
      </aside>
      <div className="shell">
        <header className="topbar">
          <div>
            Учебный практикум <span>/</span>{" "}
            {meta
              ? "Лабораторная " + number(lab)
              : route === "#history"
                ? "История"
                : "Обзор"}
          </div>
          <div className="top-actions">
            <span className="preview-pill">Локальное приложение</span>
            <button
              className="theme-button"
              aria-label="Сменить тему"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            >
              <SunMoon size={21} />
            </button>
          </div>
        </header>
        <main>
          <ErrorBox error={error} />
          {meta ? (
            <>
              <a className="back-link" href="#home">
                <ArrowLeft size={14} /> Все лабораторные
              </a>
              <div className="workspace-heading">
                <span className="card-icon">
                  {(() => {
                    const Icon = icons[lab - 1];
                    return <Icon size={27} />;
                  })()}
                </span>
                <div>
                  <p className="eyebrow">ЛАБОРАТОРНАЯ РАБОТА {number(lab)}</p>
                  <h1>{meta.title}</h1>
                  <p>{meta.description}</p>
                </div>
              </div>
              <div
                className="workspace-tabs"
                role="group"
                aria-label="Раздел работы"
              >
                {[
                  ["experiment", "Эксперимент"],
                  ["materials", "Готовые материалы"],
                  ["help", "Как это работает"],
                ].map(([key, label]) => (
                  <button
                    key={key}
                    className={tab === key ? "active" : ""}
                    aria-pressed={tab === key}
                    onClick={() => setTab(key)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <Progress
                job={current}
                onChange={() => {
                  if (current)
                    api<Job>("/api/jobs/" + current.id)
                      .then((j) => setJobs((old) => ({ ...old, [lab]: j })))
                      .catch((e) => setError(e.message));
                }}
              />
              {tab === "experiment" ? (
                catalog ? (
                  <Workspace key={lab} {...props} />
                ) : (
                  <p>Загрузка материалов…</p>
                )
              ) : tab === "materials" ? (
                <section className="panel">
                  <h2>Материалы лабораторной</h2>
                  <p>
                    Сохранённые отчёты и примеры проекта. Веб-опыты доступны в
                    истории.
                  </p>
                  {catalog?.materials[lab]?.map((item: any) => (
                    <div className="resource" key={item.url}>
                      {item.available ? (
                        <a href={item.url} target="_blank" rel="noopener">
                          {item.title} <ExternalLink size={14} />
                        </a>
                      ) : (
                        <span>
                          {item.title} · отсутствует на этом компьютере
                        </span>
                      )}
                    </div>
                  ))}
                  <a className="button" href="#history">
                    История веб-экспериментов <ArrowUpRight size={14} />
                  </a>
                </section>
              ) : (
                <section className="panel">
                  <h2>Порядок работы</h2>
                  <ol className="help-list">
                    <li>Выберите демо или загрузите исходные файлы.</li>
                    <li>Настройте параметры и запустите эксперимент.</li>
                    <li>
                      Следите за этапами над формой; длительную операцию можно
                      отменить.
                    </li>
                    <li>Изучите данные, сравните графики или аудио.</li>
                    <li>
                      Откройте отчёт для печати или скачайте весь опыт в ZIP.
                    </li>
                  </ol>
                  <p>
                    Результаты сохраняются на этом компьютере в
                    webapp/work/jobs. История остаётся доступной после
                    перезапуска. Модели загружаются по мере обращения к
                    лабораторным.
                  </p>
                  {catalog?.materials[lab]
                    ?.filter((m: any) => m.url.endsWith(".md") && m.available)
                    .map((m: any) => (
                      <a
                        key={m.url}
                        className="button"
                        target="_blank"
                        rel="noopener"
                        href={m.url}
                      >
                        <BookOpen size={15} /> {m.title}
                      </a>
                    ))}
                </section>
              )}
            </>
          ) : route === "#history" ? (
            <>
              <p className="eyebrow">СОХРАНЁННЫЕ РЕЗУЛЬТАТЫ</p>
              <h1>История экспериментов</h1>
              <p className="muted">
                Каждый запуск имеет отдельный каталог. Исходные файлы
                сохраняются.
              </p>
              <section className="panel">
                <button
                  className="button"
                  onClick={() => void refreshHistory()}
                >
                  Обновить
                </button>
                <Table
                  heads={["Время", "Лабораторная", "Операция", "Состояние", ""]}
                  rows={history.map((item) => [
                    new Date(item.created_at).toLocaleString("ru-RU"),
                    item.lab,
                    item.action,
                    item.message,
                    <button
                      className="text-button"
                      onClick={() => {
                        api<Job>("/api/jobs/" + item.id)
                          .then((job) => {
                            setJobs((old) => ({ ...old, [item.lab]: job }));
                            location.hash = "lab-" + item.lab;
                            setTab("experiment");
                          })
                          .catch((e) => setError(e.message));
                      }}
                    >
                      Открыть опыт ↗
                    </button>,
                  ])}
                />
              </section>
            </>
          ) : (
            <>
              <section className="hero">
                <div>
                  <p className="eyebrow">ВАШ УЧЕБНЫЙ ПРАКТИКУМ</p>
                  <h1>
                    Исследуйте язык.
                    <br />
                    <span>Экспериментируйте с речью.</span>
                  </h1>
                  <p className="hero-description">
                    Девять лабораторных, одно рабочее пространство.
                    <br />
                    От поиска документов до распознавания голоса.
                  </p>
                  <a className="button primary hero-button" href="#lab-1">
                    Открыть первую лабораторную <ArrowUpRight size={17} />
                  </a>
                </div>
                <div className="hero-art" aria-hidden="true">
                  <div className="art-label">TEXT → SIGNAL → MEANING</div>
                  <svg viewBox="0 0 300 180" fill="none">
                    <path
                      className="art-grid"
                      d="M0 45H300M0 90H300M0 135H300M60 0V180M120 0V180M180 0V180M240 0V180"
                    />
                    <path
                      className="art-wave"
                      d="M0 90H25L30 83L35 98L40 69L45 113L50 45L55 137L60 64L65 109L70 86L75 94H95L100 74L105 109L110 48L115 131L120 22L125 154L130 57L135 120L140 76L145 99L150 87L155 90H170L175 79L180 108L185 53L190 126L195 69L200 105L205 85L210 94H235L240 80L245 104L250 66L255 114L260 80L265 96H300"
                    />
                    <circle cx="120" cy="22" r="5" />
                  </svg>
                  <div className="art-footer">
                    <span>а → слово → смысл</span>
                    <span>01 — 09</span>
                  </div>
                </div>
              </section>
              <section className="catalogue">
                <div className="section-top">
                  <div>
                    <p className="eyebrow">ВЫБЕРИТЕ НАПРАВЛЕНИЕ</p>
                    <h2>
                      Лабораторные работы <span className="count">09</span>
                    </h2>
                  </div>
                  <label className="search-box">
                    <Search size={16} />
                    <input
                      aria-label="Найти лабораторную"
                      type="search"
                      placeholder="Найти лабораторную…"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  </label>
                </div>
                <div className="filters" role="group" aria-label="Направление">
                  {[
                    ["all", "Все работы"],
                    ["text", "Текст и язык"],
                    ["speech", "Голос и звук"],
                  ].map(([key, label]) => (
                    <button
                      key={key}
                      className={"filter " + (category === key ? "active" : "")}
                      aria-pressed={category === key}
                      onClick={() => setCategory(key)}
                    >
                      {label}
                      {key !== "all" && <span>{key === "text" ? 4 : 5}</span>}
                    </button>
                  ))}
                </div>
                <div className="cards">
                  {selected.map((item) => {
                    const Icon = icons[item.id - 1];
                    return (
                      <a
                        className={"card " + item.group}
                        href={"#lab-" + item.id}
                        key={item.id}
                      >
                        <div className="card-top">
                          <span className="card-icon">
                            <Icon size={21} />
                          </span>
                          <span className="card-number">
                            ЛАБОРАТОРНАЯ {number(item.id)}
                          </span>
                        </div>
                        <h3>{item.title}</h3>
                        <p>{item.description}</p>
                        <div className="card-bottom">
                          <span>{item.tags}</span>
                          <ArrowUpRight size={17} />
                        </div>
                      </a>
                    );
                  })}
                </div>
                {!selected.length && (
                  <p className="empty">По вашему запросу ничего не найдено.</p>
                )}
              </section>
              <section className="concept-note">
                <FlaskConical size={27} />
                <div>
                  <h3>Один привычный сценарий для каждой работы</h3>
                  <p>
                    Открыть данные → настроить эксперимент → получить результат
                    → сохранить отчёт.
                  </p>
                </div>
                <a className="note-end" href="#history">
                  История экспериментов ↗
                </a>
              </section>
            </>
          )}
        </main>
        <footer>
          <span>Естественно-языковые системы</span>
          <span>Всё для работы с текстом и речью</span>
        </footer>
      </div>
    </>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
