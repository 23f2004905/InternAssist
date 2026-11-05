
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Navbar from "../components/Navbar";

const API_URL = "http://localhost:5001";

export default function ConversationDetail() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [conversation, setConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadConversation() {
      try {
        setLoading(true);
        setError("");

        const response = await fetch(
          `${API_URL}/api/conversations/${id}`,
          {
            method: "GET",
            credentials: "include",
          }
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            data.error || "Unable to load conversation."
          );
        }

        if (!cancelled) {
          setConversation(data.conversation);
          setMessages(data.messages || []);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err.message || "Unable to connect to the server."
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadConversation();

    return () => {
      cancelled = true;
    };
  }, [id]);

  return (
    <div className="conversation-detail-page">
      <Navbar />

      <main
        style={{
          maxWidth: "900px",
          margin: "40px auto",
          padding: "20px",
        }}
      >
        <button
          type="button"
          onClick={() => navigate("/conversations")}
        >
          ← Back to conversations
        </button>

        {loading && (
          <p style={{ marginTop: "24px" }}>
            Loading conversation...
          </p>
        )}

        {error && (
          <div
            style={{
              marginTop: "24px",
              padding: "16px",
              color: "#d33",
              background: "#fff0f0",
              borderRadius: "8px",
            }}
          >
            {error}
          </div>
        )}

        {!loading && !error && conversation && (
          <>
            <header style={{ marginTop: "28px" }}>
              <h1>{conversation.title}</h1>
              <p style={{ color: "#777", marginTop: "8px" }}>
                Conversation history
              </p>
            </header>

            <section style={{ marginTop: "30px" }}>
              {messages.length === 0 ? (
                <p>No messages in this conversation yet.</p>
              ) : (
                messages.map((message) => (
                  <article
                    key={message.id}
                    style={{
                      padding: "18px",
                      marginBottom: "16px",
                      borderRadius: "10px",
                      background:
                        message.role === "user"
                          ? "#eef3ff"
                          : "#f4f5f7",
                    }}
                  >
                    <strong>
                      {message.role === "user"
                        ? "You"
                        : "InternAssist Assistant"}
                    </strong>

                    <p
                      style={{
                        marginTop: "10px",
                        whiteSpace: "pre-wrap",
                        lineHeight: "1.6",
                      }}
                    >
                      {message.content}
                    </p>

                    {message.created_at && (
                      <small style={{ color: "#888" }}>
                        {new Date(
                          message.created_at
                        ).toLocaleString()}
                      </small>
                    )}
                  </article>
                ))
              )}
            </section>
          </>
        )}
      </main>
    </div>
  );
}
