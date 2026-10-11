import { useState } from 'react'
import type { Approval, BoardItem, Cash, Ticket } from '../api'
import { agentColor, agentLabel, describeApproval, money, statusLabel } from '../describe'

interface Props {
  tickets: Ticket[]
  board: BoardItem[]
  approvals: Approval[]
  cash: Cash | null
  onOpenTicket: (id: number) => void
}

const AUDIENCE_LABEL = { customer: 'To customer', vendor: 'To vendor', landlord: 'To landlord', internal: 'Internal' }
const time = (iso: string) => new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })

/** The board: per ticket, where it stands, what happened, money requests, and every drafted message. */
export function BoardView({ tickets, board, approvals, cash, onOpenTicket }: Props) {
  const open = tickets.filter((t) => !t.is_resolved)
  const done = tickets.filter((t) => t.is_resolved)
  const drafts = board.filter((b) => b.audience !== 'internal')
  const pending = approvals.filter((a) => a.status === 'pending')

  return (
    <div className="board">
      <div className="board__stats">
        <Stat label="Open tickets" value={open.length} tone="royal" />
        <Stat label="Drafted messages" value={drafts.length} tone="violet" note="saved, never sent" />
        <Stat label="Waiting on you" value={pending.length} tone={pending.length ? 'coral' : 'royal'} note={pending.length ? money(pending.reduce((s, a) => s + a.amount, 0)) : 'nothing pending'} />
        <Stat label="Checking" value={cash ? money(cash.balance) : '—'} tone="cobalt" />
      </div>

      {open.length === 0 && <p className="board__empty">No open tickets — everything is complete.</p>}
      {open.map((t) => (
        <TicketBoard key={t.id} ticket={t} items={board.filter((b) => b.ticket_id === t.id)}
          approvals={approvals.filter((a) => a.ticket_id === t.id)} onOpen={() => onOpenTicket(t.id)} />
      ))}

      {done.length > 0 && (
        <details className="board__done">
          <summary>Completed tickets ({done.length})</summary>
          {done.map((t) => (
            <TicketBoard key={t.id} ticket={t} items={board.filter((b) => b.ticket_id === t.id)}
              approvals={approvals.filter((a) => a.ticket_id === t.id)} onOpen={() => onOpenTicket(t.id)} />
          ))}
        </details>
      )}
    </div>
  )
}

function Stat({ label, value, tone, note }: { label: string; value: string | number; tone: string; note?: string }) {
  return (
    <div className={`stat stat--${tone}`}>
      <span className="stat__label">{label}</span>
      <strong className="stat__value">{value}</strong>
      {note && <span className="stat__note">{note}</span>}
    </div>
  )
}

function TicketBoard({ ticket, items, approvals, onOpen }: { ticket: Ticket; items: BoardItem[]; approvals: Approval[]; onOpen: () => void }) {
  const notes = items.filter((i) => i.audience === 'internal')
  const drafts = items.filter((i) => i.audience !== 'internal').slice().reverse() // newest first
  const latestNote = notes.at(-1)

  return (
    <article className={`tboard ${ticket.is_resolved ? 'tboard--done' : ''}`}>
      <header className="tboard__head">
        <span className="tboard__id">#{ticket.id}</span>
        <div className="tboard__title">
          <h3>{ticket.subject}</h3>
          <p>{ticket.requester} · {ticket.type.replace('_', ' ')}</p>
        </div>
        <span className={`stamp stamp--${ticket.status}`}>{statusLabel(ticket.status)}</span>
        <button className="btn btn--ghost" onClick={onOpen}>Open in agent desk →</button>
      </header>

      <div className="tboard__body">
        <section className="tboard__story">
          <h4 className="tboard__label">Where it stands</h4>
          {latestNote ? (
            <p className="tboard__latest">{latestNote.body}</p>
          ) : (
            <p className="muted">The team hasn't worked this ticket yet.</p>
          )}

          {notes.length > 0 && (
            <>
              <h4 className="tboard__label">What happened</h4>
              <ol className="timeline">
                {notes.map((n) => (
                  <li key={n.id}>
                    <span className="timeline__when">{time(n.created_at)}</span>
                    <span className="timeline__what">{n.subject.replace(/^Ticket \d+: /, '').replaceAll('_', ' ').replace('->', '→')}</span>
                  </li>
                ))}
              </ol>
            </>
          )}

          {approvals.length > 0 && (
            <>
              <h4 className="tboard__label">Money</h4>
              <ul className="money-list">
                {approvals.map((a) => (
                  <li key={a.id} className={`money money--${a.status}`}>
                    <span>{describeApproval(a)}</span>
                    <strong>{money(a.amount)}</strong>
                    <span className="money__status">{a.status === 'paid' ? `paid · approved by ${a.decided_by}` : a.status}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>

        <section className="tboard__drafts">
          <h4 className="tboard__label">Drafted messages <span className="badge badge--violet">{drafts.length}</span></h4>
          {drafts.length === 0 ? (
            <p className="muted">No drafts yet.</p>
          ) : (
            drafts.map((d, i) => <Draft key={d.id} item={d} latest={i === 0} />)
          )}
        </section>
      </div>
    </article>
  )
}

function Draft({ item, latest }: { item: BoardItem; latest: boolean }) {
  const [copied, setCopied] = useState(false)
  const [openBody, setOpenBody] = useState(latest)
  const copy = async () => {
    await navigator.clipboard.writeText(`Subject: ${item.subject}\n\n${item.body}`)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <div className={`bdraft ${latest ? 'bdraft--latest' : ''}`} style={{ ['--agent' as string]: agentColor(item.author_agent) }}>
      <button className="bdraft__head" onClick={() => setOpenBody((o) => !o)} aria-expanded={openBody}>
        <span className="bdraft__aud">{AUDIENCE_LABEL[item.audience]}</span>
        <span className="bdraft__to">{item.recipient}</span>
        {latest && <span className="bdraft__tag">Latest</span>}
        <span className="bdraft__when">{time(item.created_at)}</span>
      </button>
      <p className="bdraft__subject">“{item.subject}”</p>
      {openBody && <p className="bdraft__body">{item.body}</p>}
      <div className="bdraft__foot">
        <span className="bdraft__by">Drafted by {agentLabel(item.author_agent)} · not sent</span>
        <button className="btn btn--ghost btn--small" onClick={copy}>{copied ? 'Copied ✓' : 'Copy text'}</button>
      </div>
    </div>
  )
}
