import { useEffect, useRef } from 'react'
import { agentColor, type AgentView } from '../describe'

const KIND_LABEL = { asked: 'Asked', thinking: 'Thinking', doing: 'Doing', saying: 'Saying', problem: 'Problem' }
const STATUS_LABEL = { idle: 'Idle', working: 'Working', done: 'Done', problem: 'Stopped' }

export function AgentCard({ label, role, color, view, featured }: { label: string; role: string; color: string; view: AgentView; featured?: boolean }) {
  const feedRef = useRef<HTMLOListElement>(null)

  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight, behavior: 'smooth' })
  }, [view.feed.length])

  return (
    <article id={`agent-${view.name}`} className={`agent agent--${view.status} ${featured ? 'agent--featured' : ''}`}
      style={{ ['--agent' as string]: color }}>
      <header className="agent__head">
        <div>
          <h3 className="agent__name">{label}</h3>
          <p className="agent__role">{role}</p>
        </div>
        <span className={`agent__status agent__status--${view.status}`}>
          <i className="dot" /> {STATUS_LABEL[view.status]}
        </span>
      </header>
      {view.feed.length === 0 ? (
        <p className="agent__empty">Not called on yet.</p>
      ) : (
        <ol className="feed" ref={feedRef}>
          {view.feed.map((item) => (
            <li key={item.key} className={`feed__item feed__item--${item.kind} ${item.refused ? 'feed__item--refused' : ''}`}
              style={item.from ? { ['--from' as string]: agentColor(item.from) } : undefined}>
              <span className="feed__kind">{KIND_LABEL[item.kind]}</span>
              <span className="feed__text">
                {item.text}
                {item.detail && <span className="feed__detail">“{item.detail}”</span>}
              </span>
            </li>
          ))}
          {view.status === 'working' && (
            <li className="feed__item feed__item--typing">
              <span className="feed__kind">…</span>
              <span className="caret" />
            </li>
          )}
        </ol>
      )}
    </article>
  )
}
