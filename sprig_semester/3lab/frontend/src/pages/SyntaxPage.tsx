import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, DepNode, DepToken, ConstNode, SyntaxResult, Roles } from '../api/client'
import { useLanguage } from '../i18n/LanguageContext'
import { useSyntaxStore } from '../store/corpus'

// ─── Dependency Tree (SVG arc diagram) ───────────────────────────────────────

const POS_COLORS: Record<string, string> = {
  NOUN: '#6366f1', VERB: '#10b981', ADJ: '#f59e0b', ADV: '#3b82f6',
  PRON: '#8b5cf6', DET: '#ec4899', ADP: '#14b8a6', PUNCT: '#9ca3af',
  CCONJ: '#f97316', SCONJ: '#84cc16', AUX: '#06b6d4', NUM: '#d946ef',
}
const DEP_COLORS: Record<string, string> = {
  ROOT: '#ef4444', nsubj: '#6366f1', dobj: '#10b981', obj: '#10b981',
  prep: '#f59e0b', det: '#9ca3af', amod: '#3b82f6', advmod: '#3b82f6',
}

function DepTreeSVG({ tokens, tree }: { tokens: SyntaxResult['dependency']['tokens']; tree: DepNode }) {
  if (!tokens.length) return null

  const W = Math.max(tokens.length * 80, 400)
  const colW = W / tokens.length
  const baseY = 120
  const svgH = 200

  // Compute arcs between head and dependent
  const arcs: { from: number; to: number; dep: string }[] = tokens
    .filter(t => t.dep !== 'ROOT' && t.head !== t.i)
    .map(t => ({ from: t.head, to: t.i, dep: t.dep }))

  function xOf(i: number) {
    return colW * i + colW / 2
  }

  return (
    <svg width="100%" viewBox={`0 0 ${W} ${svgH}`} className="overflow-visible font-mono text-xs">
      {/* Arcs */}
      {arcs.map((arc, idx) => {
        const x1 = xOf(arc.from)
        const x2 = xOf(arc.to)
        const mid = (x1 + x2) / 2
        const dist = Math.abs(arc.from - arc.to)
        const cy = baseY - 20 - dist * 18
        const color = DEP_COLORS[arc.dep] ?? '#6b7280'
        return (
          <g key={idx}>
            <path
              d={`M ${x1} ${baseY - 8} Q ${mid} ${cy} ${x2} ${baseY - 8}`}
              fill="none"
              stroke={color}
              strokeWidth="1.5"
              opacity="0.8"
            />
            {/* Arrow head */}
            <circle cx={x2} cy={baseY - 8} r="3" fill={color} />
            {/* Label */}
            <text
              x={mid}
              y={cy - 3}
              textAnchor="middle"
              fill={color}
              fontSize="9"
              fontWeight="600"
            >
              {arc.dep}
            </text>
          </g>
        )
      })}

      {/* Tokens */}
      {tokens.map((t, i) => {
        const x = xOf(i)
        const posColor = POS_COLORS[t.pos] ?? '#374151'
        const isRoot = t.dep === 'ROOT'
        return (
          <g key={i}>
            <rect x={x - 28} y={baseY} width={56} height={22} rx={4}
              fill={isRoot ? '#fef3c7' : '#f3f4f6'} stroke={isRoot ? '#fbbf24' : '#e5e7eb'} />
            <text x={x} y={baseY + 15} textAnchor="middle" fontSize="11" fontWeight={isRoot ? '700' : '400'} fill={posColor}>
              {t.text}
            </text>
            <text x={x} y={baseY + 35} textAnchor="middle" fontSize="9" fill="#9ca3af">
              {t.pos}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

// ─── Constituency Tree (SVG layout) ──────────────────────────────────────────

const LEAF_W = 70
const ROW_H = 55

interface LayoutNode { node: ConstNode; x: number; y: number; children: LayoutNode[] }

function countLeaves(n: ConstNode): number {
  return n.children.length === 0 ? 1 : n.children.reduce((s, c) => s + countLeaves(c), 0)
}

function getDepth(n: ConstNode): number {
  return n.children.length === 0 ? 0 : 1 + Math.max(...n.children.map(getDepth))
}

function buildLayout(node: ConstNode, offsetX: number, depth: number): LayoutNode {
  const leaves = countLeaves(node)
  const x = offsetX + (leaves * LEAF_W) / 2
  const y = depth * ROW_H + 20
  let childX = offsetX
  const children = node.children.map(child => {
    const l = buildLayout(child, childX, depth + 1)
    childX += countLeaves(child) * LEAF_W
    return l
  })
  return { node, x, y, children }
}

// ─── Role-based tree helpers ─────────────────────────────────────────────────

function getNounPhrase(headIdx: number, tokens: DepToken[]): DepToken[] {
  const npDeps = new Set(['det', 'amod', 'compound', 'nummod', 'poss', 'nmod'])
  const result: DepToken[] = []
  const head = tokens.find(t => t.i === headIdx)
  if (head) result.push(head)
  tokens.forEach(t => { if (t.head === headIdx && npDeps.has(t.dep)) result.push(t) })
  return result.sort((a, b) => a.i - b.i)
}

function getVerbPhrase(headIdx: number, tokens: DepToken[]): DepToken[] {
  const vpDeps = new Set(['aux', 'auxpass', 'neg'])
  const result: DepToken[] = []
  const head = tokens.find(t => t.i === headIdx)
  if (head) result.push(head)
  tokens.forEach(t => { if (t.head === headIdx && vpDeps.has(t.dep)) result.push(t) })
  return result.sort((a, b) => a.i - b.i)
}

function buildRoleTree(roles: Roles, tokens: DepToken[]): ConstNode {
  const makeWordNode = (t: DepToken): ConstNode => ({
    label: t.text,
    children: [{ label: t.pos, children: [] }],
  })
  const makePhraseNode = (phrase: DepToken[]): ConstNode => ({
    label: phrase.map(t => t.text).join(' '),
    children: phrase.map(makeWordNode),
  })

  const groups: ConstNode[] = []

  if (roles.subjects.length > 0)
    groups.push({
      label: 'Подлежащее',
      children: roles.subjects.map(r => makePhraseNode(getNounPhrase(r.idx, tokens))),
    })

  if (roles.predicates.length > 0)
    groups.push({
      label: 'Сказуемое',
      children: roles.predicates.map(r => makePhraseNode(getVerbPhrase(r.idx, tokens))),
    })

  if (roles.objects.length > 0)
    groups.push({
      label: 'Дополнение',
      children: roles.objects.map(r => makePhraseNode(getNounPhrase(r.idx, tokens))),
    })

  if (roles.modifiers.length > 0)
    groups.push({
      label: 'Обстоятельство',
      children: roles.modifiers.map(r => {
        const t = tokens.find(tok => tok.i === r.idx)
        return t ? makeWordNode(t) : { label: r.text, children: [{ label: r.pos, children: [] }] }
      }),
    })

  return { label: 'S', children: groups }
}

const ROLE_COLORS: Record<string, { bg: string; fg: string }> = {
  SUBJ: { bg: '#dbeafe', fg: '#1d4ed8' },
  PRED: { bg: '#fee2e2', fg: '#b91c1c' },
  OBJ:  { bg: '#dcfce7', fg: '#15803d' },
  MOD:  { bg: '#fef9c3', fg: '#a16207' },
}

function renderLayout(
  layout: LayoutNode,
  depth: number,
  elements: JSX.Element[],
  roleMap: Map<string, string>,
  depMap: Map<string, string>,
) {
  const hue = (depth * 47) % 360
  const isLeaf = layout.node.children.length === 0

  layout.children.forEach(child => {
    elements.push(
      <line key={`line-${layout.x}-${layout.y}-${child.x}`}
        x1={layout.x} y1={layout.y + 8} x2={child.x} y2={child.y - 8}
        stroke="#d1d5db" strokeWidth="1.5" />
    )
    renderLayout(child, depth + 1, elements, roleMap, depMap)
  })

  if (isLeaf) {
    elements.push(
      <text key={`lbl-${layout.x}-${layout.y}`}
        x={layout.x} y={layout.y} textAnchor="middle"
        fontSize="12" fill="#374151" fontWeight="500">
        {layout.node.label}
      </text>
    )
  } else {
    const w = layout.node.label.length * 7 + 12
    elements.push(
      <g key={`node-${layout.x}-${layout.y}`}>
        <rect x={layout.x - w / 2} y={layout.y - 12} width={w} height={18} rx={4}
          fill={`hsl(${hue},60%,93%)`} stroke={`hsl(${hue},50%,70%)`} strokeWidth="1" />
        <text x={layout.x} y={layout.y} textAnchor="middle"
          fontSize="11" fontWeight="700" fill={`hsl(${hue},60%,35%)`}>
          {layout.node.label}
        </text>
      </g>
    )

    const role = roleMap.get(layout.node.label)
    if (role) {
      const colors = ROLE_COLORS[role] ?? ROLE_COLORS.MOD
      const bw = role.length * 6 + 10
      elements.push(
        <g key={`role-${layout.x}-${layout.y}`}>
          <rect x={layout.x - bw / 2} y={layout.y + 8} width={bw} height={13} rx={3} fill={colors.bg} />
          <text x={layout.x} y={layout.y + 18} textAnchor="middle" fontSize="8" fontWeight="700" fill={colors.fg}>
            {role}
          </text>
        </g>
      )
    } else {
      const dep = depMap.get(layout.node.label)
      if (dep) {
        const bw = dep.length * 6 + 10
        elements.push(
          <g key={`dep-${layout.x}-${layout.y}`}>
            <rect x={layout.x - bw / 2} y={layout.y + 8} width={bw} height={13} rx={3} fill="#f3f4f6" stroke="#d1d5db" strokeWidth="0.5" />
            <text x={layout.x} y={layout.y + 18} textAnchor="middle" fontSize="8" fontWeight="600" fill="#6b7280">
              {dep}
            </text>
          </g>
        )
      }
    }
  }
}

function ConstTreeSVG({ node, roles, tokens }: { node: ConstNode; roles?: Roles; tokens?: DepToken[] }) {
  const roleMap = new Map<string, string>()
  if (roles) {
    roles.subjects.forEach(r   => roleMap.set(r.text, 'SUBJ'))
    roles.predicates.forEach(r => roleMap.set(r.text, 'PRED'))
    roles.objects.forEach(r    => roleMap.set(r.text, 'OBJ'))
    roles.modifiers.forEach(r  => roleMap.set(r.text, 'MOD'))
  }

  const depMap = new Map<string, string>()
  if (tokens) {
    tokens.forEach(t => depMap.set(t.text, t.dep.toUpperCase()))
  }

  const totalLeaves = countLeaves(node)
  const maxDepth = getDepth(node)
  const width = Math.max(totalLeaves * LEAF_W, 300)
  const height = (maxDepth + 1) * ROW_H + 30

  const layout = buildLayout(node, 0, 0)
  const elements: JSX.Element[] = []
  renderLayout(layout, 0, elements, roleMap, depMap)

  return (
    <svg width={width} height={height} className="overflow-visible font-mono">
      {elements}
    </svg>
  )
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function SyntaxPage() {
  const { t } = useLanguage()
  const { selectedDocId } = useSyntaxStore()
  const [sentId, setSentId] = useState<number | null>(null)

  const { data: docs = [] } = useQuery({ queryKey: ['documents'], queryFn: api.listDocuments })

  const { data: sentences = [], isLoading: loadingSents } = useQuery({
    queryKey: ['sentences', selectedDocId],
    queryFn: () => api.listSentences(selectedDocId!),
    enabled: selectedDocId !== null,
  })

  const { data: syntax, isLoading: loadingSyntax } = useQuery({
    queryKey: ['syntax', sentId],
    queryFn: () => api.getSentenceSyntax(sentId!),
    enabled: sentId !== null,
  })

  const { setSelectedDocId } = useSyntaxStore()

  return (
    <div className="p-6 space-y-4 max-w-full">
      <h1 className="text-xl font-bold text-gray-800">{t.syntaxTitle}</h1>

      {/* Document selector */}
      <select
        value={selectedDocId ?? ''}
        onChange={e => { setSelectedDocId(e.target.value ? Number(e.target.value) : null); setSentId(null) }}
        className="border border-gray-300 rounded px-3 py-2 text-sm text-gray-700 bg-white"
      >
        <option value="">{t.selectDocPrompt}</option>
        {docs.map(d => (
          <option key={d.id} value={d.id}>{d.filename}</option>
        ))}
      </select>

      {selectedDocId && (
        <div className="flex gap-4 h-[calc(100vh-180px)]">
          {/* Sentence list */}
          <div className="w-64 shrink-0 bg-white border border-gray-200 rounded-xl overflow-y-auto">
            <div className="px-4 py-3 border-b border-gray-100 text-xs font-semibold text-gray-500 uppercase tracking-wider">
              {t.labelSentences}
            </div>
            {loadingSents ? (
              <p className="p-4 text-sm text-gray-400">{t.loading}</p>
            ) : (
              <ul>
                {sentences.map(s => (
                  <li key={s.id}>
                    <button
                      onClick={() => setSentId(s.id)}
                      className={`w-full text-left px-4 py-3 text-xs border-b border-gray-50 hover:bg-indigo-50 transition-colors ${
                        sentId === s.id ? 'bg-indigo-50 text-indigo-700 font-medium' : 'text-gray-700'
                      }`}
                    >
                      <span className="text-gray-400 mr-1">{s.idx + 1}.</span>
                      {s.text.slice(0, 80)}{s.text.length > 80 ? '…' : ''}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Analysis panel */}
          <div className="flex-1 overflow-y-auto space-y-4">
            {!sentId ? (
              <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-sm text-gray-400">
                {t.selectSentPrompt}
              </div>
            ) : loadingSyntax ? (
              <p className="text-sm text-gray-500 p-4">{t.loading}</p>
            ) : syntax ? (
              <>
                {/* Sentence text */}
                <div className="bg-white border border-gray-200 rounded-xl p-4">
                  <p className="text-sm text-gray-800 leading-relaxed">"{syntax.text}"</p>
                </div>

                {/* Dependency Tree */}
                <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-2">
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    {t.labelDepTree}
                  </h3>
                  <div className="overflow-x-auto">
                    <DepTreeSVG
                      tokens={syntax.dependency.tokens}
                      tree={syntax.dependency.tree}
                    />
                  </div>
                </div>

                {/* Constituency Tree */}
                <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-2">
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    {t.labelConstTree}
                  </h3>
                  <div className="overflow-x-auto p-2">
                    <ConstTreeSVG node={buildRoleTree(syntax.roles, syntax.dependency.tokens)} />
                  </div>
                </div>

                {/* Bracket notation */}
                <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-2">
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    {t.labelBracket}
                  </h3>
                  <pre className="text-xs text-gray-600 whitespace-pre-wrap break-all font-mono bg-gray-50 rounded p-3">
                    {syntax.constituency_bracket}
                  </pre>
                </div>
              </>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}
