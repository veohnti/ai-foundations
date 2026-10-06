import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { fetchProduct, type ProductDetail } from '../api'
import { usePageContext } from '../pageContext'
import ProductPicker from '../components/ProductPicker'

export default function ProductPage() {
  const { productId } = useParams<{ productId: string }>()
  const [product, setProduct] = useState<ProductDetail | null>(null)
  const [selectedSize, setSelectedSize] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { setView } = usePageContext()
  const navigate = useNavigate()
  const [picking, setPicking] = useState(false)

  // Tell the chat assistant which product is on screen (and the selected size),
  // so "do you have this in another color?" refers to this product.
  useEffect(() => {
    if (!productId) return
    setView({ viewing_product_id: productId, selected_size: selectedSize })
    return () => setView(null)
  }, [productId, selectedSize, setView])

  useEffect(() => {
    if (!productId) return
    setProduct(null)
    setSelectedSize(null)
    setError(null)
    fetchProduct(productId)
      .then(setProduct)
      .catch((err: Error) => setError(err.message))
  }, [productId])

  if (error) {
    return (
      <div className="page">
        <p className="state error">Couldn't load this product ({error}).</p>
        <Link className="btn ghost" to="/products">
          Back to products
        </Link>
      </div>
    )
  }

  if (!product) {
    return (
      <div className="page">
        <p className="state">Loading…</p>
      </div>
    )
  }

  const stock = product.sizes.find((s) => s.size === selectedSize)

  return (
    <div className="page">
      <Link to="/products" className="muted" style={{ fontSize: '0.9rem' }}>
        ← Back to all products
      </Link>

      <div className="detail" style={{ marginTop: '1.5rem' }}>
        <div className="detail-image">
          <img src={product.image_url} alt={product.name} />
        </div>

        <div>
          <span className="eyebrow">{product.garment_type}</span>
          <h1 style={{ fontSize: '2rem' }}>{product.name}</h1>
          <div className="detail-price">${product.price.toFixed(2)}</div>

          <p>{product.description}</p>

          <div className="detail-section">
            <h3>Colors</h3>
            <div className="chip-row">
              {product.colors.map((color) => (
                <span key={color} className="chip">
                  {color}
                </span>
              ))}
            </div>
          </div>

          <div className="detail-section">
            <h3>Sizes</h3>
            <div className="chip-row">
              {product.sizes.map((size) => (
                <button
                  key={size.size}
                  type="button"
                  disabled={!size.in_stock}
                  onClick={() => setSelectedSize(size.size)}
                  className={[
                    'size-btn',
                    !size.in_stock ? 'out' : '',
                    selectedSize === size.size ? 'selected' : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                >
                  {size.size}
                </button>
              ))}
            </div>

            {stock ? (
              <p className={`stock-note ${stock.quantity > 5 ? 'good' : 'low'}`}>
                {stock.quantity > 5
                  ? `${stock.size} is in stock — ${stock.quantity} left.`
                  : `Only ${stock.quantity} left in ${stock.size}. Move fast.`}
              </p>
            ) : product.in_stock ? (
              <p className="stock-note muted">Pick a size to see what's on the shelf.</p>
            ) : (
              <p className="stock-note none">Sold out in every size right now.</p>
            )}
          </div>

          <div className="detail-section detail-buttons">
            <button className="btn" type="button" disabled={!stock}>
              {stock ? `Add ${stock.size} to bag` : 'Select a size'}
            </button>
            <button className="btn ghost" type="button" onClick={() => setPicking(true)}>
              ⇄ Compare with another item
            </button>
          </div>

          <div className="detail-section">
            <h3>Tags</h3>
            <div className="chip-row">
              {product.search_tags.map((tag) => (
                <span key={tag} className="chip tag">
                  {tag}
                </span>
              ))}
            </div>
          </div>

          <p className="muted" style={{ fontSize: '0.78rem', marginTop: '1.5rem' }}>
            Item code: {product.product_id}
          </p>
        </div>
      </div>

      {picking && (
        <ProductPicker
          title={`Compare ${product.name} with…`}
          excludeIds={[product.product_id]}
          onPick={(other) => navigate(`/compare/${product.product_id}/${other}`)}
          onClose={() => setPicking(false)}
        />
      )}
    </div>
  )
}
