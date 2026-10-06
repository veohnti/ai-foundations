import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, HashRouter } from 'react-router-dom'
import { STATIC_SITE } from './api'
import App from './App'
import { AuthProvider } from './auth'
import { ChatResultsProvider } from './chatResults'
import { PageContextProvider } from './pageContext'
// Fonts are bundled from npm (not loaded from Google), so they also work in
// the offline HTML copy shared with TAs.
import '@fontsource/hanken-grotesk/latin-400.css'
import '@fontsource/hanken-grotesk/latin-500.css'
import '@fontsource/hanken-grotesk/latin-600.css'
import '@fontsource/hanken-grotesk/latin-700.css'
import '@fontsource/playfair-display/latin-600.css'
import '@fontsource/playfair-display/latin-700.css'
import '@fontsource/playfair-display/latin-700-italic.css'
import './index.css'

// The offline copy is opened as a file (file://...), where only #/hash URLs work.
const Router = STATIC_SITE ? HashRouter : BrowserRouter

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Router>
      <AuthProvider>
        <ChatResultsProvider>
          <PageContextProvider>
            <App />
          </PageContextProvider>
        </ChatResultsProvider>
      </AuthProvider>
    </Router>
  </StrictMode>,
)
