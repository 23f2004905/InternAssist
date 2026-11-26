import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import { useAuth } from "../context/AuthContext";
import { getApiBaseUrl, parseJsonResponse, getSecurityHeaders } from "../utils/api";
import "./Conversations.css";

const API_URL = getApiBaseUrl();

export default function Conversations() {
  const navigate = useNavigate();
  const { currentUser } = useAuth();
  const isAdmin = currentUser?.role === "admin";

  const [activeTab, setActiveTab] = useState(isAdmin ? "oversight" : "my");
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // --------------------------------
  // Load conversations
  // --------------------------------
  const loadConversations = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const endpoint =
        isAdmin && activeTab === "oversight"
          ? `${API_URL}/api/admin/conversations`
          : `${API_URL}/api/conversations`;

      const response = await fetch(endpoint, {
        credentials: "include",
      });

      const data = await parseJsonResponse(
        response,
        "Unable to load conversations."
      );

      setConversations(data.conversations || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [isAdmin, activeTab]);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  // --------------------------------
  // Create conversation
  // --------------------------------
  async function createConversation() {
    try {
      const response = await fetch(`${API_URL}/api/conversations`, {
        method: "POST",
        headers: getSecurityHeaders({ "Content-Type": "application/json" }),
        credentials: "include",
        body: JSON.stringify({
          title: "New Conversation",
        }),
      });

      const data = await parseJsonResponse(
        response,
        "Unable to create conversation."
      );

      navigate(`/conversations/${data.conversation.id}`);
    } catch (err) {
      setError(err.message);
    }
  }

  // --------------------------------
  // Delete conversation
  // --------------------------------
  async function deleteConversation(id) {
    const confirmed = window.confirm(
      "Are you sure you want to delete this conversation?"
    );

    if (!confirmed) return;

    try {
      const response = await fetch(`${API_URL}/api/conversations/${id}`, {
        method: "DELETE",
        headers: getSecurityHeaders(),
        credentials: "include",
      });

      await parseJsonResponse(response, "Unable to delete conversation.");
      await loadConversations();
    } catch (err) {
      setError(err.message);
    }
  }

  // --------------------------------
  // Format date
  // --------------------------------
  function formatDate(dateString) {
    if (!dateString) return "—";
    return new Date(dateString).toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  return (
    <div className="conversations-page">
      <Navbar />

      <main className="conversations-main">
        <section className="conversations-header">
          <div>
            <p className="conversations-eyebrow">CONVERSATIONS</p>
            <h1>
              {isAdmin && activeTab === "oversight"
                ? "Institutional Conversations"
                : "My Conversations"}
            </h1>
            <p className="conversations-subtitle">
              {isAdmin && activeTab === "oversight"
                ? "Oversight of system interactions and student inquiry volume (privacy-preserved)."
                : "Review your previous questions and assistant interactions."}
            </p>
          </div>

          <div className="conversations-header-actions">
            {isAdmin && (
              <div className="conversations-tab-toggle" role="tablist">
                <button
                  type="button"
                  className={`tab-btn ${activeTab === "oversight" ? "active" : ""}`}
                  onClick={() => setActiveTab("oversight")}
                  role="tab"
                  aria-selected={activeTab === "oversight"}
                >
                  System Oversight
                </button>
                <button
                  type="button"
                  className={`tab-btn ${activeTab === "my" ? "active" : ""}`}
                  onClick={() => setActiveTab("my")}
                  role="tab"
                  aria-selected={activeTab === "my"}
                >
                  My Conversations
                </button>
              </div>
            )}

            <button
              className="new-conversation-button"
              onClick={createConversation}
            >
              + New conversation
            </button>
          </div>
        </section>

        {error && <div className="conversation-error">{error}</div>}

        {loading ? (
          <div className="conversation-empty">Loading conversations...</div>
        ) : conversations.length === 0 ? (
          <div className="conversation-empty">
            <div className="conversation-empty-icon">?</div>
            <h2>No conversations yet</h2>
            <p>
              {isAdmin && activeTab === "oversight"
                ? "No student conversations have been logged in the system yet."
                : "Start a conversation with InternAssist to see your questions and answers here."}
            </p>
            <button className="empty-start-button" onClick={createConversation}>
              Start a conversation
            </button>
          </div>
        ) : isAdmin && activeTab === "oversight" ? (
          /* Admin Oversight Table */
          <div className="oversight-table-container">
            <div className="oversight-privacy-banner">
              🔒 <strong>Privacy Assurance:</strong> Student conversation inquiry texts are private and omitted from oversight views. Only session metadata and message activity volumes are tracked.
            </div>

            <table className="oversight-table">
              <thead>
                <tr>
                  <th>TOPIC / TITLE</th>
                  <th>STUDENT / USER</th>
                  <th>ROLE</th>
                  <th>MESSAGES</th>
                  <th>LAST ACTIVITY</th>
                  <th>ACTION</th>
                </tr>
              </thead>
              <tbody>
                {conversations.map((conv) => (
                  <tr key={conv.id}>
                    <td>
                      <strong className="oversight-conv-title">{conv.title}</strong>
                      <span className="oversight-conv-id">ID: #{conv.id}</span>
                    </td>
                    <td>
                      <div className="oversight-user-meta">
                        <span className="oversight-user-name">{conv.user_name || "Unknown"}</span>
                        <span className="oversight-user-email">{conv.user_email || "—"}</span>
                      </div>
                    </td>
                    <td>
                      <span className={`user-role ${(conv.user_role || "student").toLowerCase()}`}>
                        {conv.user_role || "student"}
                      </span>
                    </td>
                    <td>
                      <span className="oversight-msg-badge">
                        {conv.message_count ?? 0} {conv.message_count === 1 ? "msg" : "msgs"}
                      </span>
                    </td>
                    <td>
                      <span className="oversight-date">{formatDate(conv.updated_at)}</span>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="oversight-view-btn"
                        onClick={() => navigate(`/conversations/${conv.id}`)}
                      >
                        Inspect Thread →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          /* Standard Conversation Cards List */
          <section className="conversation-list">
            {conversations.map((conversation) => (
              <div className="conversation-card" key={conversation.id}>
                <div
                  className="conversation-card-main"
                  onClick={() => navigate(`/conversations/${conversation.id}`)}
                >
                  <div className="conversation-icon">?</div>
                  <div>
                    <h2>{conversation.title}</h2>
                    <p>Updated {formatDate(conversation.updated_at)}</p>
                  </div>
                </div>

                <button
                  className="conversation-delete"
                  onClick={() => deleteConversation(conversation.id)}
                >
                  Delete
                </button>
              </div>
            ))}
          </section>
        )}
      </main>
    </div>
  );
}
