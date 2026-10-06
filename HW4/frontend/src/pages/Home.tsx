import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchProducts, type Product } from '../api'
import Carousel from '../components/Carousel'
import modelCrestCap from '../assets/model-crest-cap.webp'
import modelCrewneck from '../assets/model-crewneck.webp'

// Hand-picked so the carousel shows the range: every garment type, colleges,
// sports, The Game, and the family pieces.
const FEATURED = [
  'basic-hoodie-big-yale',
  '2025-yale-vs-harvard-t-shirt',
  'super-heavyweight-crewneck-arched-yale-crest',
  'branford-1-4-zip',
  'brooks-brothers-bomber-jacket-yale',
  'district-vit-hoodie-vintage-sailor-bulldog',
  'saybrook-college-crewneck',
  't-felt-y-heavyweight',
  'school-of-music-fleece-sweater',
  'yale-mom-hoodie',
  'yale-sports-crewneck-volleyball',
  'yale-bowl-t-shirt',
]

const CATEGORIES = [
  { value: 'crewneck', label: 'Crewnecks', blurb: 'The everyday sweatshirt', image: 'super-heavyweight-crewneck-arched-yale-crest' },
  { value: 'hood', label: 'Hoodies', blurb: 'For the walk up Science Hill', image: 'district-vit-hoodie-vintage-sailor-bulldog' },
  { value: 't-shirt', label: 'T-shirts', blurb: 'Game days and gym days', image: '2025-yale-vs-harvard-t-shirt' },
  { value: 'zip', label: 'Zips & jackets', blurb: 'Quarter-zips, fleece, bombers', image: 'school-of-public-health-1-4-zip' },
]

const FAMILY = ['yale-mom-hoodie', 'yale-dad-crewneck', 'yale-grandpa-crewneck', 'yale-aunt-hoodie']

export default function Home() {
  const [products, setProducts] = useState<Product[]>([])

  useEffect(() => {
    fetchProducts().then(setProducts).catch(() => setProducts([]))
  }, [])

  const byId = useMemo(() => new Map(products.map((p) => [p.product_id, p])), [products])
  const pick = (ids: string[]) => ids.map((id) => byId.get(id)).filter((p): p is Product => !!p)

  return (
    <div className="page">
      {/* Editorial banner, Loewe-style: two model shots side by side, full
          width, with an oversized wordmark overlapping the top-left. */}
      <section className="banner" aria-label="Campus Customs, worn on campus">
        <div className="banner-photo">
          <img src={modelCrestCap} alt="Model in a gray Yale University crest sweatshirt and denim cap" />
        </div>
        <div className="banner-photo">
          <img src={modelCrewneck} alt="Model in a heather gray Yale crest crewneck" />
        </div>
        <p className="banner-wordmark" aria-hidden="true">
          Campus <em>Customs</em>
        </p>
        <span className="banner-tag">New Haven · Est. 2024</span>
      </section>

      {/* Headline sits under the photos so it never covers the sweatshirts. */}
      <div className="banner-intro">
        <div>
          <h1>Yale gear that doesn't look like a gift shop.</h1>
          <p>
            Hoodies, crewnecks, quarter-zips, and tees you'd actually wear to a 9am. Real stock,
            honest answers, six sizes on everything.
          </p>
        </div>
        <div className="hero-actions">
          <Link className="btn" to="/products">
            Shop the catalogue
          </Link>
          <Link className="btn ghost" to="/about">
            Who we are
          </Link>
        </div>
      </div>

      <section className="home-section">
        <div className="section-head">
          <h2>Fresh off the rack</h2>
          <Link to="/products" className="section-link">
            See all 102 →
          </Link>
        </div>
        <Carousel products={pick(FEATURED)} />
      </section>

      <section className="home-section">
        <h2>Shop by category</h2>
        <div className="category-grid">
          {CATEGORIES.map((c) => {
            const p = byId.get(c.image)
            return (
              <Link key={c.value} to={`/products?category=${c.value}`} className="category-tile">
                <div className="category-image">{p && <img src={p.image_url} alt="" loading="lazy" />}</div>
                <div className="category-text">
                  <strong>{c.label}</strong>
                  <span>{c.blurb}</span>
                </div>
              </Link>
            )
          })}
        </div>
      </section>

      <section className="home-section">
        <h2>Why bother with us</h2>
        <div className="card-grid">
          <div className="info-card">
            <h3>Everything in six sizes</h3>
            <p>
              XS through XXL on every single piece. No "only XS left" energy — and the site
              shows you real stock numbers, not a vibe.
            </p>
          </div>
          <div className="info-card">
            <h3>Residential colleges included</h3>
            <p>
              Saybrook, Morse, Davenport, Grace Hopper, TD, Benjamin Franklin — your college
              is in here somewhere, and so is the one you lost to in IMs.
            </p>
          </div>
          <div className="info-card">
            <h3>Game day covered</h3>
            <p>
              The Game, every varsity team, and the sports you forgot Yale had. Yes, squash.
              Yes, field hockey.
            </p>
          </div>
          <div className="info-card">
            <h3>Ask before you buy</h3>
            <p>
              There's a chat box in the corner. Ask it for "something navy under $60" and let
              it do the scrolling for you.
            </p>
          </div>
        </div>
      </section>

      <section className="home-section family-band">
        <div className="family-text">
          <h2>Fits for every kind of Yalie</h2>
          <p className="muted">
            Grandpa crewnecks for people who run cold. Tri-blend tees for people who run hot.
            Fleece jackets for the four days a year New Haven decides to be a tundra. Plus the
            mom / dad / brother / sister / uncle set, because somebody at home is definitely
            asking.
          </p>
          <Link className="btn" to="/products">
            Browse all 102 pieces
          </Link>
        </div>
        <div className="family-images">
          {pick(FAMILY).map((p) => (
            <Link key={p.product_id} to={`/products/${p.product_id}`} className="family-tile">
              <img src={p.image_url} alt={p.name} loading="lazy" />
              <span>{p.name}</span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}
