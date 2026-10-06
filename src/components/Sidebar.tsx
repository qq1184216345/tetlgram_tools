import { NavItem } from "../types";
import logo from "../assets/logo.png";

interface SidebarProps {
  items: NavItem[];
  active: string;
  onSelect: (id: string) => void;
}

export function Sidebar({ items, active, onSelect }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <img src={logo} alt="纸翼" className="brand-icon" />
        <div>
          <h1>纸翼</h1>
          <p>Telegram 营销自动化</p>
        </div>
      </div>
      <nav className="sidebar-nav">
        {items.map((item) => (
          <button
            key={item.id}
            className={`nav-item ${active === item.id ? "active" : ""}`}
            onClick={() => onSelect(item.id)}
          >
            <span className="nav-icon">{item.icon}</span>
            <span className="nav-label">{item.label}</span>
          </button>
        ))}
      </nav>
    </aside>
  );
}
