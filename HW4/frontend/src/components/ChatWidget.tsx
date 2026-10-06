import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { fetchChatHistory, sendChat, type ChatTurn, type ProductCard } from '../api'
import { useAuth } from '../auth'
import { useChatResults } from '../chatResults'
import { usePageContext } from '../pageContext'

type Message = {
  role: 'user' | 'assistant'
  content: string
  products?: ProductCard[]
  /** Quick replies for a clarifying question; shown only on the latest message. */
  suggestions?: string[]
}

const GREETING: Message = {
  role: 'assistant',
  content:
    "Hey! I'm the Campus Customs shop assistant. Ask me for a color, a size, a team, or a budget and I'll dig through the catalogue.",
}

function greetingFor(firstName: string | null, returning: boolean): Message {
  if (!firstName) return GREETING
  return {
    role: 'assistant',
    content: returning
      ? `Welcome back, ${firstName}! Here's where we left off — ask me anything.`
      : `Hey ${firstName}! I'm the Campus Customs shop assistant. Ask me for a color, a size, a team, or a budget and I'll dig through the catalogue.`,
  }
}

export default function ChatWidget() {
  const { user } = useAuth()
  const { showResults } = useChatResults()
  const { view } = usePageContext()
  const location = useLocation()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([GREETING])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const logRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight })
  }, [messages, open])

  // Logged in: load this customer's saved conversation from the server so the
  // panel picks up where they left off. Logged out: start a fresh, unsaved
  // chat, so the next person on this browser never sees the previous customer's.
  const userId = user?.id ?? null
  const firstName = user?.first_name ?? null
  useEffect(() => {
    if (userId === null) {
      setMessages([GREETING])
      return
    }
    let cancelled = false
    fetchChatHistory()
      .then((history) => {
        if (cancelled) return
        const saved: Message[] = history.map((m) => ({
          role: m.role,
          content: m.content,
          products: m.products,
        }))
        setMessages([greetingFor(firstName, saved.length > 0), ...saved])
      })
      .catch(() => {
        if (!cancelled) setMessages([greetingFor(firstName, false)])
      })
    return () => {
      cancelled = true
    }
  }, [userId, firstName])

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    void sendMessage(draft)
  }

  async function sendMessage(raw: string) {
    const text = raw.trim()
    if (!text || sending) return

    const nextMessages: Message[] = [...messages, { role: 'user', content: text }]
    setMessages(nextMessages)
    setDraft('')
    setSending(true)

    // Send the running transcript (minus the opening greeting) so follow-ups
    // like "do you have that in navy?" resolve against earlier turns.
    // Earlier turns only: the new message goes separately as `message`.
    // (Sending it in both places made the agent see the question twice and
    // loop on the same lookup until it hit its request cap.)
    const history: ChatTurn[] = messages
      .slice(1)
      .map((m) => ({ role: m.role, content: m.content }))

    try {
      // Tell the assistant what's on screen so "this" / "these" can be resolved.
      const pageContext = { path: location.pathname, ...(view ?? {}) }
      const { reply, products, page_results, suggested_replies } = await sendChat(
        text,
        history,
        pageContext,
      )
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: reply, products, suggestions: suggested_replies },
      ])
      // A browse request ("what crewnecks do you have?") comes back with
      // page_results: hand them to the Products page and take the shopper there.
      // The chat panel stays open because it lives outside the routes.
      if (page_results) {
        showResults(page_results)
        navigate('/products')
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Sorry — ${(err as Error).message}` },
      ])
    } finally {
      setSending(false)
    }
  }

  if (!open) {
    return (
      <button className="chat-fab" onClick={() => setOpen(true)} aria-label="Open shop chat">
        ◆
      </button>
    )
  }

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <span className="dot" />
        <strong>Shop Assistant</strong>
        <button className="chat-close" onClick={() => setOpen(false)} aria-label="Close chat">
          ×
        </button>
      </div>

      <div className="chat-log" ref={logRef}>
        {messages.map((message, i) => (
          <div key={i} className={`bubble ${message.role}`}>
            <div className="bubble-text">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
            {message.products && message.products.length > 0 && (
              <div className="chat-cards">
                {message.products.map((p) => (
                  <Link
                    key={p.product_id}
                    to={`/products/${p.product_id}`}
                    className="chat-card"
                    onClick={() => setOpen(false)}
                  >
                    <img src={p.image_url} alt={p.name} loading="lazy" />
                    <div className="chat-card-meta">
                      <strong>{p.name}</strong>
                      <span className="chat-card-price">${p.price.toFixed(2)}</span>
                      {p.reason && <span className="chat-card-reason">{p.reason}</span>}
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        ))}
        {/* Tappable answers to the assistant's clarifying question. Only the
            latest message offers them, and they vanish once the shopper replies. */}
        {!sending && messages.at(-1)?.role === 'assistant' && (messages.at(-1)?.suggestions?.length ?? 0) > 0 && (
          <div className="chat-suggestions" aria-label="Suggested replies">
            {messages.at(-1)!.suggestions!.map((option) => (
              <button
                key={option}
                type="button"
                className="chat-suggestion"
                onClick={() => void sendMessage(option)}
              >
                {option}
              </button>
            ))}
          </div>
        )}
        {sending && <div className="bubble assistant muted">typing…</div>}
      </div>

      <form className="chat-form" onSubmit={handleSubmit}>
        <input
          className="input"
          placeholder={user ? `Ask away, ${user.first_name ?? 'friend'}…` : 'Ask about a product…'}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <button className="chat-send" type="submit" disabled={!draft.trim() || sending}>
          Send
        </button>
      </form>
    </div>
  )
}
