import { useEffect, useMemo, useRef, useState } from 'react'
import { fetchProducts, type Product } from '../api'

type Props = {
  title: string
  /** Products that can't be picked (e.g. the one already being compared). */
  excludeIds: string[]
  onPick: (productId: string) => void
  onClose: () => void
}

/** Modal grid for choosing a product, with a search box. Esc or backdrop closes. */
export default function ProductPicker({ title, excludeIds, onPick, onClose }: Props) {
  const [products, setProducts] = useState<Product[]>([])
  const [query, setQuery] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  // Callers pass a fresh onClose each render; keep the latest in a ref so the
  // setup below runs once instead of re-fetching the catalogue on every render.
  const closeRef = useRef(onClose)
  closeRef.current = onClose

  useEffect(() => {
    fetchProducts().then(setProducts).catch(() => setProducts([]))
    inputRef.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && closeRef.current()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const visible = useMemo(() => {
    const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean)
    return products.filter((p) => {
      if (excludeIds.includes(p.product_id)) return false
      const hay = [p.name, p.garment_type, ...p.colors, ...p.search_tags].join(' ').toLowerCase()
      return words.every((w) => hay.includes(w))
    })
  }, [products, query, excludeIds])

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2>{title}</h2>
          <button type="button" className="chat-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <input
          ref={inputRef}
          className="input"
          placeholder="Search — try 'hoodie', 'navy', 'Saybrook'…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <p className="muted picker-count">{visible.length} items</p>
        <div className="picker-grid">
          {visible.map((p) => (
            <button
              key={p.product_id}
              type="button"
              className="picker-item"
              onClick={() => onPick(p.product_id)}
            >
              <img src={p.image_url} alt="" loading="lazy" />
              <span className="picker-name">{p.name}</span>
              <span className="picker-price">${p.price.toFixed(2)}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
