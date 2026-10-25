export type Lang = 'en' | 'ru'

export const translations = {
  en: {
    appTitle: 'Syntax Analyzer',
    appSubtitle: 'Lab 3 · English HTML',
    navDocuments: 'Documents',
    navSyntax: 'Syntax Trees',
    navRoles: 'Syntactic Roles',
    navExport: 'Export',
    helpBtn: 'Help',
    langToggle: 'RU',

    helpTitle: 'Help',
    helpClose: 'Close',
    helpSections: [
      {
        title: 'Documents',
        body: 'Upload HTML files (or TXT, RTF, PDF, DOC, DOCX). The system extracts text, splits it into sentences and runs syntactic analysis automatically. Progress is shown in real-time. Click a row to select a document for analysis on other pages.',
      },
      {
        title: 'Syntax Trees',
        body: 'Choose a document and then click any sentence to see its syntactic analysis. The Dependency Tree shows grammatical relations between words (arcs with labels). The Constituency Tree shows the phrase-structure grouping (S → NP + VP). The bracket notation is also shown for reference.',
      },
      {
        title: 'Syntactic Roles',
        body: 'For the selected document, every sentence is shown with its identified syntactic roles: Subject (who performs the action), Predicate (the main verb), Object (recipient of action) and Modifiers (adjectives, adverbs, prepositional phrases).',
      },
      {
        title: 'Export',
        body: 'Download the complete syntactic analysis of the selected document as a JSON file (full tree structures) or a TXT file (constituency bracket strings, one per sentence).',
      },
    ],

    // DocumentsPage
    documentsTitle: 'Documents',
    uploadTitle: 'Upload Document',
    uploadHint: 'Accepted: .html .htm .txt .rtf .pdf .doc .docx',
    btnUpload: 'Upload & Analyse',
    btnUploading: 'Processing…',
    noDocuments: 'No documents yet. Upload one above.',
    colFilename: 'Filename',
    colFormat: 'Format',
    colSentences: 'Sentences',
    colUploaded: 'Uploaded',
    colActions: 'Actions',
    btnDelete: 'Delete',

    // SyntaxPage
    syntaxTitle: 'Syntax Trees',
    selectDocPrompt: 'Select a document',
    selectSentPrompt: 'Click a sentence to analyse',
    labelSentences: 'Sentences',
    labelDepTree: 'Dependency Tree',
    labelConstTree: 'Constituency Tree',
    labelBracket: 'Bracket Notation',
    noSyntaxYet: 'Select a sentence on the left.',

    // RolesPage
    rolesTitle: 'Syntactic Roles',
    colSentence: 'Sentence',
    colSubjects: 'Subjects',
    colPredicates: 'Predicates',
    colObjects: 'Objects',
    colModifiers: 'Modifiers',
    noRoles: 'No data. Select a document first.',

    // ExportPage
    exportTitle: 'Export',
    exportDesc: 'Download the syntactic analysis of the selected document.',
    btnExportJson: 'Download JSON',
    btnExportTxt: 'Download TXT (brackets)',
    noDocSelected: 'No document selected. Go to Documents and click a row.',

    loading: 'Loading…',

    // QuizPage
    navQuiz: 'Quiz',
    quizTitle: 'Syntax Role Quiz',
    quizScore: (c: number, total: number) => `Score: ${c} / ${total}`,
    quizStartBtn: 'Start Quiz',
    quizNextBtn: 'Next Question',
    quizClickWord: (role: string) => `Click the word that is the ${role}`,
    quizWhichRole: (word: string) => `What syntactic role does "${word}" play?`,
    quizCorrect: 'Correct!',
    quizWrong: (correct: string) => `Wrong. The correct answer is: ${correct}`,
    quizNoData: 'No suitable sentences found. Upload a document first.',
    roleLabelSubjects: 'Subject',
    roleLabelPredicates: 'Predicate',
    roleLabelObjects: 'Object',
    roleLabelModifiers: 'Modifier',
  },

  ru: {
    appTitle: 'Синтаксический анализатор',
    appSubtitle: 'Лаб. 3 · Английский HTML',
    navDocuments: 'Документы',
    navSyntax: 'Деревья',
    navRoles: 'Роли',
    navExport: 'Экспорт',
    helpBtn: 'Помощь',
    langToggle: 'EN',

    helpTitle: 'Помощь',
    helpClose: 'Закрыть',
    helpSections: [
      {
        title: 'Документы',
        body: 'Загружайте HTML-файлы (а также TXT, RTF, PDF, DOC, DOCX). Система извлекает текст, разбивает его на предложения и автоматически выполняет синтаксический анализ. Прогресс отображается в реальном времени. Кликните по строке, чтобы выбрать документ.',
      },
      {
        title: 'Деревья',
        body: 'Выберите документ и кликните на предложение для просмотра синтаксического анализа. Дерево зависимостей показывает грамматические связи между словами. Дерево составляющих показывает фразовую структуру (S → NP + VP). Также отображается скобочная нотация.',
      },
      {
        title: 'Роли',
        body: 'Для выбранного документа отображаются синтаксические роли каждого предложения: Подлежащее, Сказуемое, Дополнение, Модификаторы.',
      },
      {
        title: 'Экспорт',
        body: 'Скачайте полный синтаксический анализ выбранного документа в формате JSON (полные структуры деревьев) или TXT (скобочная нотация по предложениям).',
      },
    ],

    documentsTitle: 'Документы',
    uploadTitle: 'Загрузить документ',
    uploadHint: 'Форматы: .html .htm .txt .rtf .pdf .doc .docx',
    btnUpload: 'Загрузить и анализировать',
    btnUploading: 'Обработка…',
    noDocuments: 'Нет документов. Загрузите один выше.',
    colFilename: 'Имя файла',
    colFormat: 'Формат',
    colSentences: 'Предложений',
    colUploaded: 'Загружен',
    colActions: 'Действия',
    btnDelete: 'Удалить',

    syntaxTitle: 'Деревья синтаксического анализа',
    selectDocPrompt: 'Выберите документ',
    selectSentPrompt: 'Кликните на предложение',
    labelSentences: 'Предложения',
    labelDepTree: 'Дерево зависимостей',
    labelConstTree: 'Дерево составляющих',
    labelBracket: 'Скобочная нотация',
    noSyntaxYet: 'Выберите предложение слева.',

    rolesTitle: 'Синтаксические роли',
    colSentence: 'Предложение',
    colSubjects: 'Подлежащие',
    colPredicates: 'Сказуемые',
    colObjects: 'Дополнения',
    colModifiers: 'Модификаторы',
    noRoles: 'Нет данных. Выберите документ.',

    exportTitle: 'Экспорт',
    exportDesc: 'Скачайте результаты анализа выбранного документа.',
    btnExportJson: 'Скачать JSON',
    btnExportTxt: 'Скачать TXT (скобки)',
    noDocSelected: 'Документ не выбран. Перейдите в «Документы» и кликните по строке.',

    loading: 'Загрузка…',

    // QuizPage
    navQuiz: 'Тест',
    quizTitle: 'Тест по синтаксическим ролям',
    quizScore: (c: number, total: number) => `Результат: ${c} / ${total}`,
    quizStartBtn: 'Начать тест',
    quizNextBtn: 'Следующий вопрос',
    quizClickWord: (role: string) => `Нажмите на слово — ${role}`,
    quizWhichRole: (word: string) => `Какую роль играет слово "${word}"?`,
    quizCorrect: 'Верно!',
    quizWrong: (correct: string) => `Неверно. Правильный ответ: ${correct}`,
    quizNoData: 'Нет подходящих предложений. Загрузите документ.',
    roleLabelSubjects: 'Подлежащее',
    roleLabelPredicates: 'Сказуемое',
    roleLabelObjects: 'Дополнение',
    roleLabelModifiers: 'Модификатор',
  },
} as const
