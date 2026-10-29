"use strict";

// Design prototype: navigation works, calculations are intentionally not connected.
const labs = [
  {id:1, title:"Информационный поиск", short:"Поиск документов", group:"text", icon:"⌕", description:"Коллекция документов, поиск BM25 и оценка качества выдачи.", tags:"BM25 · Документы", input:"Поисковый запрос", sample:"python programming", action:"Найти документы", report:"../lab1/reports/demo/report.html", guide:"../lab1/README.md"},
  {id:2, title:"Определение языка", short:"Определение языка", group:"text", icon:"Aa", description:"Английский или испанский? Сравните три метода распознавания.", tags:"PDF · Классификация", input:"Документы для анализа", sample:"Перетащите PDF или выберите файлы", action:"Определить язык", report:"../lab2/reports/demo/report.html", guide:"../lab2/README.md"},
  {id:3, title:"Реферирование текста", short:"Реферирование", group:"text", icon:"≡", description:"Выделяйте ключевые слова и собирайте краткое содержание текста.", tags:"TextRank · Ключевые слова", input:"Исходный текст", sample:"Вставьте текст документа для получения краткого содержания…", action:"Создать реферат", report:"../lab3/reports/demo/report.html", guide:"../lab3/README.md"},
  {id:4, title:"Машинный перевод", short:"Перевод и анализ", group:"text", icon:"⇄", description:"Перевод с английского на французский и лингвистический анализ.", tags:"EN → FR · Словарь", input:"Текст на английском", sample:"Language connects people and makes knowledge accessible.", action:"Перевести", report:"../lab4/reports/demo/index.html", guide:"../lab4/README.md"},
  {id:5, title:"Фонетика и звук", short:"Фонетика", group:"speech", icon:"∿", description:"Исследуйте 42 звука: осциллограммы, спектры и периоды.", tags:"42 звука · Спектральный анализ", input:"Материал для исследования", sample:"Выберите звук из подтверждённого банка", action:"Исследовать звук", report:"../lab5_7/reports/local/phoneme_atlas_v1/index.html", guide:"../lab5_7/docs/LAB5_REPORT.md"},
  {id:6, title:"Интонация и просодика", short:"Интонация", group:"speech", icon:"⌁", description:"Меняйте высоту, длительность и выделение слов. Сравнивайте на слух.", tags:"F0 · PSOLA · Ударение", input:"Исходная фраза", sample:"Студент писал реферат.", action:"Применить обработку", report:"../lab5_7/reports/local/lab6_selected_examples/index.html", guide:"../lab5_7/docs/LAB6_REPORT.md"},
  {id:7, title:"Компиляционный синтез", short:"Сборка речи", group:"speech", icon:"⋈", description:"Собирайте речь из звуков и слогов, сравнивайте с эталоном.", tags:"Фонемы · Слоги · Стыки", input:"Фраза для синтеза", sample:"Саша кушал кашу, а Мама пила сок.", action:"Собрать фразу", report:"../lab5_7/reports/local/lab7_reference3_mama_v1/index.html", guide:"../lab5_7/docs/LAB7_REPORT.md", extra:"../lab5_7/reports/local/lab7_repair_v1/selected/index.html"},
  {id:8, title:"Синтез французской речи", short:"Синтез речи", group:"speech", icon:"▷", description:"Превращайте текст в речь. Выбирайте голос, темп и громкость.", tags:"Piper · FR · Два голоса", input:"Текст на французском", sample:"La langue française ouvre les portes de la littérature.", action:"Озвучить текст", report:"../lab8/reports/demo/index.html", guide:"../lab8/README.md"},
  {id:9, title:"Распознавание речи", short:"Распознавание", group:"speech", icon:"◉", description:"Распознавайте французскую речь и управляйте чтением голосом.", tags:"Vosk · Голосовые команды", input:"Источник звука", sample:"Микрофон или WAV-файл", action:"Начать распознавание", report:"../lab9/reports/demo/index.html", guide:"../lab9/README.md"}
];

const content = document.getElementById("content");
const navigation = document.getElementById("navigation");
const homeTemplate = document.getElementById("home-template");
const escapeHtml = value => String(value).replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[char]);
const number = id => String(id).padStart(2,"0");
let category = "all";

navigation.innerHTML = labs.map(lab => `<a href="#lab-${lab.id}" data-lab="${lab.id}" title="${escapeHtml(lab.title)}"><span class="nav-num">${number(lab.id)}</span><span class="nav-title">${lab.short}</span></a>`).join("");

function renderCards() {
  const query = document.getElementById("search").value.toLocaleLowerCase("ru").trim();
  const selected = labs.filter(lab => (category === "all" || lab.group === category) && `${lab.id} ${lab.title} ${lab.description} ${lab.tags}`.toLocaleLowerCase("ru").includes(query));
  document.getElementById("cards").innerHTML = selected.map(lab => `<a class="card ${lab.group}" href="#lab-${lab.id}"><div class="card-top"><span class="card-icon" aria-hidden="true">${lab.icon}</span><span class="card-number">ЛАБОРАТОРНАЯ ${number(lab.id)}</span></div><h3>${lab.title}</h3><p>${lab.description}</p><div class="card-bottom"><span>${lab.tags}</span><span class="card-arrow" aria-hidden="true">↗</span></div></a>`).join("");
  document.getElementById("empty").hidden = selected.length !== 0;
}

function showHome() {
  category = "all";
  content.replaceChildren(homeTemplate.content.cloneNode(true));
  document.getElementById("breadcrumb").innerHTML = "Учебный практикум <span>/</span> Обзор";
  document.getElementById("search").addEventListener("input",renderCards);
  document.querySelectorAll(".filter").forEach(button => button.addEventListener("click",() => {
    category = button.dataset.filter;
    document.querySelectorAll(".filter").forEach(item => {
      const active = item === button;
      item.classList.toggle("active",active);
      item.setAttribute("aria-pressed",String(active));
    });
    renderCards();
  }));
  renderCards();
}

function showWorkspace(lab) {
  document.getElementById("breadcrumb").innerHTML = `Учебный практикум <span>/</span> Лабораторная ${number(lab.id)}`;
  content.innerHTML = `<a class="back-link" href="#home">← Все лабораторные</a><div class="workspace-heading"><span class="card-icon" aria-hidden="true">${lab.icon}</span><div><p class="eyebrow">ЛАБОРАТОРНАЯ РАБОТА ${number(lab.id)}</p><h1>${lab.title}</h1><p>${lab.description}</p></div></div><div class="workspace-tabs" role="group" aria-label="Раздел работы"><button class="active" data-tab="experiment" aria-pressed="true">Эксперимент</button><button data-tab="materials" aria-pressed="false">Готовые материалы</button><button data-tab="help" aria-pressed="false">Как это работает</button></div><div class="demo-banner"><strong>Это интерактивный макет.</strong> Навигация и ссылки работают. Вычисления ещё не подключены; готовые материалы можно открыть в соседнем разделе.</div><section id="tab-content"></section>`;
  document.querySelectorAll("[data-tab]").forEach(button => button.addEventListener("click",() => {
    document.querySelectorAll("[data-tab]").forEach(item => {
      item.classList.toggle("active",item === button);
      item.setAttribute("aria-pressed",String(item === button));
    });
    renderTab(lab,button.dataset.tab);
  }));
  renderTab(lab,"experiment");
}

function renderTab(lab,tab) {
  const target = document.getElementById("tab-content");
  if (tab === "materials") {
    target.innerHTML = `<div class="panel"><h2>Материалы этой лабораторной</h2><p>Ссылки ведут к уже существующим результатам проекта.</p><a class="resource" href="${lab.report}" target="_blank" rel="noopener">Открыть результаты и примеры <span>↗</span></a>${lab.extra ? `<a class="resource" href="${lab.extra}" target="_blank" rel="noopener">Улучшенная первая фраза <span>↗</span></a>` : ""}<a class="resource" href="${lab.guide}" target="_blank" rel="noopener">Инструкция и описание работы <span>↗</span></a></div>`;
  } else if (tab === "help") {
    target.innerHTML = `<div class="panel"><h2>Рабочий сценарий</h2><ol class="help-list"><li>Добавьте исходные данные или выберите подготовленный пример.</li><li>Настройте параметры и запустите эксперимент.</li><li>Изучите результаты, графики и объяснения.</li><li>Сохраните материалы и отчёт для защиты.</li></ol><p>Этот сценарий предлагается для будущего приложения. В текущем макете вычисления и экспорт недоступны.</p></div>`;
  } else {
    const fileInput = [2,5,9].includes(lab.id);
    const editor = fileInput ? `<input id="source" type="file" disabled accept="${lab.id === 2 ? '.pdf' : '.wav'}"><p>${lab.sample}</p>` : lab.id === 1 ? `<input id="source" value="${escapeHtml(lab.sample)}">` : `<textarea id="source">${escapeHtml(lab.sample)}</textarea>`;
    target.innerHTML = `<div class="workspace-grid"><div class="panel"><h2>Исходные данные</h2><p>Подготовьте материал для эксперимента.</p><label class="field-label" for="source">${lab.input}</label>${editor}<label class="field-label" for="mode">Режим работы</label><select id="mode" disabled><option>Параметры лабораторной</option></select><button class="button primary" disabled title="Вычисления появятся после подключения Python">${lab.action} <span>↗</span></button></div><div class="panel"><h2>Результат</h2><p>Все результаты эксперимента — рядом с исходными данными.</p><div class="result-placeholder"><span aria-hidden="true">${lab.icon}</span><h3>Здесь появится результат</h3><p>После подключения Python здесь будут реальные данные, графики и действия для экспорта.</p></div></div></div>`;
  }
}

function route() {
  const match = /^#lab-([1-9])$/.exec(location.hash);
  const lab = match ? labs.find(item => item.id === Number(match[1])) : undefined;
  document.querySelectorAll("[data-lab]").forEach(item => {
    if (lab && Number(item.dataset.lab) === lab.id) item.setAttribute("aria-current","page");
    else item.removeAttribute("aria-current");
  });
  if (lab) showWorkspace(lab); else showHome();
  document.title = lab ? `${lab.title} — ЕЯЗиС` : "ЕЯЗиС — лаборатории языка и речи";
  window.scrollTo(0,0);
}

try {document.body.classList.toggle("dark",localStorage.getItem("eyazis-preview-theme") === "dark");} catch { /* File preview can restrict storage. */ }
document.getElementById("theme").addEventListener("click",() => {
  const dark = document.body.classList.toggle("dark");
  try {localStorage.setItem("eyazis-preview-theme",dark ? "dark" : "light");} catch { /* Theme still works in memory. */ }
});
window.addEventListener("hashchange",route);
route();
