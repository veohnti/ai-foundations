import { useEffect, useRef, useState } from 'react'
import type { Cash } from '../api'
import { money } from '../describe'

/** Checking balance. When it drops after an approval, the change is shown for a few seconds. */
export function CashCard({ cash }: { cash: Cash | null }) {
  const last = useRef<number | null>(null)
  const [delta, setDelta] = useState<number | null>(null)

  useEffect(() => {
    if (!cash) return
    if (last.current !== null && cash.balance !== last.current) {
      setDelta(cash.balance - last.current)
      const t = setTimeout(() => setDelta(null), 6000)
      last.current = cash.balance
      return () => clearTimeout(t)
    }
    last.current = cash.balance
  }, [cash])

  return (
    <div className={`cash-card ${delta ? 'cash-card--changed' : ''}`}>
      <span className="eyebrow">Checking</span>
      <strong className="cash-card__amount">{cash ? money(cash.balance) : '—'}</strong>
      <span className="cash-card__meta">
        {delta ? <em className="cash-card__delta">{delta < 0 ? '−' : '+'}{money(Math.abs(delta))}</em> : cash ? `as of ${cash.as_of}` : 'loading'}
      </span>
    </div>
  )
}
