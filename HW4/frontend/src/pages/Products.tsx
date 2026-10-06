import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { fetchProducts, type Product } from '../api'
import { useChatResults } from '../chatResults'
import { usePageContext } from '../pageContext'

// garment_type in the database is not normalized ("hoodie" vs "pullover hoodie",
// "t-shirt" vs "short-sleeve T-shirt"), so the filter groups on a lowercased
// keyword rather than the raw value.
const CATEGORIES = [
  { value: 'all', label: 'Everything' },
  { value: 't-shirt', label: 'T-shirts' },
  { value: 'crewneck', label: 'Crewnecks' },
  { value: 'hood', label: 'Hoodies' },
  { value: 'zip', label: 'Zips & jackets' },
]

function matchesCategory(product: Product, category: string) {
  if (category === 'all') return true
  const type = product.garment_type.toLowerCase()
  if (category === 'zip') return type.includes('zip') || type.includes('jacket')
  if (category === 'hood') return type.includes('hood')
  return type.includes(category)
}

export default function Products() {
  const { pageResults, clearResults } = useChatResults()
  const [searchParams] = useSearchParams()
  const { setView } = usePageContext()
  const [products, setProducts] = useState<Product[]>([])
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState(() => {
    const c = searchParams.get('category')
    return CATEGORIES.some((x) => x.value === c) ? c! : 'all'
  })
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchProducts()
      .then(setProducts)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  // Arriving from a "Shop by category" tile (/products?category=hood) shows
  // that category. A tile click is a fresh browse, so any chat results are
  // cleared rather than left hiding part of the category.
  const categoryParam = searchParams.get('category')
  useEffect(() => {
    if (categoryParam && CATEGORIES.some((x) => x.value === categoryParam)) {
      setCategory(categoryParam)
      clearResults()
    }
    // clearResults is recreated when results change; only the param matters here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [categoryParam])

  // A new set of chat results resets the page's own search box and category,
  // so an old local filter can't hide part of what the assistant just found.
  useEffect(() => {
    if (pageResults) {
      setQuery('')
      setCategory('all')
    }
  }, [pageResults])

  // When the chat assistant has sent results, the page starts from exactly those
  // products (in the order the backend returned them); otherwise from everything.
  // Ids are matched against the full catalogue fetched above, so tiles carry the
  // same data as the normal page and link to the same detail pages.
  const base = useMemo(() => {
    if (!pageResults) return products
    const byId = new Map(products.map((p) => [p.product_id, p]))
    return pageResults.products
      .map((card) => byId.get(card.product_id))
      .filter((p): p is Product => p !== undefined)
  }, [products, pageResults])

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    return base.filter((product) => {
      if (!matchesCategory(product, category)) return false
      if (!q) return true
      const haystack = [
        product.name,
        product.garment_type,
        product.description,
        ...product.colors,
        ...product.search_tags,
      ]
        .join(' ')
        .toLowerCase()
      return haystack.includes(q)
    })
  }, [base, query, category])

  // Tell the chat assistant what the grid is showing, so "these" or "the first
  // one" refers to these tiles. Ids are listed only for a manageable grid; the
  // full 102-item catalogue is described by its count and filters instead.
  useEffect(() => {
    if (loading) return
    const label = pageResults
      ? pageResults.label
      : category === 'all' && !query.trim()
        ? 'All products'
        : (CATEGORIES.find((c) => c.value === category)?.label ?? 'Products')
    setView({
      list_label: label,
      list_total: visible.length,
      listed_product_ids: visible.length <= 60 ? visible.map((p) => p.product_id) : [],
      search_text: query.trim() || null,
      category,
    })
    return () => setView(null)
  }, [loading, visible, pageResults, query, category, setView])

  return (
    <div className="page">
      <span className="eyebrow">Products</span>
      <h1>{pageResults ? pageResults.label : 'The whole rack'}</h1>
      <p className="muted">Click any piece to see sizes, colors, and what's actually in stock.</p>

      {pageResults && (
        <div className="chat-results-banner" role="status">
          <span>
            Showing the <strong>{pageResults.total}</strong>{' '}
            {pageResults.total === 1 ? 'product' : 'products'} the shop assistant found for
            you.
          </span>
          <button type="button" className="btn ghost" onClick={clearResults}>
            Show all products
          </button>
        </div>
      )}

      <div className="toolbar">
        <input
          className="input"
          placeholder="Search — try 'navy', 'Saybrook', 'tennis'…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select className="select" value={category} onChange={(e) => setCategory(e.target.value)}>
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
        <span className="muted">{visible.length} items</span>
      </div>

      {loading && <p className="state">Loading the catalogue…</p>}
      {error && (
        <p className="state error">
          Couldn't reach the shop API ({error}). Is the FastAPI backend running on port 8000?
        </p>
      )}

      <div className="product-grid">
        {visible.map((product) => (
          <Link
            key={product.product_id}
            to={`/products/${product.product_id}`}
            className="product-card"
          >
            <div className="thumb">
              <img src={product.image_url} alt={product.name} loading="lazy" />
            </div>
            <div className="meta">
              <h3>{product.name}</h3>
              <div className="type">{product.garment_type}</div>
              <div className="price">${product.price.toFixed(2)}</div>
            </div>
          </Link>
        ))}
      </div>

      {!loading && !error && visible.length === 0 && (
        <p className="state">Nothing matched that. Try a looser search.</p>
      )}
    </div>
  )
}
