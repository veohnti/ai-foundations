import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { fetchProduct, type ProductDetail } from '../api'
import ProductPicker from '../components/ProductPicker'
import { usePageContext } from '../pageContext'

const SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL']

type Side = 'left' | 'right'

/** Side-by-side comparison of two products: /compare/:leftId/:rightId */
export default function Compare() {
  const { leftId, rightId } = useParams<{ leftId: string; rightId: string }>()
  const navigate = useNavigate()
  const { setView } = usePageContext()
  const [left, setLeft] = useState<ProductDetail | null>(null)
  const [right, setRight] = useState<ProductDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [changing, setChanging] = useState<Side | null>(null)

  useEffect(() => {
    if (!leftId || !rightId) return
    setError(null)
    Promise.all([fetchProduct(leftId), fetchProduct(rightId)])
      .then(([l, r]) => {
        setLeft(l)
        setRight(r)
      })
      .catch((err: Error) => setError(err.message))
  }, [leftId, rightId])

  // Let the chat assistant know which two products are on screen, so "which of
  // these is warmer?" or "is the left one cheaper?" can be answered.
  useEffect(() => {
    if (!leftId || !rightId) return
    setView({ comparing_product_ids: [leftId, rightId] })
    return () => setView(null)
  }, [leftId, rightId, setView])

  if (error) {
    return (
      <div className="page">
        <p className="state error">Couldn't load these products ({error}).</p>
        <Link className="btn ghost" to="/products">
          Back to products
        </Link>
      </div>
    )
  }
  if (!left || !right) {
    return (
      <div className="page">
        <p className="state">Loading…</p>
      </div>
    )
  }

  const pair = [left, right]
  const cheaper =
    left.price === right.price ? null : left.price < right.price ? left.product_id : right.product_id
  const shared = left.colors.filter((c) => right.colors.includes(c))

  function pick(productId: string) {
    if (!changing) return
    const next = changing === 'left' ? [productId, right!.product_id] : [left!.product_id, productId]
    setChanging(null)
    navigate(`/compare/${next[0]}/${next[1]}`)
  }

  return (
    <div className="page">
      <span className="eyebrow">Compare</span>
      <h1>Side by side</h1>
      <p className="muted">
        Swap either item to compare something else. Prices and stock are live from the shop.
      </p>

      <div className="compare-actions">
        <button
          type="button"
          className="btn ghost"
          onClick={() => navigate(`/compare/${right.product_id}/${left.product_id}`)}
        >
          ⇄ Swap sides
        </button>
      </div>

      <div className="compare-grid">
        {pair.map((p, i) => {
          const side: Side = i === 0 ? 'left' : 'right'
          return (
            <div key={side} className="compare-col">
              <Link to={`/products/${p.product_id}`} className="compare-image">
                <img src={p.image_url} alt={p.name} />
              </Link>
              <h2 className="compare-name">
                <Link to={`/products/${p.product_id}`}>{p.name}</Link>
              </h2>
              <button type="button" className="btn ghost compare-change" onClick={() => setChanging(side)}>
                Change item
              </button>
            </div>
          )
        })}
      </div>

      <table className="compare-table">
        <tbody>
          <tr>
            <th scope="row">Price</th>
            {pair.map((p) => (
              <td key={p.product_id}>
                <span className="compare-price">${p.price.toFixed(2)}</span>
                {cheaper === p.product_id && <span className="compare-badge">Lower price</span>}
                {cheaper === null && <span className="compare-badge neutral">Same price</span>}
              </td>
            ))}
          </tr>
          <tr>
            <th scope="row">Type</th>
            {pair.map((p) => (
              <td key={p.product_id} className="cap">
                {p.garment_type}
              </td>
            ))}
          </tr>
          <tr>
            <th scope="row">Colors</th>
            {pair.map((p) => (
              <td key={p.product_id}>
                <div className="chip-row">
                  {p.colors.map((c) => (
                    <span key={c} className={`chip ${shared.includes(c) ? 'chip-shared' : ''}`}>
                      {c}
                    </span>
                  ))}
                </div>
              </td>
            ))}
          </tr>
          <tr>
            <th scope="row">Sizes in stock</th>
            {pair.map((p) => (
              <td key={p.product_id}>
                <div className="compare-sizes">
                  {SIZES.map((size) => {
                    const s = p.sizes.find((x) => x.size === size)
                    const qty = s?.quantity ?? 0
                    return (
                      <span
                        key={size}
                        className={`compare-size ${qty > 0 ? '' : 'out'}`}
                        title={qty > 0 ? `${qty} in stock` : 'Sold out'}
                      >
                        {size}
                        <small>{qty > 0 ? qty : '—'}</small>
                      </span>
                    )
                  })}
                </div>
              </td>
            ))}
          </tr>
          <tr>
            <th scope="row">Total in stock</th>
            {pair.map((p) => (
              <td key={p.product_id}>
                {p.sizes.reduce((sum, s) => sum + s.quantity, 0)} units
              </td>
            ))}
          </tr>
          <tr>
            <th scope="row">Description</th>
            {pair.map((p) => (
              <td key={p.product_id} className="compare-desc">
                {p.description}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
      {shared.length > 0 && (
        <p className="muted compare-note">Highlighted colors are available in both.</p>
      )}

      {changing && (
        <ProductPicker
          title={`Pick the ${changing} item`}
          excludeIds={[left.product_id, right.product_id]}
          onPick={pick}
          onClose={() => setChanging(null)}
        />
      )}
    </div>
  )
}
