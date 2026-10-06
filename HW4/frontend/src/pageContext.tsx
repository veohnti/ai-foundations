import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import type { PageContext } from './api'

/**
 * What the current page is showing, published by the page itself (a product
 * page, or the Products grid) and read by the chat panel, which sends it along
 * with every message. Pages clear it when they unmount, so it never describes a
 * page the shopper has left.
 */
type ViewState = {
  view: Omit<PageContext, 'path'> | null
  setView: (view: Omit<PageContext, 'path'> | null) => void
}

const PageContextContext = createContext<ViewState | null>(null)

export function PageContextProvider({ children }: { children: ReactNode }) {
  const [view, setView] = useState<Omit<PageContext, 'path'> | null>(null)
  const value = useMemo(() => ({ view, setView }), [view])
  return <PageContextContext.Provider value={value}>{children}</PageContextContext.Provider>
}

export function usePageContext() {
  const ctx = useContext(PageContextContext)
  if (!ctx) throw new Error('usePageContext must be used within PageContextProvider')
  return ctx
}
