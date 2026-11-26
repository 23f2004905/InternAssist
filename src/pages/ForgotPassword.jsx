import { Link } from "react-router-dom";
import "./Login.css";

export default function ForgotPassword() {
  return (
    <div className="login-page">
      <div className="login-card card">
        <div className="login-brand">
          <div className="login-mark">IA</div>
          <div>
            <h1 className="login-title">Account Recovery</h1>
            <p className="login-subtitle">Campus credential assistance</p>
          </div>
        </div>

        <div style={{ marginTop: "16px", lineHeight: "1.6", color: "var(--ink)" }}>
          <p style={{ fontSize: "14px", marginBottom: "16px" }}>
            Password recovery for InternAssist campus accounts is managed through your institution&rsquo;s Central IT Support and Directory Services.
          </p>

          <div
            style={{
              background: "var(--surface-sunken)",
              border: "1px solid var(--border)",
              borderRadius: "8px",
              padding: "16px",
              marginBottom: "20px",
              fontSize: "13px",
            }}
          >
            <strong style={{ color: "var(--primary)", display: "block", marginBottom: "8px" }}>
              How to restore your access:
            </strong>
            <ul style={{ paddingLeft: "20px", margin: 0, display: "flex", flexDirection: "column", gap: "6px" }}>
              <li>
                <strong>Students:</strong> Contact your university IT Help Desk or visit the campus single-sign-on self-service portal.
              </li>
              <li>
                <strong>Faculty & Staff:</strong> Reach out to your departmental administrator or submit a ticket to the registrar&rsquo;s IT helpdesk.
              </li>
              <li>
                <strong>System Administrators:</strong> Accounts can be reset or reactivated directly from the Admin Users management panel.
              </li>
            </ul>
          </div>

          <div
            style={{
              padding: "12px 14px",
              background: "var(--primary-soft)",
              borderRadius: "6px",
              fontSize: "13px",
              color: "var(--primary)",
              marginBottom: "20px",
            }}
          >
            <strong>Help Desk Email:</strong>{" "}
            <a href="mailto:support@internassist.campus.edu" style={{ color: "var(--primary)", textDecoration: "underline" }}>
              support@internassist.campus.edu
            </a>
          </div>
        </div>

        <p className="login-footer-text">
          <Link to="/login" className="login-inline-link">Back to login</Link>
        </p>
      </div>
    </div>
  );
}