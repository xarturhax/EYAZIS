import { create } from 'zustand'

interface SyntaxStore {
  selectedDocId: number | null
  selectedSentId: number | null
  setSelectedDocId: (id: number | null) => void
  setSelectedSentId: (id: number | null) => void
}

export const useSyntaxStore = create<SyntaxStore>((set) => ({
  selectedDocId: null,
  selectedSentId: null,
  setSelectedDocId: (id) => set({ selectedDocId: id, selectedSentId: null }),
  setSelectedSentId: (id) => set({ selectedSentId: id }),
}))
