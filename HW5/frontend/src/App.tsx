import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, type Approval, type BoardItem, type Cash, type DeskEvent, type RunInfo, type Ticket } from './api'
import { AgentCard } from './components/AgentCard'
import { ApprovalPanel } from './components/ApprovalPanel'
import { BoardView } from './components/BoardView'
import { CashCard } from './components/CashCard'
import { RunSummary } from './components/RunSummary'
import { TeamWeb } from './components/TeamWeb'
import { TicketList } from './components/TicketList'
import { AGENTS, buildAgentViews, buildHandoffs, statusLabel } from './describe'

const POLL_MS = 1000

/** run_id -> ticket_id, from the events themselves (works for runs from before a page reload). */
function ticketOfRun(events: DeskEvent[]): Map<string, number> {
  const map = new Map<string, number>()
  for (const e of events) if (e.ticket_id != null && !map.has(e.run_id) && e.agent) map.set(e.run_id, e.ticket_id)
  return map
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [deskDate, setDeskDate] = useState('')
  const [cash, setCash] = useState<Cash | null>(null)
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [board, setBoard] = useState<BoardItem[]>([])
  const [tab, setTab] = useState<'desk' | 'board'>('desk')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  // ticket -> its runs since the last database reset (first pass, follow-ups...)
  const [ticketRuns, setTicketRuns] = useState<Record<number, string[]>>({})
  const [eventsByRun, setEventsByRun] = useState<Record<string, DeskEvent[]>>({})
  const [runInfo, setRunInfo] = useState<Record<string, RunInfo>>({})
  const [active, setActive] = useState<{ runId: string; ticketId: number } | null>(null)
  const [busyApproval, setBusyApproval] = useState<number | null>(null)
  const [notice, setNotice] = useState<{ tone: 'ok' | 'error'; text: string } | null>(null)
  const nextIndex = useRef(0)
  const [compact, setCompact] = useState(false) // header shrinks once you scroll
  const [liveSince, setLiveSince] = useState(Number.MAX_SAFE_INTEGER) // events after page load animate

  const refreshDesk = useCallback(async () => {
    const [t, c, a, b] = await Promise.all([api.tickets(), api.cash(), api.approvals(), api.board()])
    setTickets(t.tickets)
    setDeskDate(t.desk_date_today)
    setCash(c)
    setApprovals(a.approvals)
    setBoard(b.board)
    setSelectedId((id) => id ?? t.tickets[0]?.id ?? null)
  }, [])

  useEffect(() => {
    const onScroll = () => setCompact(window.scrollY > 40)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // First load: desk state + the last run for each ticket from the audit trail.
  useEffect(() => {
    ;(async () => {
      try {
        await refreshDesk()
        const all = await api.events({})
        const lastReset = Math.max(-1, ...all.events.filter((e) => e.event === 'database_reset').map((e) => e.index))
        const fresh = all.events.filter((e) => e.index > lastReset)
        const owner = ticketOfRun(fresh)
        const byRun: Record<string, DeskEvent[]> = {}
        const runs: Record<number, string[]> = {}
        for (const e of fresh) {
          const tid = owner.get(e.run_id)
          if (tid == null) continue
          if (!byRun[e.run_id]) (runs[tid] ??= []).push(e.run_id)
          ;(byRun[e.run_id] ??= []).push(e)
        }
        setEventsByRun(byRun)
        setTicketRuns(runs)
        nextIndex.current = all.next
        setLiveSince(all.next - 1)
        const running = all.runs.find((r) => r.state === 'running')
        if (running) setActive({ runId: running.run_id, ticketId: running.ticket_id })
      } catch (err) {
        setNotice({ tone: 'error', text: `Can't reach the backend at http://localhost:8000 (${(err as Error).message}).` })
      }
    })()
  }, [refreshDesk])

  // While a run is going: pull new events every second, plus approvals and cash.
  useEffect(() => {
    if (!active) return
    let stopped = false
    const tick = async () => {
      try {
        const [ev, info, a, b] = await Promise.all([
          api.events({ run_id: active.runId, after: nextIndex.current }),
          api.run(active.runId),
          api.approvals(),
          api.board(),
        ])
        if (stopped) return
        nextIndex.current = ev.next
        if (ev.events.length)
          setEventsByRun((prev) => ({ ...prev, [active.runId]: [...(prev[active.runId] ?? []), ...ev.events] }))
        setRunInfo((prev) => ({ ...prev, [active.runId]: info }))
        setApprovals(a.approvals)
        setBoard(b.board)
        if (info.state !== 'running') {
          setActive(null)
          await refreshDesk()
          setNotice(
            info.state === 'finished'
              ? { tone: 'ok', text: `Ticket #${active.ticketId}: the team finished.` }
              : { tone: 'error', text: `Ticket #${active.ticketId}: run ${info.state}. ${info.error ?? ''}` },
          )
        }
      } catch (err) {
        if (!stopped) setNotice({ tone: 'error', text: (err as Error).message })
      }
    }
    const id = setInterval(tick, POLL_MS)
    tick()
    return () => {
      stopped = true
      clearInterval(id)
    }
  }, [active, refreshDesk])

  const startRun = async (ticketId: number) => {
    setNotice(null)
    try {
      const r = await api.runTicket(ticketId)
      setEventsByRun((prev) => ({ ...prev, [r.run_id]: [] }))
      setTicketRuns((prev) => ({ ...prev, [ticketId]: [...(prev[ticketId] ?? []), r.run_id] }))
      setActive({ runId: r.run_id, ticketId })
    } catch (err) {
      setNotice({ tone: 'error', text: (err as Error).message })
    }
  }

  const decide = async (id: number, approve: boolean) => {
    setBusyApproval(id)
    try {
      const res = await (approve ? api.approve(id) : api.deny(id))
      await refreshDesk()
      setNotice({
        tone: 'ok',
        text: approve
          ? `Approved #${id}: paid $${Number(res.amount).toLocaleString('en-US', { minimumFractionDigits: 2 })} from checking.`
          : `Denied #${id}. No money moved.`,
      })
    } catch (err) {
      setNotice({ tone: 'error', text: `#${id} not approved: ${(err as Error).message}` })
      await refreshDesk()
    } finally {
      setBusyApproval(null)
    }
  }

  const reset = async () => {
    if (!window.confirm('Reset the shop database to its original values? Runs and approvals stay in the audit trail.')) return
    try {
      await api.reset()
      setTicketRuns({})
      await refreshDesk()
      setNotice({ tone: 'ok', text: 'Database reset to the original values. Ready for a fresh run.' })
    } catch (err) {
      setNotice({ tone: 'error', text: (err as Error).message })
    }
  }

  const pending = approvals.filter((a) => a.status === 'pending')
  const draftCount = board.filter((b) => b.audience !== 'internal').length
  const openTicket = (id: number) => {
    setSelectedId(id)
    setTab('desk')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
  const selected = tickets.find((t) => t.id === selectedId) ?? null
  const runIds = useMemo(() => (selected ? ticketRuns[selected.id] ?? [] : []), [selected, ticketRuns])
  const runId = runIds.at(-1)
  const runEvents = useMemo(() => runIds.flatMap((id) => eventsByRun[id] ?? []), [runIds, eventsByRun])
  const views = useMemo(() => buildAgentViews(runEvents), [runEvents])
  const handoffs = useMemo(() => buildHandoffs(runEvents), [runEvents])
  const isRunningHere = !!active && active.ticketId === selected?.id
  const runDone = !!runId && !isRunningHere && runEvents.some((e) => e.agent === 'boss' && e.event === 'agent_finished')
  const pendingHere = pending.filter((p) => p.ticket_id === selected?.id)
  const canContinue = selected?.status === 'waiting_on_approval' && pendingHere.length === 0 && !active
  const runLabel = isRunningHere
    ? 'Team at work…'
    : pendingHere.length
      ? 'Waiting on your approval'
      : canContinue
        ? 'Continue with the team'
        : runId
          ? 'Run the team again'
          : 'Start the agent team'

  return (
    <>
    <div className={`masthead-wrap ${compact ? 'masthead-wrap--compact' : ''}`}>
      <header className="masthead">
        <div>
          <h1 className="masthead__title">
            <span className="typebox">[C|A|M|P|U|S]</span> Customs
          </h1>
          <p className="masthead__sub">Agent desk · shop date {deskDate || '—'}</p>
        </div>
        <div className="masthead__right">
          <CashCard cash={cash} />
          <button className="btn btn--on-dark" onClick={reset} disabled={!!active}>
            Reset database
          </button>
        </div>
      </header>
      <div className="palette-strip" aria-hidden="true"><span /><span /><span /><span /><span /><span /><span /></div>
    </div>

    <div className="desk">

      {notice && (
        <div className={`notice notice--${notice.tone}`} role="status">
          {notice.text}
          <button className="notice__close" onClick={() => setNotice(null)} aria-label="Dismiss">×</button>
        </div>
      )}

      <div className="layout">
        <aside className="sidebar">
          <TicketList tickets={tickets} selectedId={tab === 'desk' ? selectedId : null} runningTicketId={active?.ticketId ?? null} onSelect={openTicket} />
          <ApprovalPanel pending={pending} busyId={busyApproval} onApprove={(id) => decide(id, true)} onDeny={(id) => decide(id, false)} />
        </aside>

        <main className="main">
          <nav className="tabs" role="tablist">
            <button role="tab" aria-selected={tab === 'desk'} className={`tab ${tab === 'desk' ? 'tab--on' : ''}`} onClick={() => setTab('desk')}>
              Agent desk {active && <span className="tab__live">live</span>}
            </button>
            <button role="tab" aria-selected={tab === 'board'} className={`tab ${tab === 'board' ? 'tab--on' : ''}`} onClick={() => setTab('board')}>
              Board <span className="badge badge--violet">{draftCount}</span>
            </button>
          </nav>

          {tab === 'board' && <BoardView tickets={tickets} board={board} approvals={approvals} cash={cash} onOpenTicket={openTicket} />}

          {tab === 'desk' && <>
          {selected && (
            <section className="ticket-head">
              <div>
                <span className="eyebrow">Ticket #{selected.id} · {selected.type.replace('_', ' ')}</span>
                <h2 className="ticket-head__title">{selected.subject}</h2>
                <p className="ticket-head__meta">
                  From {selected.requester}
                  {selected.sku && ` · ${selected.qty} × ${selected.sku} size ${selected.size}`}
                  {selected.invoice_id && ` · invoice ${selected.invoice_id}`}
                  {selected.lease_id && ` · lease ${selected.lease_id}`}
                </p>
              </div>
              <div className="ticket-head__actions">
                {selected.is_resolved ? (
                  <span className="stamp stamp--resolved stamp--big">Complete</span>
                ) : (
                  <span className={`stamp stamp--${selected.status}`}>{statusLabel(selected.status)}</span>
                )}
                {!selected.is_resolved && (
                  <button
                    className="btn btn--primary btn--big"
                    disabled={!!active || pendingHere.length > 0}
                    onClick={() => startRun(selected.id)}
                  >
                    {runLabel}
                  </button>
                )}
              </div>
            </section>
          )}

          {pendingHere.length > 0 && !isRunningHere && (
            <div className="callout">
              The team is waiting on you: {pendingHere.length} request{pendingHere.length > 1 ? 's' : ''} to approve or deny in the panel on the left.
            </div>
          )}

          <TeamWeb views={views} handoffs={handoffs} liveSince={liveSince} running={isRunningHere} />

          <section className="agents">
            {AGENTS.map((a) => (
              <AgentCard key={a.name} label={a.label} role={a.role} color={a.color} view={views[a.name]} featured={a.name === 'boss'} />
            ))}
          </section>

          {runDone && <RunSummary views={views} decision={runId ? runInfo[runId]?.decision : null} />}
          </>}
        </main>
      </div>
    </div>
    </>
  )
}
