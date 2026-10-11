import type { BossDecision } from '../api'
import { AGENTS, statusLabel, type AgentView } from '../describe'
import type { AgentName } from '../api'

/** Short "what each agent did" recap, shown once the run on this ticket has finished. */
export function RunSummary({ views, decision }: { views: Record<AgentName, AgentView>; decision?: BossDecision | null }) {
  const worked = AGENTS.filter((a) => views[a.name].calls > 0)
  if (!worked.length) return null
  const boss = views.boss.output

  return (
    <section className="panel summary">
      <h2 className="panel__title">Run summary</h2>
      {(decision || boss) && (
        <div className="verdict">
          <span className="eyebrow">Boss's final call</span>
          <p className="verdict__text">{decision?.final_decision ?? boss?.final_decision}</p>
          {(decision?.new_status ?? boss?.new_status) && (
            <span className={`stamp stamp--${decision?.new_status ?? boss?.new_status}`}>
              {statusLabel(String(decision?.new_status ?? boss?.new_status))}
            </span>
          )}
          {!!(decision?.next_steps ?? boss?.next_steps)?.length && (
            <ul className="verdict__steps">
              {(decision?.next_steps ?? boss?.next_steps ?? []).map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          )}
        </div>
      )}
      <table className="summary__table">
        <thead>
          <tr><th>Agent</th><th>What it did</th><th>MCP tools</th></tr>
        </thead>
        <tbody>
          {worked.map((a) => {
            const v = views[a.name]
            return (
              <tr key={a.name}>
                <td className="summary__agent" style={{ ['--agent' as string]: a.color }}><span>{a.label}</span></td>
                <td>
                  {v.outputs.length === 0 && '—'}
                  {v.outputs.map((o, i) => (
                    <p key={i} className="summary__line">{a.name === 'boss' ? o.final_decision : o.summary}</p>
                  ))}
                  {v.drafts.map((d, i) => (
                    <details key={i} className="draft">
                      <summary>Draft to {d.recipient} · “{d.subject}” <em>(not sent)</em></summary>
                      <p>{d.body}</p>
                    </details>
                  ))}
                </td>
                <td>
                  <div className="chips">{v.toolsUsed.map((t) => <code key={t} className="chip">{t}</code>)}</div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}
