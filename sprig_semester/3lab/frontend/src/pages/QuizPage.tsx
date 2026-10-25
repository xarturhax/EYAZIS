import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, SyntaxQuizQuestion, QuizToken } from '../api/client'
import { useLanguage } from '../i18n/LanguageContext'
import { useSyntaxStore } from '../store/corpus'

type Translations = typeof import('../i18n/translations').translations['en']

function roleLabel(role: string, t: Translations): string {
  const map: Record<string, string> = {
    subjects: t.roleLabelSubjects,
    predicates: t.roleLabelPredicates,
    objects: t.roleLabelObjects,
    modifiers: t.roleLabelModifiers,
  }
  return map[role] ?? role
}

function highlightWord(sentence: string, word: string) {
  const idx = sentence.toLowerCase().indexOf(word.toLowerCase())
  if (idx === -1) return <span>{sentence}</span>
  return (
    <>
      {sentence.slice(0, idx)}
      <mark className="bg-yellow-200 font-bold rounded px-0.5">{sentence.slice(idx, idx + word.length)}</mark>
      {sentence.slice(idx + word.length)}
    </>
  )
}

export default function QuizPage() {
  const { t } = useLanguage()
  const { selectedDocId, setSelectedDocId } = useSyntaxStore()
  const [question, setQuestion] = useState<SyntaxQuizQuestion | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [score, setScore] = useState({ correct: 0, total: 0 })

  const { data: docs = [] } = useQuery({
    queryKey: ['documents'],
    queryFn: api.listDocuments,
  })

  const quizQuery = useQuery({
    queryKey: ['syntax-quiz', selectedDocId],
    queryFn: () => api.getSyntaxQuiz(selectedDocId ?? undefined),
    enabled: false,
  })

  useEffect(() => {
    if (quizQuery.data && !('error' in quizQuery.data)) {
      setQuestion(quizQuery.data as SyntaxQuizQuestion)
      setSelected(null)
    }
  }, [quizQuery.data])

  const handleNext = () => { quizQuery.refetch() }

  const handleClickWord = (text: string) => {
    if (selected !== null || !question) return
    setSelected(text)
    const correct = question.correct_words.includes(text)
    setScore(s => ({ correct: s.correct + (correct ? 1 : 0), total: s.total + 1 }))
  }

  const handleChooseRole = (opt: string) => {
    if (selected !== null || !question) return
    setSelected(opt)
    const correct = opt === question.correct_answer
    setScore(s => ({ correct: s.correct + (correct ? 1 : 0), total: s.total + 1 }))
  }

  const isAnswerCorrect = selected !== null && question && (
    question.question_type === 'click_word'
      ? question.correct_words.includes(selected)
      : selected === question.correct_answer
  )

  const hasError = quizQuery.data && 'error' in quizQuery.data

  return (
    <div className="p-6 space-y-5 max-w-2xl">
      <h1 className="text-xl font-bold text-gray-800">{t.quizTitle}</h1>

      {/* Document selector */}
      <select
        value={selectedDocId ?? ''}
        onChange={e => setSelectedDocId(e.target.value ? Number(e.target.value) : null)}
        className="border border-gray-300 rounded px-3 py-2 text-sm text-gray-700 bg-white"
      >
        <option value="">{t.selectDocPrompt}</option>
        {docs.map(d => (
          <option key={d.id} value={d.id}>{d.filename}</option>
        ))}
      </select>

      {/* Score + Next button */}
      <div className="flex items-center justify-between">
        {score.total > 0 ? (
          <span className="text-sm font-medium text-gray-600">{t.quizScore(score.correct, score.total)}</span>
        ) : (
          <span />
        )}
        <button
          onClick={handleNext}
          disabled={quizQuery.isFetching}
          className="bg-indigo-600 text-white rounded px-5 py-2 text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
        >
          {quizQuery.isFetching ? t.loading : question ? t.quizNextBtn : t.quizStartBtn}
        </button>
      </div>

      {hasError && (
        <p className="text-sm text-gray-400">{t.quizNoData}</p>
      )}

      {question && !hasError && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
          {/* Question prompt */}
          <p className="text-sm font-semibold text-gray-800">
            {question.question_type === 'click_word'
              ? t.quizClickWord(roleLabel(question.question_role, t))
              : t.quizWhichRole(question.target_word!)}
          </p>

          {question.question_type === 'click_word' ? (
            /* Token chips */
            <div className="flex flex-wrap gap-2">
              {(question.tokens as QuizToken[]).map(tok => {
                const isCorrect = question.correct_words.includes(tok.text)
                const isSelected = selected === tok.text
                let cls = 'px-3 py-1.5 rounded-lg border text-sm transition-colors '
                if (selected === null) {
                  cls += 'bg-gray-50 border-gray-200 hover:bg-indigo-50 hover:border-indigo-300 cursor-pointer'
                } else if (isCorrect) {
                  cls += 'bg-green-100 border-green-400 text-green-700 font-semibold'
                } else if (isSelected) {
                  cls += 'bg-red-100 border-red-400 text-red-700'
                } else {
                  cls += 'bg-gray-50 border-gray-100 text-gray-300'
                }
                return (
                  <button
                    key={tok.i}
                    disabled={selected !== null}
                    onClick={() => handleClickWord(tok.text)}
                    className={cls}
                  >
                    {tok.text}
                  </button>
                )
              })}
            </div>
          ) : (
            /* Multiple choice */
            <div className="space-y-3">
              {/* Sentence with highlighted target word */}
              <p className="text-xs text-gray-500 italic bg-gray-50 rounded p-2 leading-relaxed">
                "{highlightWord(question.sentence_text, question.target_word!)}"
              </p>
              {/* Role options */}
              <div className="grid grid-cols-2 gap-2">
                {(question.options ?? []).map(opt => {
                  let cls = 'py-2.5 px-3 rounded-lg border text-sm font-medium transition-colors text-center '
                  if (selected === null) {
                    cls += 'bg-gray-50 border-gray-200 hover:bg-indigo-50 hover:border-indigo-300 cursor-pointer'
                  } else if (opt === question.correct_answer) {
                    cls += 'bg-green-100 border-green-400 text-green-700'
                  } else if (opt === selected) {
                    cls += 'bg-red-100 border-red-400 text-red-700'
                  } else {
                    cls += 'bg-gray-50 border-gray-100 text-gray-300'
                  }
                  return (
                    <button
                      key={opt}
                      disabled={selected !== null}
                      onClick={() => handleChooseRole(opt)}
                      className={cls}
                    >
                      {roleLabel(opt, t)}
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* Feedback */}
          {selected !== null && (
            <p className={`text-sm font-semibold ${isAnswerCorrect ? 'text-green-600' : 'text-red-600'}`}>
              {isAnswerCorrect
                ? t.quizCorrect
                : t.quizWrong(
                    question.question_type === 'click_word'
                      ? question.correct_words.join(', ')
                      : roleLabel(question.correct_answer!, t)
                  )}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
