import { useState, useEffect, useRef } from "react";
import { NavLink, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import "./Navbar.css";

export default function Navbar() {
  const { currentUser, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const drawerRef = useRef(null);

  const role = currentUser?.role;

  let links = [];

  if (role === "student") {
    links = [
      { label: "Dashboard", path: "/dashboard" },
      { label: "Ask Assistant", path: "/assistant" },
      { label: "Documents", path: "/documents" },
      { label: "My Conversations", path: "/conversations" },
    ];
  }

  if (role === "faculty") {
    links = [
      { label: "Dashboard", path: "/dashboard" },
      { label: "Ask Assistant", path: "/assistant" },
      { label: "Documents", path: "/documents" },
      { label: "Conversations", path: "/conversations" },
    ];
  }

  if (role === "admin") {
    links = [
      { label: "Dashboard", path: "/dashboard" },
      { label: "Ask Assistant", path: "/assistant" },
      { label: "Documents", path: "/documents" },
      { label: "Users", path: "/users" },
      { label: "Conversations", path: "/conversations" },
    ];
  }

  // Close drawer on route change
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  // Close drawer on Escape key
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === "Escape" && mobileMenuOpen) {
        setMobileMenuOpen(false);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [mobileMenuOpen]);

  // Prevent background scroll when mobile drawer is open
  useEffect(() => {
    if (mobileMenuOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileMenuOpen]);

  async function handleLogout() {
    setMobileMenuOpen(false);
    await logout();
    navigate("/login");
  }

  return (
    <>
      <nav className="navbar" role="navigation" aria-label="Main Navigation">
        <div className="navbar-left">
          <button
            className="navbar-brand"
            onClick={() => {
              setMobileMenuOpen(false);
              navigate("/dashboard");
            }}
            aria-label="InternAssist Home"
          >
            <span className="navbar-logo">IA</span>
            <span className="navbar-brand-text">InternAssist</span>
          </button>

          {/* Desktop Navigation Links */}
          <div className="navbar-links" role="menubar">
            {links.map((link) => (
              <NavLink
                key={link.path}
                to={link.path}
                className={({ isActive }) =>
                  `navbar-link ${isActive ? "active" : ""}`
                }
                role="menuitem"
              >
                {link.label}
              </NavLink>
            ))}
          </div>
        </div>

        <div className="navbar-right">
          {/* Desktop User Info */}
          <div className="navbar-user">
            <div className="navbar-avatar" aria-hidden="true">
              {currentUser?.name?.charAt(0).toUpperCase()}
            </div>
            <div className="navbar-user-info">
              <span className="navbar-user-name">{currentUser?.name}</span>
              <span className="navbar-user-role">{currentUser?.role}</span>
            </div>
          </div>

          <button
            className="navbar-logout desktop-only"
            onClick={handleLogout}
            aria-label="Log out of account"
          >
            Logout
          </button>

          {/* Accessible Hamburger Toggle Button */}
          <button
            type="button"
            className={`navbar-hamburger ${mobileMenuOpen ? "open" : ""}`}
            onClick={() => setMobileMenuOpen((prev) => !prev)}
            aria-label={mobileMenuOpen ? "Close navigation menu" : "Open navigation menu"}
            aria-expanded={mobileMenuOpen}
            aria-controls="mobile-nav-drawer"
          >
            <span className="hamburger-box">
              <span className="hamburger-inner"></span>
            </span>
          </button>
        </div>
      </nav>

      {/* Mobile Drawer Overlay & Menu */}
      {mobileMenuOpen && (
        <div
          className="mobile-drawer-backdrop"
          onClick={() => setMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside
        id="mobile-nav-drawer"
        ref={drawerRef}
        className={`mobile-nav-drawer ${mobileMenuOpen ? "open" : ""}`}
        aria-label="Mobile Navigation"
        aria-hidden={!mobileMenuOpen}
      >
        <div className="drawer-header">
          <div className="drawer-user-card">
            <div className="drawer-avatar" aria-hidden="true">
              {currentUser?.name?.charAt(0).toUpperCase()}
            </div>
            <div className="drawer-user-meta">
              <span className="drawer-user-name">{currentUser?.name}</span>
              <span className="drawer-user-role-badge">{currentUser?.role}</span>
            </div>
          </div>
        </div>

        <nav className="drawer-nav">
          {links.map((link) => (
            <NavLink
              key={link.path}
              to={link.path}
              onClick={() => setMobileMenuOpen(false)}
              className={({ isActive }) =>
                `drawer-link ${isActive ? "active" : ""}`
              }
            >
              <span className="drawer-link-text">{link.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="drawer-footer">
          <button
            className="drawer-logout-btn"
            onClick={handleLogout}
            aria-label="Log out of account"
          >
            Logout
          </button>
        </div>
      </aside>
    </>
  );
}