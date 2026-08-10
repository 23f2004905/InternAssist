import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import "./Navbar.css";

export default function Navbar() {
  const { currentUser, logout } = useAuth();
  const navigate = useNavigate();

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
      { label: "Documents", path: "/documents" },
      { label: "Users", path: "/users" },
      { label: "Conversations", path: "/conversations" },
    ];
  }

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  return (
    <nav className="navbar">

      <div className="navbar-left">

        <button
          className="navbar-brand"
          onClick={() => navigate("/dashboard")}
        >
          <span className="navbar-logo">
            IA
          </span>

          <span className="navbar-brand-text">
            InternAssist
          </span>
        </button>


        <div className="navbar-links">

          {links.map((link) => (
            <NavLink
              key={link.path}
              to={link.path}
              className={({ isActive }) =>
                `navbar-link ${
                  isActive ? "active" : ""
                }`
              }
            >
              {link.label}
            </NavLink>
          ))}

        </div>

      </div>


      <div className="navbar-right">

        <div className="navbar-user">

          <div className="navbar-avatar">
            {currentUser?.name
              ?.charAt(0)
              .toUpperCase()}
          </div>

          <div className="navbar-user-info">

            <span className="navbar-user-name">
              {currentUser?.name}
            </span>

            <span className="navbar-user-role">
              {currentUser?.role}
            </span>

          </div>

        </div>


        <button
          className="navbar-logout"
          onClick={handleLogout}
        >
          Logout
        </button>

      </div>

    </nav>
  );
}