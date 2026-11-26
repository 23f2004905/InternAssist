import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import Navbar from "../components/Navbar";
import { getApiBaseUrl, parseJsonResponse } from "../utils/api";
import "./ConversationDetail.css";

const API_URL = getApiBaseUrl();

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

        const data = await parseJsonResponse(
          response,
          "Unable to load conversation."
        );

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

      <main className="conversation-detail-main">
        <div className="conversation-detail-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={() => navigate("/conversations")}
          >
            ← Back to conversations
          </button>

          {conversation && (
            <Link
              to={`/assistant?conversationId=${conversation.id}`}
              className="btn-primary"
            >
              Continue conversation →
            </Link>
          )}
        </div>

        {loading && (
          <p className="conversation-detail-loading">
            Loading conversation...
          </p>
        )}

        {error && (
          <div className="conversation-detail-error">
            {error}
          </div>
        )}

        {!loading && !error && conversation && (
          <>
            <header className="conversation-detail-header">
              <h1>{conversation.title}</h1>
              <p>Conversation history</p>
            </header>

            <section className="conversation-detail-messages">
              {messages.length === 0 ? (
                <p className="conversation-detail-empty">No messages in this conversation yet.</p>
              ) : (
                messages.map((message) => (
                  <article
                    key={message.id}
                    className={`conversation-message-card ${
                      message.role === "user"
                        ? "user-message"
                        : "assistant-message"
                    }`}
                  >
                    <strong className="message-author">
                      {message.role === "user"
                        ? "You"
                        : "InternAssist Assistant"}
                    </strong>

                    {message.role === "user" ? (
                      <p className="message-body">
                        {message.content}
                      </p>
                    ) : (
                      <div className="message-body-markdown">
                        <ReactMarkdown>{message.content}</ReactMarkdown>
                      </div>
                    )}

                    {message.created_at && (
                      <small className="message-timestamp">
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
