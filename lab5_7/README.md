# Лабораторные работы №5–7

Общий пакет **Praat + Python-утилиты** подготовлен.
**Собраны 25 записей, получены оценки восьми частотных/разрядностных вариантов.**
**Состояние на 29.10.2026:** подтверждены все 76 фрагментов. Получены все 60 исходных оценок №6 и восемь дополнительных; итоговые шесть примеров выбраны.
Работы №5–7 завершены в согласованном объёме: все запрошенные записи, разметка и оценки получены, отчёты заполнены. Необязательный пункт 3.3.6* исключён.
Сводка и выводы — в [отчёте №6](docs/LAB6_REPORT.md); повторять его 24 перестановки и 36 вариантов не нужно.
Материалы и полученные результаты:

- `reports/local/lab7_reference3_mama_v1/index.html` — оба исправленных варианта третьей фразы с «Мама» оценены: фонемы 3/1, слоги 5/4. Исходный JSON и комментарии сохранены; повторная оценка не нужна.
- `reports/local/phoneme_atlas_v1/index.html` — осциллограммы, спектры и WAV всех 42 подтверждённых звуков, повторная разметка не нужна.
- `reports/local/lab6_selected_examples/index.html` — шесть итоговых уже оценённых примеров: утверждение/вопрос с выделением каждого слова. Повторное заполнение оценок не требуется.
- `reports/local/lab6_question_focus_v1/index.html` — все четыре оценки получены: совместно распознаны вопрос и нужное слово, 5/4, замечания о скачках высоты сохранены.
- `reports/local/lab6_question_refinement_v1/index.html` — четыре оценки уже получены: концевой подъём дал вопрос, но сместил выделение на «реферат».
- `reports/local/lab6_source_observations_v1/index.html` — все 15 исходных просодических наблюдений уже получены и внесены в отчёт №6.
- `reports/local/lab5_comparisons_v1/index.html` — все 14 наблюдений уже получены и внесены в отчёт №5.
- `reports/local/lab7_repair_v1/index.html` — три обработанных варианта уже оценены; лучший слоговый получил 5/4 и сохранён в `selected/ref1_syllables_improved.wav`.
- `reports/local/t_diagnosis_v1/index.html` — сравнение «т»; пользователь выбрал второй кандидат.
- `reports/local/lab7_synthesis_v2/index.html` — базовые девять вариантов уже оценены, повторное прослушивание не требуется.
- `reports/local/lab5_phonetics_v1/index.html` — все 10 наблюдений уже получены: 6 гласных похожи, 4 шумовых цикла непохожи на исходник.

Разметка полностью подтверждена, включая уточнённый «р» длиной 101 мс.
В третьем эталоне пользователь подтвердил «Мама», оба рецепта и WAV исправлены.
Обе новые оценки получены. Дополнительная разметка и прослушивание не требуются;
замечания и неопределённые ответы в отчётах сохранены.

## Готовые инструменты

- Переносимый Praat: vendor/praat/Praat.exe; официальный URL и SHA-256 рядом.
- Список 25 записей: 15 основных, 2 другого диктора, 8 отдельных захватов для пункта 1.3.
- Полная временная разметка: все 76 единиц банка подтверждены пользователем.
- Анализ осциллограммы, спектрограммы, F0 и RMS dBFS, JSON/CSV/PNG/HTML и печать.
- Полосоограниченный ресемплинг, реальные WAV PCM_U8 и PCM_16.
- Нарезка, повтор периода, перестановки слов, сборка из фонем и слогов.
- Praat overlap-add для изменения F0 и длительности; отдельная смена скорости
  для связанного изменения высоты/длительности.
- Заполненные отчёты: [№5](docs/LAB5_REPORT.md), [№6](docs/LAB6_REPORT.md), [№7](docs/LAB7_REPORT.md).
- Необязательный пункт 3.3.6* исключён; обязательные опыты работы 6 сохранены.

Полный редактор не дублируется: слушаем и проверяем границы в Praat,
повторяемые численные операции выполняем Python-командами.
Исходники остаются в data/raw. Существующие WAV не перезаписываются.

## Запуск

```powershell
.venv\Scripts\python.exe -B -m lab5_7
.venv\Scripts\python.exe -B -m lab5_7 record vowels --seconds 40
```

Первая команда обновляет reports/status/index.html.
Вторая **явно включает микрофон** после отсчёта.
Зависимости и переносимый Praat в текущем окружении уже подготовлены.
Для новой установки: pip install -r lab5_7/requirements.txt,
затем python -B -m lab5_7.tools.download_praat.

## Анализ после получения записей

```powershell
.venv\Scripts\python.exe -B -m lab5_7 analyze lab5_7\data\raw\vowels.wav --output lab5_7\reports\vowels
.venv\Scripts\python.exe -B -m lab5_7 quality lab5_7\data\raw\quality.wav --output lab5_7\work\quality_run1
.venv\Scripts\python.exe -B -m lab5_7 extract lab5_7\data\raw\vowels.wav --start 2.1 --end 2.3 --output lab5_7\work\fragment.wav
```

**2.1–2.3 — пример синтаксиса, не найденные границы вашего звука.**
Времена определяются по реальной записи и прослушиванию.
Для повторения настоящего периода добавьте --repeat 200.
Для шума произвольное короткое окно не называется периодом.

В data/segments.csv внесите реальные времена и reviewed=yes после проверки.
Пустые/неподтверждённые интервалы в банк не входят.
Команда textgrid создаёт Praat-разметку из CSV; без имеющихся времён —
пустой уровень для ручной работы.
После правки в Praat времена переносятся в CSV, либо TextGrid передаётся
для дальнейшего разбора.

```powershell
.venv\Scripts\python.exe -B -m lab5_7 textgrid lab5_7\data\raw\vowels.wav --output lab5_7\work\vowels.TextGrid
.venv\Scripts\python.exe -B -m lab5_7 bank --output lab5_7\work\bank_run1
.venv\Scripts\python.exe -B -m lab5_7 permutations --bank lab5_7\work\bank_run1 --output lab5_7\work\permutations
```

Последовательности recipes.json проверены по плановым текстам в учебном алфавите,
статус REVIEWED. Перед сборкой должны быть подтверждены все используемые аудиоединицы:

```powershell
.venv\Scripts\python.exe -B -m lab5_7 assemble ref1_phones --bank lab5_7\work\bank_run1 --output lab5_7\work\phonemic.wav
.venv\Scripts\python.exe -B -m lab5_7 assemble ref1_syllables --bank lab5_7\work\bank_run1 --output lab5_7\work\syllabic.wav
```

Для эксперимента сглаживания добавьте --crossfade-ms 3 и новое имя результата.
Перекрытие меняет длительность и может смазать взрыв согласного:
улучшение не предполагается до прослушивания.

## Просодика

Скопируйте data/prosody_template.json, внесите настоящие точки и status=READY.
pitch_points: пары [время, F0 Гц]; duration_points: [время, множитель 0.5–2];
gain: [начало, конец, дБ] на временной шкале результата.

```powershell
.venv\Scripts\python.exe -B -m lab5_7 prosody lab5_7\data\raw\student.wav --controls lab5_7\work\student_controls.json --output lab5_7\work\student_modified.wav
```

psola изменяет заданные F0/длительность через Praat.
coupled_contour + rate_points задаёт переменную скорость; время точек относится к исходнику.
coupled + semitones — аналог постоянной смены скорости с изменением длительности,
не точная реализация графического Pitch Bend из Sound Forge.
Полный обязательный опыт описан в docs/LAB6_REPORT.md; 36 вариантов уже построены по проверенным словам.
Повторная сборка требует новой папки: `python -B -m lab5_7.tools.build_lab6 --output <новая_папка>`.

## Проверки

Импорт новых оценок: `python -B -m lab5_7.tools.import_listening <путь_к_JSON>`.
Проверяются манифест, WAV, идентификаторы и шкалы; исходный JSON, CSV и сводка
сохраняются в отдельной квитанции. Экспериментальные WAV и их results.json не изменяются.

```powershell
.venv\Scripts\python.exe -B -m unittest discover -s lab5_7/tests -t . -v
.venv\Scripts\python.exe -B -m lab5_7.tools.technical_demo
.venv\Scripts\python.exe -m ruff check lab5_7 --no-cache
.venv\Scripts\python.exe -B -m mypy lab5_7 --config-file lab5_7/pyproject.toml --no-incremental
```

Технические WAV находятся в work/technical, отчёты имеют TECHNICAL_TEST_ONLY.
Папка data/raw ими не заполняется.
Praat GUI 7.0.02 и движок Parselmouth 6.1.38 различаются;
их результаты не обязаны совпадать побитно.
Настройки F0 и версии фиксируются в метриках.
RMS dBFS не является dB SPL; отсутствие F0 хранится пустым значением, не нулём.
