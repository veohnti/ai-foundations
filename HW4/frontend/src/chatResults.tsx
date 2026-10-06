import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import type { PageResults } from './api'

/**
 * Holds the product set the chat assistant asked the Products page to show.
 * The chat panel writes it when a reply carries `page_results`; the Products
 * page reads it. `null` means no chat filter is active and the page shows the
 * full catalogue.
 */
type ChatResultsState = {
  pageResults: PageResults | null
  showResults: (results: PageResults) => void
  clearResults: () => void
}

const ChatResultsContext = createContext<ChatResultsState | null>(null)

export function ChatResultsProvider({ children }: { children: ReactNode }) {
  const [pageResults, setPageResults] = useState<PageResults | null>(null)

  const value = useMemo<ChatResultsState>(
    () => ({
      pageResults,
      showResults: setPageResults,
      clearResults: () => setPageResults(null),
    }),
    [pageResults],
  )

  return <ChatResultsContext.Provider value={value}>{children}</ChatResultsContext.Provider>
}

export function useChatResults() {
  const ctx = useContext(ChatResultsContext)
  if (!ctx) throw new Error('useChatResults must be used within ChatResultsProvider')
  return ctx
}
