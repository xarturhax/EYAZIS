"""Статические пояснения и векторная схема для печатного отчёта."""

FLOWCHART = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 350" role="img"
aria-label="Алгоритм распознавания языка">
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3"
orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#315b83"/></marker></defs>
<g fill="#eef4fa" stroke="#315b83" stroke-width="2">
<rect x="300" y="5" width="400" height="45" rx="8"/>
<rect x="260" y="75" width="480" height="45" rx="8"/>
<rect x="20" y="160" width="280" height="50" rx="8"/>
<rect x="360" y="160" width="280" height="50" rx="8"/>
<rect x="700" y="160" width="280" height="50" rx="8"/>
<rect x="260" y="250" width="480" height="45" rx="8"/>
<path d="M500 50 V72 M500 120 V140 H160 V157 M500 140 V157 M500 140 H840 V157
M160 210 V230 H500 V247 M500 210 V247 M840 210 V230 H500"
fill="none" marker-end="url(#arrow)"/>
</g><g text-anchor="middle" font-family="sans-serif" font-size="16" fill="#172338">
<text x="500" y="33">PDF → текст → проверка train/test</text>
<text x="500" y="103">Языковые профили: обучение только на train</text>
<text x="160" y="190">Короткие слова: log-оценка</text>
<text x="500" y="190">Частоты букв: L1</text>
<text x="840" y="190">Символьный TF-IDF → MLP</text>
<text x="500" y="278">Предсказания на test → метрики → отчёт</text>
<text x="500" y="330">Эталонный язык test используется только для оценки качества</text>
</g></svg>"""

ARCHITECTURE = """<h2>Структура системы и данных</h2>
<p>GUI Tkinter и CLI вызывают единый сервис Experiment. Предметный слой содержит
модели, частотные классификаторы и метрики; инфраструктурные адаптеры читают PDF,
обучают MLP и сохраняют отчёт. Bootstrap собирает зависимости через небольшие
Protocol-контракты. Длительные задачи GUI выполняются в потоке с очередью сообщений.</p>
<p>CorpusEntry: путь, роль, эталонный язык, источник. Document: текст, число страниц,
хеш. Prediction: выбранный язык, оценки и объяснение. ResultRow: результат одного PDF.
ExperimentReport: параметры, профили, времена, метрики и версии библиотек.
JSON-манифест заменяет базу данных для этой небольшой коллекции.</p>
<h2>Схема алгоритма</h2><img src="algorithm.svg" alt="Схема трёх методов">
<h2>Используемые библиотеки</h2>
<p>pypdf извлекает текст; scikit-learn реализует TF-IDF и MLP; NumPy/SciPy выполняют
численные операции; Matplotlib строит диаграммы; ReportLab создаёт учебные PDF.
Tkinter, JSON, CSV и logging обеспечивают интерфейс, хранение и диагностику.</p>
<p>Документация:
<a href="https://pypdf.readthedocs.io/en/stable/user/extract-text.html">pypdf</a>,
<a href="https://scikit-learn.org/stable/modules/neural_networks_supervised.html">MLP</a>.
Исходники демо и лицензии находятся в data/demo/sources, библиография — provenance.json.</p>"""
