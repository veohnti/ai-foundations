import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchProducts, type Product } from '../api'

const STRIP = [
  'saybrook-college-crewneck',
  'yale-sports-hoodie-tennis',
  'morse-1-4-zip',
  'boola-boola-t-shirt',
  'benjamin-franklin-fleece-jacket',
]

export default function About() {
  const [products, setProducts] = useState<Product[]>([])
  useEffect(() => {
    fetchProducts().then(setProducts).catch(() => setProducts([]))
  }, [])
  const strip = STRIP.map((id) => products.find((p) => p.product_id === id)).filter(
    (p): p is Product => !!p,
  )

  return (
    <div className="page">
      <span className="eyebrow">About Us</span>
      <h1>
        We make Yale apparel. <span className="accent">That's the whole thing.</span>
      </h1>

      {strip.length > 0 && (
        <div className="photo-strip">
          {strip.map((p) => (
            <Link key={p.product_id} to={`/products/${p.product_id}`}>
              <img src={p.image_url} alt={p.name} loading="lazy" />
            </Link>
          ))}
        </div>
      )}

      <p style={{ maxWidth: '680px', fontSize: '1.1rem' }}>
        Campus Customs started in 2024 out of a dorm room in New Haven, mostly because we were
        tired of the same three hoodie designs showing up everywhere on campus. We do custom
        collegiate apparel — hoodies, crewneck sweatshirts, quarter-zips, fleece jackets, and
        t-shirts — all of it Yale, all of it stuff we'd wear ourselves.
      </p>

      <p style={{ maxWidth: '680px' }}>
        The lineup is 102 pieces and counting: residential colleges, varsity teams, the
        professional schools, The Game, and the family set for whoever at home keeps asking
        you to send something. Prices stay boring on purpose — $32 for a tee, $58 for a
        crewneck, $68 for a hoodie, $98 if you want the jacket. No surprise checkout math.
      </p>

      <div className="card-grid" style={{ marginTop: '2.5rem' }}>
        <div className="info-card">
          <h3>Founded</h3>
          <p>2024, New Haven. Started small, still small, fine with that.</p>
        </div>
        <div className="info-card">
          <h3>What we do</h3>
          <p>
            Custom collegiate apparel — mainly fleece and knit: hoodies, crewnecks,
            quarter-zips, jackets, and tees.
          </p>
        </div>
        <div className="info-card">
          <h3>How we do it</h3>
          <p>
            Real stock counts on every size, honest answers about colors, and a chatbot that
            says "we don't have that" when we don't have that.
          </p>
        </div>
        <div className="info-card">
          <h3>Who it's for</h3>
          <p>
            Students, alumni, parents, and the uncle who has never been to campus but wants
            the sweatshirt anyway.
          </p>
        </div>
      </div>

      <section style={{ marginTop: '3rem' }}>
        <h2>The short version</h2>
        <p className="muted" style={{ maxWidth: '680px' }}>
          Good blanks, clean graphics, sizes that actually exist, and nobody trying to upsell
          you a lanyard at checkout. If you want help picking something, the chat box in the
          corner knows the whole catalogue better than we do.
        </p>
        <div className="hero-actions" style={{ marginTop: '1.25rem' }}>
          <Link className="btn" to="/products">
            Go see the goods
          </Link>
        </div>
      </section>
    </div>
  )
}
