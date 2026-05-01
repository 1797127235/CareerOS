import { NavLink, Outlet } from 'react-router-dom'

const FEEDBACK_URL = 'https://github.com/anthropics/claude-code/issues'

function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="h-[52px] flex items-center justify-between px-md md:px-lg border-b border-border-soft">
        <NavLink
          to="/"
          end
          className="flex items-baseline gap-xs text-text hover:opacity-100"
        >
          <span className="text-lg font-han">码路</span>
          <span className="text-xs text-text-subtle font-latin tracking-wide">
            codepilot
          </span>
        </NavLink>

        <nav className="flex items-center gap-lg text-sm">
          <NavItem to="/" end>对话</NavItem>
          <NavItem to="/profile">画像</NavItem>
          <NavItem to="/jd">JD 诊断</NavItem>
          <a
            href={FEEDBACK_URL}
            target="_blank"
            rel="noreferrer noopener"
            className="text-text-muted hover:text-text"
          >
            反馈
          </a>
        </nav>
      </header>

      <main className="flex-1 ink-fade-in">
        <Outlet />
      </main>
    </div>
  )
}

function NavItem({
  to,
  end,
  children,
}: {
  to: string
  end?: boolean
  children: React.ReactNode
}) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        isActive ? 'text-ink' : 'text-text-muted hover:text-text'
      }
    >
      {children}
    </NavLink>
  )
}

export default App
