import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import Logo from './Logo'

const links = [
  { to: '/', label: 'Home', end: true },
  { to: '/products', label: 'Products' },
  { to: '/about', label: 'About Us' },
]

export default function NavBar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/')
  }

  return (
    <nav className="nav">
      <NavLink to="/" className="nav-brand" aria-label="Campus Customs home">
        <Logo />
      </NavLink>
      <div className="nav-links">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.end}
            className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
          >
            {link.label}
          </NavLink>
        ))}

        {user ? (
          <>
            <span className="nav-greeting">Hi, {user.first_name ?? user.name}</span>
            <button type="button" className="nav-link cta" onClick={handleLogout}>
              Log Out
            </button>
          </>
        ) : (
          <>
            <NavLink
              to="/login"
              className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
            >
              Log In
            </NavLink>
            <NavLink to="/create-account" className="nav-link cta">
              Create Account
            </NavLink>
          </>
        )}
      </div>
    </nav>
  )
}
