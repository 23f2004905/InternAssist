
import { useState } from "react";
import { Link } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import Navbar from "../components/Navbar";
import "./AskAssistant.css";

const API_URL = "http://localhost:5001";

export default function AskAssistant() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState("");
  const [conversationId, setConversationId] = useState(null);
  const [citations, setCitations] = useState([]);

  async function saveMessage(id, role, content) {
    const response = await fetch(
      `${API_URL}/api/conversations/${id}/messages`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ role, content }),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "Unable to save message.");
    }

    return data;
  }

  async function handleSubmit(event) {
    event.preventDefault();

    const value = question.trim();

    if (!value || loading) return;

    setLoading(true);
    setError("");
    setAnswer("");
    setCitations([]);

    try {
      let activeConversationId = conversationId;

      // Create a conversation for the first question.
      if (!activeConversationId) {
        const createResponse = await fetch(
          `${API_URL}/api/conversations`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({
              title: value.slice(0, 60),
            }),
          }
        );

        const createData = await createResponse.json();

        if (!createResponse.ok) {
          throw new Error(
            createData.error || "Could not create conversation."
          );
        }

        activeConversationId = createData.conversation.id;
        setConversationId(activeConversationId);
      }

      // Save the student's question.
      await saveMessage(activeConversationId, "user", value);

      // Get the RAG/Gemini answer.
      const response = await fetch(`${API_URL}/api/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ question: value }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Assistant request failed.");
      }

      // Save the assistant's answer.
      await saveMessage(
        activeConversationId,
        "assistant",
        data.answer
      );

      setAnswer(data.answer || "");
      setCitations(data.citations || []);
      setQuestion("");
    } catch (err) {
      setError(err.message || "Unable to connect to the server.");
    } finally {
      setLoading(false);
    }
  }

  function useSuggestion(text) {
    setQuestion(text);
  }

  return (
    <div className="ask-page">
      <Navbar />

      <main className="ask-main">
        <section className="ask-header">
          <p className="ask-eyebrow">INTERNASSIST</p>
          <h1>Ask Assistant</h1>
          <p className="ask-description">
            Ask questions about internships, academic requirements
            and institutional policies.
          </p>
        </section>

        <section className="assistant-panel">
          <div className="assistant-panel-header">
            <div className="assistant-icon">?</div>
            <div>
              <h2>What would you like to know?</h2>
              <p>Ask your question in natural language.</p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="ask-form">
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="For example: What documents are required to apply for an internship?"
              rows="5"
              disabled={loading}
            />

            <div className="ask-form-footer">
              <span>
                Your answer will be based on institutional documents.
              </span>

              <button
                type="submit"
                disabled={loading || !question.trim()}
              >
                {loading ? "Processing..." : "Ask Assistant →"}
              </button>
            </div>
          </form>

          {error && (
            <p style={{ color: "#d33", marginTop: "12px" }}>
              {error}
            </p>
          )}

          {answer && (
            <div
              style={{
                marginTop: "20px",
                padding: "22px",
                background: "#f4f5f7",
                borderRadius: "10px",
                color: "#243247",
                lineHeight: 1.7,
              }}
            >
              <strong style={{ fontSize: "18px" }}>Answer</strong>

              <div className="markdown-answer">
                <ReactMarkdown
                  components={{
                    h1: ({ children }) => <h2>{children}</h2>,
                    h2: ({ children }) => <h3>{children}</h3>,
                    ul: ({ children }) => (
                      <ul style={{ paddingLeft: "24px" }}>
                        {children}
                      </ul>
                    ),
                    ol: ({ children }) => (
                      <ol style={{ paddingLeft: "24px" }}>
                        {children}
                      </ol>
                    ),
                    li: ({ children }) => (
                      <li style={{ marginBottom: "6px" }}>
                        {children}
                      </li>
                    ),
                    p: ({ children }) => (
                      <p style={{ margin: "10px 0" }}>
                        {children}
                      </p>
                    ),
                  }}
                >
                  {answer}
                </ReactMarkdown>
              </div>

              {citations.length > 0 && (
                <div
                  style={{
                    marginTop: "20px",
                    paddingTop: "14px",
                    borderTop: "1px solid #d7dce3",
                  }}
                >
                  <strong>Sources</strong>

                  <ul style={{ paddingLeft: "20px" }}>
                    {citations.map((citation, index) => (
                      <li key={`${citation.document_id}-${index}`}>
                        {citation.document_name}
                        {citation.page_number
                          ? ` — Page ${citation.page_number}`
                          : ""}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {conversationId && (
                <Link
                  to={`/conversations/${conversationId}`}
                  style={{
                    display: "inline-block",
                    marginTop: "14px",
                    padding: "10px 16px",
                    background: "#173653",
                    color: "#ffffff",
                    borderRadius: "6px",
                    textDecoration: "none",
                  }}
                >
                  View conversation history →
                </Link>
              )}
            </div>
          )}
        </section>

        <section className="suggestions-section">
          <div className="section-heading">
            <h2>Suggested questions</h2>
            <p>You can start with one of these common queries.</p>
          </div>

          <div className="suggestions-grid">
            <button
              type="button"
              onClick={() =>
                useSuggestion(
                  "What documents are required for an internship?"
                )
              }
            >
              <span>01</span>
              <strong>Internship documents</strong>
              <small>
                Find documents required for internship applications.
              </small>
            </button>

            <button
              type="button"
              onClick={() =>
                useSuggestion(
                  "What are the internship approval requirements?"
                )
              }
            >
              <span>02</span>
              <strong>Approval requirements</strong>
              <small>
                Understand the process and requirements for approval.
              </small>
            </button>

            <button
              type="button"
              onClick={() =>
                useSuggestion("How is the internship evaluated?")
              }
            >
              <span>03</span>
              <strong>Internship evaluation</strong>
              <small>
                Find information about evaluation and assessment.
              </small>
            </button>
          </div>
        </section>

        <section className="assistant-note">
          <div className="note-icon">✓</div>
          <div>
            <strong>Source-based answers</strong>
            <p>
              InternAssist is designed to answer questions using the
              institution's uploaded documents and show the source
              used for the response.
            </p>
          </div>
        </section>

        <button
          className="back-to-dashboard"
          type="button"
          onClick={() => window.location.assign("/dashboard")}
        >
          ← Back to dashboard
        </button>
      </main>
    </div>
  );
}
