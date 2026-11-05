# ЕЯЗиС — лабораторные работы

Девять самостоятельных приложений Tkinter. В каждой папке точка входа — `main.py`.

## Установка

Windows, Python 3.12. Все зависимости устанавливаются из одного файла:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

На текущем компьютере окружение и модели уже подготовлены. Для нового компьютера:

```powershell
.venv/Scripts/python.exe -m lab4.tools.download_model
.venv/Scripts/python.exe -m lab8.tools.download_voices
.venv/Scripts/python.exe -m lab9.tools.download_models
```

## Запуск и отчёты

В PyCharm выберите интерпретатор `.venv/Scripts/python.exe`, откройте нужный `main.py` и нажмите Run.
Из терминала: `.venv/Scripts/python.exe lab1/main.py` (замените номер).

| Лаба | Точка входа | Вариант | Word-отчёт |
|---|---|---|---|
| №1 | [main.py](lab1/main.py) | 36 | [Отчёт](lab1/reports/Отчет_ЛР1_вариант36.docx) |
| №2 | [main.py](lab2/main.py) | 36 | [Отчёт](lab2/reports/Отчет_ЛР2_вариант36.docx) |
| №3 | [main.py](lab3/main.py) | 27 | [Отчёт](lab3/reports/Отчет_ЛР3_вариант27.docx) |
| №4 | [main.py](lab4/main.py) | 12 | [Отчёт](lab4/reports/Отчет_ЛР4_вариант12.docx) |
| №5 | [main.py](lab5/main.py) | Общее задание | [Отчёт](lab5/reports/Отчет_ЛР5.docx) |
| №6 | [main.py](lab6/main.py) | Общее задание | [Отчёт](lab6/reports/Отчет_ЛР6.docx) |
| №7 | [main.py](lab7/main.py) | Общее задание | [Отчёт](lab7/reports/Отчет_ЛР7.docx) |
| №8 | [main.py](lab8/main.py) | 8 | [Отчёт](lab8/reports/Отчет_ЛР8_вариант8.docx) |
| №9 | [main.py](lab9/main.py) | 8 | [Отчёт](lab9/reports/Отчет_ЛР9_вариант8.docx) |

Отчёты и их материалы — в `labN/reports`. Исходный код — рядом с `main.py`; данные — в `data`, проверки — в `tests`.

№6–7 используют записи и разметку из `lab5/data`; №9 использует французские голоса №8. Коллекция поиска: `lab1/data/search.sqlite3`, словарь переводов: `lab4/data/lexicon.sqlite3`. Модели и личные записи в Git не включаются.

Проверки: `python -m unittest discover -s . -p "test_*.py"`.
