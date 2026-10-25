# Лабораторные работы №5–7

Общий пакет **Praat + Python-утилиты** подготовлен.
**Речевые эксперименты ожидают записей пользователя.**
Начните с одного файла по [инструкции записи](docs/RECORDING_GUIDE.md).

## Готовые инструменты

- Переносимый Praat: vendor/praat/Praat.exe; официальный URL и SHA-256 рядом.
- Список 25 записей: 15 основных, 2 другого диктора, 8 отдельных захватов для пункта 1.3.
- Пустая временная разметка, 42 единицы учебного перечня фонем, слова/слоги/эталоны.
- Анализ осциллограммы, спектрограммы, F0 и RMS dBFS, JSON/CSV/PNG/HTML и печать.
- Полосоограниченный ресемплинг, реальные WAV PCM_U8 и PCM_16.
- Нарезка, повтор периода, перестановки слов, сборка из фонем и слогов.
- Praat overlap-add для изменения F0 и длительности; отдельная смена скорости
  для связанного изменения высоты/длительности.
- Отдельные отчёты-заготовки: LAB5_REPORT.md, LAB6_REPORT.md, LAB7_REPORT.md.
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

Проверьте recipes.json по произношению и замените статус рецепта на REVIEWED:

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
Полный обязательный опыт описан в docs/LAB6_REPORT.md и пока ожидает записи.

## Проверки

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
