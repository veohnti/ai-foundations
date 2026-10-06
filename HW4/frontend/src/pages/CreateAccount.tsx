import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { signup } from '../api'
import { useAuth } from '../auth'

export default function CreateAccount() {
  const { setUser } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({
    firstName: '',
    lastName: '',
    email: '',
    password: '',
    confirmPassword: '',
  })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const update = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [field]: e.target.value })

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)

    // Catch the mismatch in the browser too, so the user hears about it before a
    // round trip. The backend checks this again as the real gate.
    if (form.password !== form.confirmPassword) {
      setError('Passwords do not match.')
      return
    }
    if (form.password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }

    setBusy(true)
    try {
      const { user } = await signup({
        email: form.email,
        first_name: form.firstName,
        last_name: form.lastName,
        password: form.password,
        confirm_password: form.confirmPassword,
      })
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
        <h1 style={{ fontSize: '1.6rem' }}>Create an account</h1>
        <p className="muted" style={{ fontSize: '0.92rem', marginTop: 0 }}>
          Takes a second. Mostly so we know what to call you.
        </p>

        <label htmlFor="first-name">First name</label>
        <input id="first-name" className="input" required value={form.firstName} onChange={update('firstName')} />

        <label htmlFor="last-name">Last name</label>
        <input id="last-name" className="input" required value={form.lastName} onChange={update('lastName')} />

        <label htmlFor="signup-email">Email</label>
        <input
          id="signup-email"
          className="input"
          type="email"
          autoComplete="email"
          required
          value={form.email}
          onChange={update('email')}
        />

        <label htmlFor="signup-password">Password</label>
        <input
          id="signup-password"
          className="input"
          type="password"
          autoComplete="new-password"
          required
          value={form.password}
          onChange={update('password')}
        />

        <label htmlFor="confirm-password">Confirm password</label>
        <input
          id="confirm-password"
          className="input"
          type="password"
          autoComplete="new-password"
          required
          value={form.confirmPassword}
          onChange={update('confirmPassword')}
        />

        <button className="btn" type="submit" disabled={busy}>
          {busy ? 'Creating…' : 'Create account'}
        </button>

        {error && <p className="form-error">{error}</p>}

        <p className="muted" style={{ fontSize: '0.9rem', marginTop: '1rem' }}>
          Already have one? <Link to="/login">Log in</Link>.
        </p>
      </form>
    </div>
  )
}
