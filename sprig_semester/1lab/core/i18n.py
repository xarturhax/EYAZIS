"""Simple i18n module. Call set_language('en'|'ru') then t('key') everywhere."""

_LANG = "en"

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        # App
        "app_title": "English Dictionary Builder",
        # Menu — File
        "menu_file": "File",
        "menu_open": "Open TXT/RTF...",
        "menu_save": "Save Dictionary",
        "menu_save_as": "Save Dictionary As...",
        "menu_load": "Load Dictionary...",
        "menu_export_csv": "Export to CSV...",
        "menu_exit": "Exit",
        # Menu — Edit
        "menu_edit": "Edit",
        "menu_add": "Add Entry...",
        "menu_edit_entry": "Edit Entry...",
        "menu_delete": "Delete Entry",
        "menu_clear": "Clear Dictionary",
        # Menu — Search
        "menu_search": "Search",
        "menu_search_cmd": "Search...",
        "menu_filter_freq": "Filter by Frequency...",
        "menu_show_all": "Show All",
        # Menu — View
        "menu_view": "View",
        "menu_language": "Language",
        # Menu — Help
        "menu_help": "Help",
        "menu_guide": "User Guide",
        "menu_about": "About",
        # Toolbar
        "tb_open": "Open",
        "tb_save": "Save",
        "tb_load": "Load",
        "tb_export": "Export CSV",
        "tb_add": "Add",
        "tb_edit": "Edit",
        "tb_delete": "Delete",
        "tb_show_all": "Show All",
        "tb_help": "Help",
        # Search bar
        "search_label": "Search:",
        "search_clear": "Clear",
        # Table columns
        "col_lemma": "Lemma",
        "col_wordform": "Wordform",
        "col_frequency": "Frequency",
        "col_morphology": "Morphology",
        # Edit dialog
        "dlg_add_title": "Add Entry",
        "dlg_edit_title": "Edit Entry",
        "dlg_lemma": "Lemma:",
        "dlg_wordform": "Wordform:",
        "dlg_frequency": "Frequency:",
        "dlg_morphology": "Morphology:",
        "dlg_ok": "OK",
        "dlg_cancel": "Cancel",
        "dlg_val_lemma": "Lemma cannot be empty.",
        "dlg_val_wordform": "Wordform cannot be empty.",
        "dlg_val_freq": "Frequency must be a non-negative integer.",
        "dlg_val_title": "Validation",
        # Filter dialog
        "flt_title": "Filter by Frequency",
        "flt_min": "Min frequency:",
        "flt_max": "Max frequency:",
        "flt_hint": "(leave blank for no limit)",
        "flt_apply": "Apply",
        "flt_input_err": "Input error",
        "flt_not_int": "is not an integer.",
        # Context menu
        "ctx_edit": "Edit",
        "ctx_delete": "Delete",
        # Status
        "status_ready": "Ready",
        "status_reading": "Reading",
        "status_analysing": "Analysing text...",
        "status_loaded_file": "Loaded",
        "status_wordforms": "wordforms",
        "status_lemmas": "lemmas",
        "status_saved": "Saved to",
        "status_exported": "Exported to",
        "status_deleted": "Deleted",
        "status_updated": "Updated",
        "status_added": "Added",
        "status_cleared": "Dictionary cleared.",
        "status_showing": "Showing",
        "status_of": "of",
        # Dialogs
        "msg_edit_select": "Please select a row first.",
        "msg_edit_title": "Edit",
        "msg_delete_confirm": "Delete wordform",
        "msg_delete_of": "of",
        "msg_delete_q": "?",
        "msg_delete_title": "Delete",
        "msg_clear_confirm": "Clear the entire dictionary?",
        "msg_clear_title": "Clear",
        "msg_error_title": "Error",
        "msg_error_open": "Error opening file.",
        "msg_export_title": "Export",
        "msg_export_done": "Dictionary exported to:",
        "msg_about_title": "About",
        "msg_about_body": (
            "English Dictionary Builder\n"
            "Laboratory Work #1, Variant 13\n\n"
            "Builds an alphabetical dictionary (lemmas + wordforms)\n"
            "with frequency counts and morphological notes.\n\n"
            "Input formats: TXT, RTF"
        ),
        # Help dialog
        "help_title": "Help — English Dictionary Builder",
        "help_close": "Close",
    },
    "ru": {
        # App
        "app_title": "Построитель словаря английского языка",
        # Menu — File
        "menu_file": "Файл",
        "menu_open": "Открыть TXT/RTF...",
        "menu_save": "Сохранить словарь",
        "menu_save_as": "Сохранить словарь как...",
        "menu_load": "Загрузить словарь...",
        "menu_export_csv": "Экспорт в CSV...",
        "menu_exit": "Выход",
        # Menu — Edit
        "menu_edit": "Правка",
        "menu_add": "Добавить запись...",
        "menu_edit_entry": "Редактировать запись...",
        "menu_delete": "Удалить запись",
        "menu_clear": "Очистить словарь",
        # Menu — Search
        "menu_search": "Поиск",
        "menu_search_cmd": "Найти...",
        "menu_filter_freq": "Фильтр по частоте...",
        "menu_show_all": "Показать всё",
        # Menu — View
        "menu_view": "Вид",
        "menu_language": "Язык",
        # Menu — Help
        "menu_help": "Справка",
        "menu_guide": "Руководство пользователя",
        "menu_about": "О программе",
        # Toolbar
        "tb_open": "Открыть",
        "tb_save": "Сохранить",
        "tb_load": "Загрузить",
        "tb_export": "Экспорт CSV",
        "tb_add": "Добавить",
        "tb_edit": "Изменить",
        "tb_delete": "Удалить",
        "tb_show_all": "Показать всё",
        "tb_help": "Справка",
        # Search bar
        "search_label": "Поиск:",
        "search_clear": "Сбросить",
        # Table columns
        "col_lemma": "Лексема",
        "col_wordform": "Словоформа",
        "col_frequency": "Частота",
        "col_morphology": "Морфология",
        # Edit dialog
        "dlg_add_title": "Добавить запись",
        "dlg_edit_title": "Редактировать запись",
        "dlg_lemma": "Лексема:",
        "dlg_wordform": "Словоформа:",
        "dlg_frequency": "Частота:",
        "dlg_morphology": "Морфология:",
        "dlg_ok": "ОК",
        "dlg_cancel": "Отмена",
        "dlg_val_lemma": "Лексема не может быть пустой.",
        "dlg_val_wordform": "Словоформа не может быть пустой.",
        "dlg_val_freq": "Частота должна быть неотрицательным целым числом.",
        "dlg_val_title": "Ошибка ввода",
        # Filter dialog
        "flt_title": "Фильтр по частоте",
        "flt_min": "Минимальная частота:",
        "flt_max": "Максимальная частота:",
        "flt_hint": "(оставьте пустым для отсутствия ограничения)",
        "flt_apply": "Применить",
        "flt_input_err": "Ошибка ввода",
        "flt_not_int": "не является целым числом.",
        # Context menu
        "ctx_edit": "Редактировать",
        "ctx_delete": "Удалить",
        # Status
        "status_ready": "Готово",
        "status_reading": "Чтение файла",
        "status_analysing": "Анализ текста...",
        "status_loaded_file": "Загружен файл",
        "status_wordforms": "словоформ",
        "status_lemmas": "лексем",
        "status_saved": "Сохранено в",
        "status_exported": "Экспортировано в",
        "status_deleted": "Удалено",
        "status_updated": "Обновлено",
        "status_added": "Добавлено",
        "status_cleared": "Словарь очищен.",
        "status_showing": "Показано",
        "status_of": "из",
        # Dialogs
        "msg_edit_select": "Пожалуйста, выберите строку.",
        "msg_edit_title": "Редактирование",
        "msg_delete_confirm": "Удалить словоформу",
        "msg_delete_of": "лексемы",
        "msg_delete_q": "?",
        "msg_delete_title": "Удаление",
        "msg_clear_confirm": "Очистить весь словарь?",
        "msg_clear_title": "Очистка",
        "msg_error_title": "Ошибка",
        "msg_error_open": "Ошибка открытия файла.",
        "msg_export_title": "Экспорт",
        "msg_export_done": "Словарь экспортирован в:",
        "msg_about_title": "О программе",
        "msg_about_body": (
            "Построитель словаря английского языка\n"
            "Лабораторная работа №1, Вариант 13\n\n"
            "Строит алфавитный словарь (лексемы + словоформы)\n"
            "с подсчётом частоты и морфологическими пометками.\n\n"
            "Форматы входных данных: TXT, RTF"
        ),
        # Help dialog
        "help_title": "Справка — Построитель словаря",
        "help_close": "Закрыть",
    },
}

HELP_TEXT = {
    "en": """\
English Dictionary Builder — User Guide
========================================

OPENING A FILE
  File → Open TXT/RTF
  Select a .txt or .rtf file. The application will tokenize, lemmatize,
  and count word frequencies automatically.

DICTIONARY TABLE
  Columns: Lemma | Wordform | Frequency | Morphology
  • Lemma      — base (dictionary) form of the word
  • Wordform   — the exact form found in the text
  • Frequency  — how many times this wordform appeared
  • Morphology — free-text morphological notes (editable)

  Click a column header to sort by that column.
  Double-click a row or press Edit button to edit morphology.

ADDING AN ENTRY MANUALLY
  Edit → Add Entry (or toolbar button)
  Fill in Lemma, Wordform, Frequency and optional Morphology.

EDITING AN ENTRY
  Select a row → Edit → Edit Entry (or double-click).
  You can change Lemma, Wordform, Frequency and Morphology notes.

DELETING AN ENTRY
  Select a row → Edit → Delete Entry.
  If the last wordform of a lemma is deleted, the lemma is removed too.

SEARCH
  Search → Search (Ctrl+F)
  Searches across lemma, wordform and morphology fields.
  Clear the search box to restore the full list.

FILTER BY FREQUENCY
  Search → Filter by Frequency
  Enter minimum and/or maximum frequency to narrow the list.

SAVING THE DICTIONARY
  File → Save Dictionary  — saves to the current JSON file.
  File → Save Dictionary As — choose a new file path.

LOADING A DICTIONARY
  File → Load Dictionary — opens a previously saved .json file.

EXPORTING TO CSV
  File → Export to CSV — saves the dictionary as a CSV file
  (compatible with Excel and other spreadsheet applications).

KEYBOARD SHORTCUTS
  Ctrl+O   Open file
  Ctrl+S   Save dictionary
  Ctrl+F   Search
  Delete   Delete selected entry
  F1       Open this help window
""",
    "ru": """\
Построитель словаря английского языка — Руководство пользователя
=================================================================

ОТКРЫТИЕ ФАЙЛА
  Файл → Открыть TXT/RTF
  Выберите файл .txt или .rtf. Приложение автоматически выполнит
  токенизацию, лемматизацию и подсчёт частот слов.

ТАБЛИЦА СЛОВАРЯ
  Столбцы: Лексема | Словоформа | Частота | Морфология
  • Лексема    — базовая (словарная) форма слова
  • Словоформа — конкретная форма слова, найденная в тексте
  • Частота    — сколько раз эта словоформа встретилась в тексте
  • Морфология — произвольные морфологические пометки (редактируемые)

  Нажмите на заголовок столбца для сортировки.
  Дважды щёлкните строку или нажмите «Изменить» для редактирования.

ДОБАВЛЕНИЕ ЗАПИСИ ВРУЧНУЮ
  Правка → Добавить запись (или кнопка на панели инструментов)
  Заполните поля: Лексема, Словоформа, Частота и Морфология.

РЕДАКТИРОВАНИЕ ЗАПИСИ
  Выберите строку → Правка → Редактировать запись (или двойной щелчок).
  Можно изменить все поля, включая морфологические пометки.

УДАЛЕНИЕ ЗАПИСИ
  Выберите строку → Правка → Удалить запись.
  Если удалена последняя словоформа лексемы, лексема также удаляется.

ПОИСК
  Поиск → Найти (Ctrl+F)
  Ищет по лексеме, словоформе и полю морфологии.
  Очистите поле поиска для отображения всего словаря.

ФИЛЬТР ПО ЧАСТОТЕ
  Поиск → Фильтр по частоте
  Введите минимальную и/или максимальную частоту.

СОХРАНЕНИЕ СЛОВАРЯ
  Файл → Сохранить словарь  — сохраняет в текущий JSON-файл.
  Файл → Сохранить словарь как — выберите новый файл.

ЗАГРУЗКА СЛОВАРЯ
  Файл → Загрузить словарь — открывает ранее сохранённый файл .json.

ЭКСПОРТ В CSV
  Файл → Экспорт в CSV — сохраняет словарь в формате CSV
  (совместимо с Excel и другими таблицами).

ГОРЯЧИЕ КЛАВИШИ
  Ctrl+O   Открыть файл
  Ctrl+S   Сохранить словарь
  Ctrl+F   Поиск
  Delete   Удалить выбранную запись
  F1       Открыть это окно справки
""",
}


def set_language(lang: str) -> None:
    global _LANG
    if lang not in TRANSLATIONS:
        raise ValueError(f"Unknown language: {lang}")
    _LANG = lang


def get_language() -> str:
    return _LANG


def t(key: str) -> str:
    return TRANSLATIONS[_LANG].get(key, TRANSLATIONS["en"].get(key, key))


def help_text() -> str:
    return HELP_TEXT.get(_LANG, HELP_TEXT["en"])
