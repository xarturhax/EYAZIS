// ─── Types ────────────────────────────────────────────────────────────────────

export interface DocumentItem {
  id: number
  filename: string
  source_format: string
  created_at: string
  sentence_count: number
}

export interface SentenceItem {
  id: number
  idx: number
  text: string
}

export interface DepToken {
  i: number
  text: string
  lemma: string
  pos: string
  tag: string
  dep: string
  head: number
}

export interface DepNode {
  i: number
  text: string
  lemma: string
  pos: string
  dep: string
  children: DepNode[]
}

export interface DepTree {
  tokens: DepToken[]
  tree: DepNode
}

export interface ConstNode {
  label: string
  children: ConstNode[]
}

export interface RoleItem {
  text: string
  idx: number
  dep: string
  pos: string
}

export interface Roles {
  subjects: RoleItem[]
  predicates: RoleItem[]
  objects: RoleItem[]
  modifiers: RoleItem[]
}

export interface SyntaxResult {
  sentence_id: number
  text: string
  dependency: DepTree
  constituency_bracket: string
  constituency_tree: ConstNode
  roles: Roles
}

export interface SentenceRoles {
  sentence_id: number
  idx: number
  text: string
  roles: Roles
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init)
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status} ${body}`)
  }
  return res.json() as Promise<T>
}

// ─── API ──────────────────────────────────────────────────────────────────────

// Syntax Quiz
export interface QuizToken {
  i: number
  text: string
}

export interface SyntaxQuizQuestion {
  sentence_id: number
  sentence_text: string
  tokens: QuizToken[]
  question_type: 'click_word' | 'multiple_choice'
  question_role: string
  correct_words: string[]
  target_word: string | null
  correct_answer: string | null
  options: string[] | null
}

export const api = {
  /** List all documents */
  listDocuments: () => apiFetch<DocumentItem[]>('/documents'),

  /** Delete a document */
  deleteDocument: (id: number) =>
    apiFetch<void>(`/documents/${id}`, { method: 'DELETE' }),

  /** List sentences for a document */
  listSentences: (docId: number) =>
    apiFetch<SentenceItem[]>(`/syntax/${docId}/sentences`),

  /** Get full syntax for one sentence */
  getSentenceSyntax: (sentId: number) =>
    apiFetch<SyntaxResult>(`/syntax/sentence/${sentId}`),

  /** Get roles for all sentences in a document */
  listRoles: (docId: number) =>
    apiFetch<SentenceRoles[]>(`/syntax/${docId}/roles`),

  /** Export URL (open in new tab) */
  exportUrl: (docId: number, fmt: 'json' | 'txt') =>
    `/api/syntax/${docId}/export?fmt=${fmt}`,

  /** Get a random syntax quiz question */
  getSyntaxQuiz: (docId?: number) =>
    apiFetch<SyntaxQuizQuestion>(`/syntax/quiz${docId !== undefined ? `?doc_id=${docId}` : ''}`),
}
