import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiRequest } from "../lib/api";
import Navbar from "../components/Navbar";
import { useAuth } from "../context/AuthContext";
import "./Conversations.css";

function formatDate(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function Conversations() {
  const navigate = useNavigate();
  const { currentUser } = useAuth();
  const isAdmin = currentUser?.role === "admin";
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState(null);
  const [error, setError] = useState("");

  const loadConversations = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await apiRequest(isAdmin ? "/admin/conversations" : "/conversations");
      setConversations(data.conversations || []);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }, [isAdmin]);

  useEffect(() => { loadConversations(); }, [loadConversations]);

  async function deleteConversation(event, id) {
    event.stopPropagation();
    if (!window.confirm("Delete this conversation?")) return;
    setDeletingId(id);
    setError("");
    try {
      await apiRequest(`/conversations/${id}`, { method: "DELETE" });
      setConversations((items) => items.filter((item) => item.id !== id));
    } catch (deleteError) {
      setError(deleteError.message);
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="conversations-page">
      <Navbar />
      <main className="conversations-main">
        <section className="conversations-header">
          <div><p className="conversations-eyebrow">CONVERSATIONS</p><h1>{isAdmin ? "System conversations" : "My conversations"}</h1><p className="conversations-subtitle">{isAdmin ? "Review conversation activity across all users." : "Continue a previous question or start a fresh chat."}</p></div>
          {!isAdmin && <button className="new-conversation-button" onClick={() => navigate("/assistant")}>+ New conversation</button>}
        </section>
        {error && <div className="conversation-error" role="alert">{error}</div>}
        {loading ? <div className="conversation-empty" role="status">Loading conversations…</div> : conversations.length === 0 ? (
          <div className="conversation-empty"><div className="conversation-empty-icon">?</div><h2>No conversations yet</h2><p>Start a conversation with InternAssist to see your questions and answers here.</p><button className="empty-start-button" onClick={() => navigate("/assistant")}>Start a conversation</button></div>
        ) : (
          <section className="conversation-list" aria-label="Conversation history">
            {conversations.map((item) => (
              <article className="conversation-card" key={item.id} onClick={() => !isAdmin && navigate(`/conversations/${item.id}`)}>
                <div className="conversation-card-main"><div className="conversation-icon">IA</div><div><h2>{item.title}</h2><p>{isAdmin ? `${item.user_name} · ${item.user_email} · ${item.message_count} messages · ` : ""}Updated {formatDate(item.updated_at)}</p></div></div>
                {!isAdmin && <button className="conversation-delete" onClick={(event) => deleteConversation(event, item.id)} disabled={deletingId === item.id}>{deletingId === item.id ? "Deleting…" : "Delete"}</button>}
              </article>
            ))}
          </section>
        )}
      </main>
    </div>
  );
}
