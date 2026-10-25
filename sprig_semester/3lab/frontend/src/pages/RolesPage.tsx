import { useQuery } from '@tanstack/react-query'
import { api, SentenceRoles, RoleItem } from '../api/client'
import { useLanguage } from '../i18n/LanguageContext'
import { useSyntaxStore } from '../store/corpus'

function Chips({ items, color }: { items: RoleItem[]; color: string }) {
  if (!items.length) return <span className="text-gray-300">—</span>
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((item, i) => (
        <span
          key={i}
          className={`inline-block text-xs px-2 py-0.5 rounded-full font-medium ${color}`}
          title={`dep:${item.dep} pos:${item.pos}`}
        >
          {item.text}
        </span>
      ))}
    </div>
  )
}

export default function RolesPage() {
  const { t } = useLanguage()
  const { selectedDocId, setSelectedDocId } = useSyntaxStore()

  const { data: docs = [] } = useQuery({ queryKey: ['documents'], queryFn: api.listDocuments })

  const { data: roles = [], isLoading } = useQuery({
    queryKey: ['roles', selectedDocId],
    queryFn: () => api.listRoles(selectedDocId!),
    enabled: selectedDocId !== null,
  })

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-xl font-bold text-gray-800">{t.rolesTitle}</h1>

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

      {!selectedDocId ? (
        <p className="text-sm text-gray-500">{t.noRoles}</p>
      ) : isLoading ? (
        <p className="text-sm text-gray-500">{t.loading}</p>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider w-6">#</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">{t.colSentence}</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-indigo-500 uppercase tracking-wider">{t.colSubjects}</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-emerald-500 uppercase tracking-wider">{t.colPredicates}</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-amber-500 uppercase tracking-wider">{t.colObjects}</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-blue-400 uppercase tracking-wider">{t.colModifiers}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {(roles as SentenceRoles[]).map(row => (
                <tr key={row.sentence_id} className="hover:bg-gray-50 align-top">
                  <td className="px-4 py-3 text-gray-400 text-xs">{row.idx + 1}</td>
                  <td className="px-4 py-3 text-gray-700 max-w-xs">
                    <span className="line-clamp-2 text-xs leading-relaxed">{row.text}</span>
                  </td>
                  <td className="px-4 py-3">
                    <Chips items={row.roles.subjects} color="bg-indigo-100 text-indigo-700" />
                  </td>
                  <td className="px-4 py-3">
                    <Chips items={row.roles.predicates} color="bg-emerald-100 text-emerald-700" />
                  </td>
                  <td className="px-4 py-3">
                    <Chips items={row.roles.objects} color="bg-amber-100 text-amber-700" />
                  </td>
                  <td className="px-4 py-3">
                    <Chips items={row.roles.modifiers} color="bg-blue-100 text-blue-700" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
