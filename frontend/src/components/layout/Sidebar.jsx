import { NavLink } from 'react-router-dom';

const navItems = [{ to: '/', label: 'Projects' }];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="logo-mark">AI</div>
        <div>
          <div className="logo-title">Ai_Studio</div>
        </div>
      </div>

      <nav className="sidebar-nav" aria-label="Sidebar navigation">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `nav-item ${isActive ? 'nav-item-active' : ''}`
            }
            end={item.to === '/'}
          >
            {item.label}
          </NavLink>
        ))}

        <div className="nav-section-label">Future domains</div>
        <div className="nav-item disabled">Parts</div>
        <div className="nav-item disabled">Sources</div>
        <div className="nav-item disabled">Findings</div>
        <div className="nav-item disabled">Assets</div>
        <div className="nav-item disabled">Scripts</div>
        <div className="nav-item disabled">History</div>
      </nav>
    </aside>
  );
}
