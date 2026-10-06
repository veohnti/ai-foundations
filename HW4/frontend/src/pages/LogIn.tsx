import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { login } from '../api'
import { useAuth } from '../auth'

export default function LogIn() {
  const { setUser } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const { user } = await login(email, password)
      setUser(user)
      navigate('/products')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page">
      <form className="form-card" onSubmit={handleSubmit}>
        <h1 style={{ fontSize: '1.6rem' }}>Welcome back</h1>
        <p className="muted" style={{ fontSize: '0.92rem', marginTop: 0 }}>
          Log in to pick up where you left off.
        </p>

        <label htmlFor="login-email">Email</label>
        <input
          id="login-email"
          className="input"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />

        <label htmlFor="login-password">Password</label>
        <input
          id="login-password"
          className="input"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        <button className="btn" type="submit" disabled={busy}>
          {busy ? 'Logging in…' : 'Log in'}
        </button>

        {error && <p className="form-error">{error}</p>}

        <p className="muted" style={{ fontSize: '0.9rem', marginTop: '1rem' }}>
          No account? <Link to="/create-account">Make one</Link>.
        </p>
      </form>
    </div>
  )
}
