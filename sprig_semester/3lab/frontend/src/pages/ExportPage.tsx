import { useQuery } from '@tanstack/react-query'
import { Download, FileJson, FileText } from 'lucide-react'
import { api } from '../api/client'
import { useLanguage } from '../i18n/LanguageContext'
import { useSyntaxStore } from '../store/corpus'

export default function ExportPage() {
  const { t } = useLanguage()
  const { selectedDocId, setSelectedDocId } = useSyntaxStore()

  const { data: docs = [] } = useQuery({ queryKey: ['documents'], queryFn: api.listDocuments })

  const selectedDoc = docs.find(d => d.id === selectedDocId)

  return (
    <div className="p-6 space-y-6 max-w-xl">
      <h1 className="text-xl font-bold text-gray-800">{t.exportTitle}</h1>
      <p className="text-sm text-gray-600">{t.exportDesc}</p>

      <select
        value={selectedDocId ?? ''}
        onChange={e => setSelectedDocId(e.target.value ? Number(e.target.value) : null)}
        className="border border-gray-300 rounded px-3 py-2 text-sm text-gray-700 bg-white w-full"
      >
        <option value="">{t.selectDocPrompt}</option>
        {docs.map(d => (
          <option key={d.id} value={d.id}>{d.filename}</option>
        ))}
      </select>

      {!selectedDocId ? (
        <p className="text-sm text-gray-500">{t.noDocSelected}</p>
      ) : (
        <div className="space-y-3">
          {selectedDoc && (
            <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-600">
              <strong>{selectedDoc.filename}</strong> · {selectedDoc.sentence_count} sentences · {selectedDoc.source_format.toUpperCase()}
            </div>
          )}

          <a
            href={api.exportUrl(selectedDocId, 'json')}
            download
            className="flex items-center gap-3 bg-white border border-gray-200 rounded-xl px-5 py-4 hover:bg-indigo-50 hover:border-indigo-300 transition-colors group"
          >
            <FileJson size={24} className="text-indigo-500" />
            <div>
              <p className="text-sm font-semibold text-gray-800 group-hover:text-indigo-700">
                {t.btnExportJson}
              </p>
              <p className="text-xs text-gray-500">Full dependency + constituency trees + roles</p>
            </div>
            <Download size={16} className="ml-auto text-gray-400 group-hover:text-indigo-500" />
          </a>

          <a
            href={api.exportUrl(selectedDocId, 'txt')}
            download
            className="flex items-center gap-3 bg-white border border-gray-200 rounded-xl px-5 py-4 hover:bg-indigo-50 hover:border-indigo-300 transition-colors group"
          >
            <FileText size={24} className="text-indigo-400" />
            <div>
              <p className="text-sm font-semibold text-gray-800 group-hover:text-indigo-700">
                {t.btnExportTxt}
              </p>
              <p className="text-xs text-gray-500">One bracket-notation tree per sentence</p>
            </div>
            <Download size={16} className="ml-auto text-gray-400 group-hover:text-indigo-500" />
          </a>
        </div>
      )}
    </div>
  )
}
