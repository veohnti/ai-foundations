import type { AgentName } from '../api'
import { AGENTS, agentColor as cardColor, agentLabel, type AgentView, type Handoff } from '../describe'

// On the dark web background the boss's royal blue would disappear, so it glows periwinkle here.
const agentColor = (name: string | null | undefined) => (name === 'boss' ? 'rgb(150, 165, 255)' : cardColor(name))

// Node layout: boss on top, the four specialists around it. Every pair is connected (the web).
const POS: Record<AgentName, { x: number; y: number }> = {
  boss: { x: 410, y: 72 },
  inventory: { x: 135, y: 178 },
  accounting: { x: 685, y: 178 },
  facilities: { x: 255, y: 305 },
  customer_service: { x: 565, y: 305 },
}
const R = 38

/** Endpoints of a line between two nodes, trimmed so it starts and ends at the circles' edges. */
function segment(from: AgentName, to: AgentName, pad = R + 6) {
  const a = POS[from], b = POS[to]
  const dx = b.x - a.x, dy = b.y - a.y
  const len = Math.hypot(dx, dy)
  const ux = dx / len, uy = dy / len
  return { x1: a.x + ux * pad, y1: a.y + uy * pad, x2: b.x - ux * pad, y2: b.y - uy * pad, len: len - 2 * pad }
}

const PAIRS: [AgentName, AgentName][] = AGENTS.flatMap((a, i) => AGENTS.slice(i + 1).map((b) => [a.name, b.name] as [AgentName, AgentName]))

interface Props {
  views: Record<AgentName, AgentView>
  handoffs: Handoff[]
  liveSince: number // only animate "report back" pulses for events that happened while watching
  running: boolean
}

export function TeamWeb({ views, handoffs, liveSince, running }: Props) {
  const active = handoffs.filter((h) => h.finishIndex === null && running)
  const done = handoffs.filter((h) => h.finishIndex !== null)
  const latest = active.at(-1)
  const workingBoss = running && views.boss.status === 'working'

  const caption = latest
    ? { who: latest.from, text: `${agentLabel(latest.from)} → ${agentLabel(latest.to)}`, task: latest.task }
    : running
      ? { who: 'boss' as AgentName, text: workingBoss ? 'Boss is reading the ticket and deciding who to call' : 'Team is working', task: '' }
      : handoffs.length
        ? { who: 'boss' as AgentName, text: `Run finished · ${handoffs.length} hand-off${handoffs.length > 1 ? 's' : ''}`, task: '' }
        : null

  const goTo = (name: AgentName) => document.getElementById(`agent-${name}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })

  return (
    <section className="panel web">
      <div className="web__head">
        <h2 className="panel__title panel__title--inline">Team web</h2>
        <div className="web__legend">
          <span><i className="legend-line legend-line--live" /> handing off (lit while the teammate works)</span>
          <span><i className="legend-dot" /> reporting back</span>
          <span><i className="legend-line legend-line--done" /> finished hand-off</span>
        </div>
      </div>

      <div className="web__canvas">
        <svg viewBox="0 0 820 370" role="img" aria-label="Delegation web between the five agents">
          <defs>
            {AGENTS.map((a) => (
              <marker key={a.name} id={`arrow-${a.name}`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                <path d="M0,0 L10,5 L0,10 z" fill={agentColor(a.name)} />
              </marker>
            ))}
            <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="5" result="b" />
              <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>

          {/* the web: every agent can reach every other */}
          {PAIRS.map(([a, b]) => {
            const s = segment(a, b, R)
            return <line key={`${a}-${b}`} className="web__strand" x1={s.x1} y1={s.y1} x2={s.x2} y2={s.y2} />
          })}

          {/* finished hand-offs: solid line in the sender's color */}
          {done.map((h) => {
            const s = segment(h.from, h.to)
            return (
              <line key={`done-${h.key}`} className="web__done" x1={s.x1} y1={s.y1} x2={s.x2} y2={s.y2}
                stroke={agentColor(h.from)} markerEnd={`url(#arrow-${h.from})`} />
            )
          })}

          {/* live hand-offs: glowing, dashes flowing toward the teammate */}
          {active.map((h) => {
            const s = segment(h.from, h.to)
            return (
              <g key={`live-${h.key}`} filter="url(#glow)">
                <line className="web__halo" x1={s.x1} y1={s.y1} x2={s.x2} y2={s.y2} stroke={agentColor(h.from)} />
                <line className="web__live" x1={s.x1} y1={s.y1} x2={s.x2} y2={s.y2} stroke={agentColor(h.from)} markerEnd={`url(#arrow-${h.from})`} />
              </g>
            )
          })}

          {/* report-back pulse: a bright streak running from the teammate back to whoever asked */}
          {done.filter((h) => (h.finishIndex ?? -1) > liveSince).map((h) => {
            const s = segment(h.to, h.from)
            return (
              <line key={`reply-${h.key}`} className="web__reply" x1={s.x1} y1={s.y1} x2={s.x2} y2={s.y2}
                stroke={agentColor(h.to)} style={{ ['--len' as string]: s.len }} />
            )
          })}

          {AGENTS.map((a) => {
            const v = views[a.name]
            const p = POS[a.name]
            const status = running || v.status !== 'working' ? v.status : 'done'
            return (
              <g key={a.name} className={`node node--${status}`} style={{ ['--c' as string]: agentColor(a.name) }}
                transform={`translate(${p.x} ${p.y})`} onClick={() => goTo(a.name)} role="button" tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && goTo(a.name)}>
                <title>{`${a.label}: ${status} — click to jump to its card`}</title>
                {status === 'working' && <circle className="node__ring" r={R} />}
                <circle className="node__disc" r={R} />
                <text className="node__initials" dy="7">{a.initials}</text>
                <text className="node__label" y={R + 22}>{a.label}</text>
                {status === 'done' && (
                  <g transform={`translate(${R * 0.72} ${-R * 0.72})`}>
                    <circle className="node__badge" r="11" />
                    <path d="M-5 0 L-1 4 L5 -4" className="node__check" />
                  </g>
                )}
              </g>
            )
          })}
        </svg>
      </div>

      <div className="web__now" style={{ ['--c' as string]: agentColor(caption?.who) }}>
        <span className="eyebrow">{running ? 'Right now' : 'Status'}</span>
        <strong>{caption?.text ?? 'Pick a ticket and start the team to see hand-offs light up.'}</strong>
        {caption?.task && <span className="web__task">“{caption.task}”</span>}
      </div>

      {handoffs.length > 0 && (
        <ol className="handoffs">
          {handoffs.map((h) => (
            <li key={h.key} className={`handoff ${h.finishIndex === null && running ? 'handoff--live' : ''}`}
              style={{ ['--from' as string]: agentColor(h.from), ['--to' as string]: agentColor(h.to) }}
              title={`${h.task}${h.answer ? `\n\nReported back: ${h.answer}` : ''}`}>
              <span className="handoff__n">{h.order}</span>
              <span className="handoff__from">{agentLabel(h.from)}</span>
              <span className="handoff__arrow">→</span>
              <span className="handoff__to">{agentLabel(h.to)}</span>
              <span className="handoff__state">{h.finishIndex === null ? (running ? 'working…' : 'stopped') : 'reported back ✓'}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
