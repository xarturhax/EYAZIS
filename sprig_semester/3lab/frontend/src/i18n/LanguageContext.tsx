import { createContext, useContext, useState, ReactNode } from 'react'
import { translations, Lang } from './translations'

interface LangCtx {
  lang: Lang
  t: typeof translations['en']
  toggleLang: () => void
}

const LanguageContext = createContext<LangCtx>(null!)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>('en')
  const toggleLang = () => setLang(l => (l === 'en' ? 'ru' : 'en'))
  return (
    <LanguageContext.Provider value={{ lang, t: translations[lang], toggleLang }}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useLanguage() {
  return useContext(LanguageContext)
}
