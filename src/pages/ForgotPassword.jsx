import { useState } from "react";
import { Link } from "react-router-dom";
import "./Login.css";

// PROTOTYPE: no real email is sent. This just simulates the
// "check your inbox" confirmation step. Phase 7 would wire this
// to a real backend email/reset-token flow.
export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);

  function handleSubmit(e) {
    e.preventDefault();
    if (email.trim()) setSent(true);
  }

  return (
    <div className="login-page">
      <div className="login-card card">
        <div className="login-brand">
          <div className="login-mark">IA</div>
          <div>
            <h1 className="login-title">Reset password</h1>
            <p className="login-subtitle">We'll send a reset link</p>
          </div>
        </div>

        {sent ? (
          <p className="login-success">
            If an account exists for {email}, a reset link has been sent.
            <br /><br />
            <span className="field-note">Prototype note: no real email is sent yet — this will be connected to a real email service later.</span>
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="login-form">
            <label htmlFor="fp-email">Email</label>
            <input id="fp-email" type="email" placeholder="you@student.edu"
              value={email} onChange={(e) => setEmail(e.target.value)} />

            <button type="submit" className="btn-primary login-submit">
              Send reset link
            </button>
          </form>
        )}

        <p className="login-footer-text">
          <Link to="/login" className="login-inline-link">Back to login</Link>
        </p>
      </div>
    </div>
  );
}