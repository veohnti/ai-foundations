import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { Product } from '../api'

type Props = {
  products: Product[]
  /** ms between automatic slides */
  interval?: number
}

function usePerView() {
  const pick = () => {
    const w = window.innerWidth
    return w >= 1000 ? 4 : w >= 720 ? 3 : w >= 480 ? 2 : 1
  }
  const [perView, setPerView] = useState(pick)
  useEffect(() => {
    const onResize = () => setPerView(pick())
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])
  return perView
}

/**
 * Sliding row of product cards. Advances one card at a time, loops, and pauses
 * while hovered or keyboard-focused. With "reduce motion" on it still advances,
 * but switches instantly instead of sliding (see the CSS). Arrows and dots work
 * with mouse and keyboard.
 */
export default function Carousel({ products, interval = 2800 }: Props) {
  const perView = usePerView()
  const positions = Math.max(1, products.length - perView + 1)
  const [index, setIndex] = useState(0)
  const [paused, setPaused] = useState(false)
  useEffect(() => {
    if (index >= positions) setIndex(0)
  }, [positions, index])

  useEffect(() => {
    if (paused || positions <= 1) return
    const id = window.setInterval(() => setIndex((i) => (i + 1) % positions), interval)
    return () => window.clearInterval(id)
  }, [paused, positions, interval])

  const go = (i: number) => setIndex(((i % positions) + positions) % positions)

  if (products.length === 0) return null

  return (
    <div
      className="carousel"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={(e) => e.target.matches(':focus-visible') && setPaused(true)}
      onBlur={() => setPaused(false)}
      aria-roledescription="carousel"
    >
      <button type="button" className="carousel-arrow prev" onClick={() => go(index - 1)} aria-label="Previous">
        ‹
      </button>
      <div className="carousel-viewport">
        <div
          className="carousel-track"
          style={{ transform: `translateX(-${(index * 100) / perView}%)` }}
        >
          {products.map((p, i) => (
            <Link
              key={p.product_id}
              to={`/products/${p.product_id}`}
              className="carousel-slide"
              style={{ flexBasis: `${100 / perView}%` }}
              aria-hidden={i < index || i >= index + perView}
              tabIndex={i < index || i >= index + perView ? -1 : 0}
            >
              <div className="carousel-card">
                <div className="carousel-thumb">
                  <img src={p.image_url} alt={p.name} />
                </div>
                <div className="carousel-meta">
                  <span className="carousel-type">{p.garment_type}</span>
                  <strong>{p.name}</strong>
                  <span className="carousel-price">${p.price.toFixed(2)}</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>
      <button type="button" className="carousel-arrow next" onClick={() => go(index + 1)} aria-label="Next">
        ›
      </button>
      <div className="carousel-dots" role="tablist">
        {Array.from({ length: positions }, (_, i) => (
          <button
            key={i}
            type="button"
            className={`carousel-dot ${i === index ? 'active' : ''}`}
            onClick={() => go(i)}
            aria-label={`Go to slide ${i + 1}`}
            aria-selected={i === index}
            role="tab"
          />
        ))}
      </div>
    </div>
  )
}
