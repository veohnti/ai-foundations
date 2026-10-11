import type { Ticket } from '../api'
import { statusLabel } from '../describe'

interface Props {
  tickets: Ticket[]
  selectedId: number | null
  runningTicketId: number | null
  onSelect: (id: number) => void
}

export function TicketList({ tickets, selectedId, runningTicketId, onSelect }: Props) {
  return (
    <section className="panel">
      <h2 className="panel__title">Tickets</h2>
      <ul className="ticket-list">
        {tickets.map((t) => (
          <li key={t.id}>
            <button
              className={`ticket ${t.id === selectedId ? 'ticket--selected' : ''} ${t.is_resolved ? 'ticket--done' : ''}`}
              onClick={() => onSelect(t.id)}
            >
              <span className="ticket__id">#{t.id}</span>
              <span className="ticket__body">
                <span className="ticket__subject">{t.subject}</span>
                <span className="ticket__requester">{t.requester}</span>
                <span className={`stamp stamp--${t.id === runningTicketId ? 'working' : t.status}`}>
                  {t.id === runningTicketId ? 'Agents working' : statusLabel(t.status)}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
