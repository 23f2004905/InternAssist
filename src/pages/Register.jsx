import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import "./Login.css";

export default function Register() {
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    confirm: "",
    role: "student",
  });

  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const { register } = useAuth();
  const navigate = useNavigate();

  function update(field, value) {
    setForm((f) => ({
      ...f,
      [field]: value,
    }));

    setError("");
  }

  async function handleSubmit(e) {
    e.preventDefault();

    setError("");

    // Basic validation
    if (
      !form.name.trim() ||
      !form.email.trim() ||
      !form.password ||
      !form.confirm
    ) {
      setError("Please fill in all fields.");
      return;
    }

    if (form.password !== form.confirm) {
      setError("Passwords do not match.");
      return;
    }

    if (form.password.length < 6) {
      setError(
        "Password must be at least 6 characters long."
      );
      return;
    }

    setLoading(true);

    // Send only the fields required by the backend.
    const result = await register({
      name: form.name.trim(),
      email: form.email.trim(),
      password: form.password,
      role: form.role,
    });

    if (!result.ok) {
      setError(
        result.error || "Registration failed."
      );
      setLoading(false);
      return;
    }

    setSuccess(true);
    setLoading(false);

    setTimeout(() => {
      navigate("/login");
    }, 1200);
  }

  return (
    <div className="login-page">
      <div className="login-card card">

        <div className="login-brand">
          <div className="login-mark">
            IA
          </div>

          <div>
            <h1 className="login-title">
              Create account
            </h1>

            <p className="login-subtitle">
              Register for InternAssist
            </p>
          </div>
        </div>


        {success ? (
          <p className="login-success">
            Account created successfully —
            redirecting to login...
          </p>
        ) : (

          <form
            onSubmit={handleSubmit}
            className="login-form"
          >

            <label htmlFor="name">
              Full name
            </label>

            <input
              id="name"
              type="text"
              
              value={form.name}
              onChange={(e) =>
                update("name", e.target.value)
              }
              required
            />


            <label htmlFor="reg-email">
              Email
            </label>

            <input
              id="reg-email"
              type="email"
              
              value={form.email}
              onChange={(e) =>
                update("email", e.target.value)
              }
              required
            />


            <label htmlFor="role">
              I am a
            </label>

            <select
              id="role"
              value={form.role}
              onChange={(e) =>
                update("role", e.target.value)
              }
            >
              <option value="student">
                Student
              </option>

              <option value="faculty">
                Faculty
              </option>
            </select>


            <label htmlFor="reg-password">
              Password
            </label>

            <input
              id="reg-password"
              type="password"
              value={form.password}
              onChange={(e) =>
                update("password", e.target.value)
              }
              required
            />


            <label htmlFor="confirm">
              Confirm password
            </label>

            <input
              id="confirm"
              type="password"
              placeholder="Enter password again"
              value={form.confirm}
              onChange={(e) =>
                update("confirm", e.target.value)
              }
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
              {loading
                ? "Creating account..."
                : "Register"}
            </button>

          </form>
        )}


        <p className="login-footer-text">
          Already have an account?{" "}

          <Link
            to="/login"
            className="login-inline-link"
          >
            Log in
          </Link>
        </p>

      </div>
    </div>
  );
}