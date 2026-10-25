import { useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Upload, Trash2 } from 'lucide-react'
import { api, DocumentItem } from '../api/client'
import { useLanguage } from '../i18n/LanguageContext'
import { useSyntaxStore } from '../store/corpus'

type ProgressState =
  | { phase: 'idle' }
  | { phase: 'uploading'; message: string; current: number; total: number }
  | { phase: 'done'; docId: number }
  | { phase: 'error'; message: string }

export default function DocumentsPage() {
  const { t } = useLanguage()
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [progress, setProgress] = useState<ProgressState>({ phase: 'idle' })
  const { selectedDocId, setSelectedDocId } = useSyntaxStore()

  const { data: docs = [], isLoading } = useQuery({
    queryKey: ['documents'],
    queryFn: api.listDocuments,
  })

  async function handleUpload() {
    const file = fileRef.current?.files?.[0]
    if (!file) return

    setProgress({ phase: 'uploading', message: 'Starting…', current: 0, total: 0 })

    const form = new FormData()
    form.append('file', file)

    const resp = await fetch('/api/documents', { method: 'POST', body: form })
    if (!resp.ok || !resp.body) {
      const text = await resp.text()
      setProgress({ phase: 'error', message: text })
      return
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })

      const events = buf.split('\n\n')
      buf = events.pop() ?? ''

      for (const raw of events) {
        const eventLine = raw.split('\n').find(l => l.startsWith('event:'))
        const dataLine = raw.split('\n').find(l => l.startsWith('data:'))
        if (!eventLine || !dataLine) continue

        const event = eventLine.replace('event:', '').trim()
        const data = JSON.parse(dataLine.replace('data:', '').trim())

        if (event === 'status') {
          setProgress(p =>
            p.phase === 'uploading'
              ? { ...p, message: data.message }
              : { phase: 'uploading', message: data.message, current: 0, total: 0 }
          )
        } else if (event === 'progress') {
          setProgress({ phase: 'uploading', message: 'Analysing sentences…', current: data.current, total: data.total })
        } else if (event === 'done') {
          setProgress({ phase: 'done', docId: data.doc_id })
          qc.invalidateQueries({ queryKey: ['documents'] })
          if (fileRef.current) fileRef.current.value = ''
        } else if (event === 'error') {
          setProgress({ phase: 'error', message: data.message || 'Unknown error' })
        }
      }
    }
  }

  async function handleDelete(id: number) {
    if (!confirm('Delete this document and all its analysis data?')) return
    await api.deleteDocument(id)
    qc.invalidateQueries({ queryKey: ['documents'] })
    if (selectedDocId === id) setSelectedDocId(null)
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <h1 className="text-xl font-bold text-gray-800">{t.documentsTitle}</h1>

      {/* Upload panel */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
        <h2 className="text-sm font-semibold text-gray-700">{t.uploadTitle}</h2>
        <p className="text-xs text-gray-500">{t.uploadHint}</p>
        <div className="flex gap-3 items-center">
          <input
            ref={fileRef}
            type="file"
            accept=".html,.htm,.txt,.rtf,.pdf,.doc,.docx"
            className="text-sm text-gray-600 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
          />
          <button
            onClick={handleUpload}
            disabled={progress.phase === 'uploading'}
            className="flex items-center gap-1.5 bg-indigo-600 text-white text-sm px-4 py-2 rounded hover:bg-indigo-700 disabled:opacity-50"
          >
            <Upload size={14} />
            {progress.phase === 'uploading' ? t.btnUploading : t.btnUpload}
          </button>
        </div>

        {/* Progress */}
        {progress.phase === 'uploading' && (
          <div className="space-y-1">
            <p className="text-xs text-gray-600">{progress.message}</p>
            {progress.total > 0 && (
              <div className="w-full bg-gray-100 rounded-full h-2">
                <div
                  className="bg-indigo-500 h-2 rounded-full transition-all"
                  style={{ width: `${Math.round((progress.current / progress.total) * 100)}%` }}
                />
              </div>
            )}
            {progress.total > 0 && (
              <p className="text-xs text-gray-400">
                {progress.current} / {progress.total} sentences
              </p>
            )}
          </div>
        )}
        {progress.phase === 'done' && (
          <p className="text-xs text-green-600">Done! Document ID: {progress.docId}</p>
        )}
        {progress.phase === 'error' && (
          <p className="text-xs text-red-600">Error: {progress.message}</p>
        )}
      </div>

      {/* Documents table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {isLoading ? (
          <p className="p-6 text-sm text-gray-500">{t.loading}</p>
        ) : docs.length === 0 ? (
          <p className="p-6 text-sm text-gray-500">{t.noDocuments}</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {[t.colFilename, t.colFormat, t.colSentences, t.colUploaded, t.colActions].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {docs.map((doc: DocumentItem) => (
                <tr
                  key={doc.id}
                  onClick={() => setSelectedDocId(doc.id)}
                  className={`cursor-pointer transition-colors ${
                    selectedDocId === doc.id ? 'bg-indigo-50' : 'hover:bg-gray-50'
                  }`}
                >
                  <td className="px-4 py-3 font-medium text-gray-800">{doc.filename}</td>
                  <td className="px-4 py-3">
                    <span className="bg-gray-100 text-gray-600 text-xs rounded px-2 py-0.5 uppercase">
                      {doc.source_format}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{doc.sentence_count}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {new Date(doc.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={e => { e.stopPropagation(); handleDelete(doc.id) }}
                      className="text-red-400 hover:text-red-600 transition-colors"
                      title={t.btnDelete}
                    >
                      <Trash2 size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
