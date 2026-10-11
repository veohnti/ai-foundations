import type { Approval } from '../api'
import { agentLabel, describeApproval, money } from '../describe'

interface Props {
  pending: Approval[]
  busyId: number | null
  onApprove: (id: number) => void
  onDeny: (id: number) => void
}

/** Requests the agents prepared. Approving is what actually pays (backend route d). */
export function ApprovalPanel({ pending, busyId, onApprove, onDeny }: Props) {
  return (
    <section className={`panel approvals ${pending.length ? 'approvals--waiting' : ''}`}>
      <h2 className="panel__title">
        Your approval {pending.length ? <span className="badge">{pending.length}</span> : null}
      </h2>
      {pending.length === 0 ? (
        <p className="muted">Nothing waiting. Agents can only prepare payments — money moves when you approve.</p>
      ) : (
        <ul className="approval-list">
          {pending.map((a) => (
            <li key={a.id} className="approval">
              <div className="approval__head">
                <span className="approval__what">{describeApproval(a)}</span>
                <strong className="approval__amount">{money(a.amount)}</strong>
              </div>
              <p className="approval__reason">{a.reason}</p>
              <p className="approval__meta">
                #{a.id} · ticket {a.ticket_id ?? '—'} · prepared by {agentLabel(a.requested_by)}
              </p>
              <div className="approval__actions">
                <button className="btn btn--primary" disabled={busyId !== null} onClick={() => onApprove(a.id)}>
                  {busyId === a.id ? 'Paying…' : 'Approve & pay'}
                </button>
                <button className="btn btn--ghost" disabled={busyId !== null} onClick={() => onDeny(a.id)}>
                  Deny
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
