import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import "./Login.css";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();

    setError("");
    setLoading(true);

    const result = await login(email, password);

    if (result.ok) {
      navigate("/dashboard");
    } else {
      setError(result.error || "Login failed.");
    }

    setLoading(false);
  }

  return (
    <div className="login-page">
      <div className="login-card card">
        <div className="login-brand">
          <div className="login-mark">IA</div>

          <div>
            <h1 className="login-title">
              InternAssist
            </h1>

            <p className="login-subtitle">
              Institutional Q&amp;A Assistant
            </p>
          </div>
        </div>

        <form
          onSubmit={handleSubmit}
          className="login-form"
        >
          <label htmlFor="email">
            Email
          </label>

          <input
            id="email"
            type="email"
            placeholder="you@student.edu"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              setError("");
            }}
            required
          />

          <div className="login-label-row">
            <label htmlFor="password">
              Password
            </label>

            <Link
              to="/forgot-password"
              className="login-inline-link"
            >
              Forgot password?
            </Link>
          </div>

          <input
            id="password"
            type="password"
            
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              setError("");
            }}
            required
          />

          {error && (
            <p className="login-error">
              {error}
            </p>
          )}

          <button
            type="submit"
            className="btn-primary login-submit"
            disabled={loading}
          >
            {loading ? "Logging in..." : "Log in"}
          </button>
        </form>

        <p className="login-footer-text">
          Don&apos;t have an account?{" "}
          <Link
            to="/register"
            className="login-inline-link"
          >
            Register
          </Link>
        </p>
      </div>
    </div>
  );
}