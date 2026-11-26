import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import Navbar from "../components/Navbar";
import { getApiBaseUrl, parseJsonResponse } from "../utils/api";
import "./AskAssistant.css";

const API_URL = getApiBaseUrl();

const MARKDOWN_COMPONENTS = {
  h1: ({ children }) => <h2>{children}</h2>,
  h2: ({ children }) => <h3>{children}</h3>,
  ul: ({ children }) => (
    <ul style={{ paddingLeft: "24px" }}>{children}</ul>
  ),
  ol: ({ children }) => (
    <ol style={{ paddingLeft: "24px" }}>{children}</ol>
  ),
  li: ({ children }) => (
    <li style={{ marginBottom: "6px" }}>{children}</li>
  ),
  p: ({ children }) => (
    <p style={{ margin: "10px 0" }}>{children}</p>
  ),
};

export default function AskAssistant() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [messages, setMessages] = useState([]);
  const [error, setError] = useState("");
  const [activeCitation, setActiveCitation] = useState(null);
  const [conversationId, setConversationId] = useState(() => {
    const raw = searchParams.get("conversationId");
    const parsed = raw ? Number(raw) : NaN;
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  });

  const initialQuestionHandledRef = useRef(false);

  const saveMessage = useCallback(async (id, role, content) => {
    const response = await fetch(
      `${API_URL}/api/conversations/${id}/messages`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ role, content }),
      }
    );

    return parseJsonResponse(response, "Unable to save message.");
  }, []);

  const submitQuestion = useCallback(
    async (rawQuestion) => {
      const value = rawQuestion.trim();
      if (!value || loading) return;

      setLoading(true);
      setError("");

      const tempUserId = `temp-user-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        { id: tempUserId, role: "user", content: value, citations: [] },
      ]);

      try {
        let activeConversationId = conversationId;

        if (!activeConversationId) {
          const createResponse = await fetch(`${API_URL}/api/conversations`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({
              title: value.slice(0, 60),
            }),
          });

          const createData = await parseJsonResponse(
            createResponse,
            "Could not create conversation."
          );

          activeConversationId = createData.conversation.id;
          setConversationId(activeConversationId);
        }

        await saveMessage(activeConversationId, "user", value);

        let assistantAnswer = "";
        let retrievedCitations = [];
        let askErrorOccurred = false;

        try {
          const response = await fetch(`${API_URL}/api/ask`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({
              question: value,
              conversation_id: activeConversationId,
            }),
          });

          const data = await parseJsonResponse(
            response,
            "Assistant request failed."
          );

          assistantAnswer =
            data.answer ||
            "I don't have any relevant documents to answer this question yet.";
          retrievedCitations = Array.isArray(data.citations)
            ? data.citations
            : [];

          if (
            assistantAnswer.trim() ===
            "Gemini is temporarily unavailable. Please try again."
          ) {
            askErrorOccurred = true;
            setError(assistantAnswer);
          }
        } catch (askErr) {
          askErrorOccurred = true;
          assistantAnswer =
            askErr.message ||
            "I'm sorry, I was unable to retrieve an answer at this time. Please try again.";
          setError(assistantAnswer);
        }

        if (assistantAnswer) {
          if (!askErrorOccurred) {
            try {
              await saveMessage(
                activeConversationId,
                "assistant",
                assistantAnswer
              );
            } catch (saveErr) {
              console.error("Failed to save assistant message:", saveErr);
            }
          }

          setMessages((prev) => [
            ...prev,
            {
              id: `assistant-${Date.now()}`,
              role: "assistant",
              content: assistantAnswer,
              citations: retrievedCitations,
              isError: askErrorOccurred,
            },
          ]);
        }

        if (!askErrorOccurred) {
          setQuestion("");
        }
      } catch (err) {
        setError(err.message || "Unable to connect to the server.");
      } finally {
        setLoading(false);
      }
    },
    [conversationId, loading, saveMessage]
  );

  // Load an existing conversation when opened with ?conversationId=...
  useEffect(() => {
    const paramId = searchParams.get("conversationId");
    const parsedId = paramId ? Number(paramId) : NaN;
    if (!Number.isInteger(parsedId) || parsedId <= 0) return;

    let cancelled = false;
    async function loadExistingConversation() {
      try {
        setLoadingHistory(true);
        setError("");
        const response = await fetch(
          `${API_URL}/api/conversations/${parsedId}`,
          { credentials: "include" }
        );
        const data = await parseJsonResponse(
          response,
          "Unable to load conversation."
        );
        if (!cancelled) {
          setConversationId(parsedId);
          setMessages(
            (data.messages || []).map((msg) => ({
              id: msg.id,
              role: msg.role,
              content: msg.content,
              citations: [],
            }))
          );
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Unable to load conversation.");
        }
      } finally {
        if (!cancelled) {
          setLoadingHistory(false);
        }
      }
    }

    loadExistingConversation();
    return () => {
      cancelled = true;
    };
  }, [searchParams]);

  // Accept question passed via router state from StudentDashboard / FacultyDashboard
  useEffect(() => {
    const incomingQuestion = location.state?.question;
    if (
      typeof incomingQuestion === "string" &&
      incomingQuestion.trim() &&
      !initialQuestionHandledRef.current
    ) {
      initialQuestionHandledRef.current = true;
      const trimmed = incomingQuestion.trim();
      setQuestion(trimmed);
      navigate(location.pathname + location.search, { replace: true, state: {} });
      submitQuestion(trimmed);
    }
  }, [location, navigate, submitQuestion]);

  async function handleSubmit(event) {
    event.preventDefault();
    await submitQuestion(question);
  }

  function applySuggestion(text) {
    setQuestion(text);
  }

  function startNewConversation() {
    setConversationId(null);
    setMessages([]);
    setError("");
    setQuestion("");
    if (searchParams.has("conversationId")) {
      setSearchParams({}, { replace: true });
    }
  }

  return (
    <div className="ask-page">
      <Navbar />

      <main className="ask-main">
        <section className="ask-header">
          <div className="ask-header-row">
            <div>
              <p className="ask-eyebrow">INTERNASSIST</p>
              <h1>Ask Assistant</h1>
              <p className="ask-description">
                Ask questions about internships, academic requirements
                and institutional policies.
              </p>
            </div>
            {(conversationId || messages.length > 0) && (
              <button
                type="button"
                className="new-chat-button"
                onClick={startNewConversation}
                disabled={loading}
              >
                + New conversation
              </button>
            )}
          </div>
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
              onKeyDown={(event) => {
                if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                  event.preventDefault();
                  submitQuestion(question);
                }
              }}
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
            <p className="ask-error-banner" role="alert">
              {error}
            </p>
          )}

          {loadingHistory && (
            <p className="ask-loading-history">
              Loading conversation history...
            </p>
          )}

          {messages.length > 0 && (
            <div className="assistant-thread">
              {messages.map((msg) => (
                <article
                  key={msg.id}
                  className={`thread-message ${
                    msg.role === "user" ? "thread-user" : "thread-assistant"
                  }`}
                >
                  <strong className="thread-role">
                    {msg.role === "user" ? "You" : "Answer"}
                  </strong>

                  {msg.role === "user" ? (
                    <p className="thread-user-text">{msg.content}</p>
                  ) : (
                    <div className="markdown-answer">
                      <ReactMarkdown components={MARKDOWN_COMPONENTS}>
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  )}

                  {Array.isArray(msg.citations) && msg.citations.length > 0 && (
                    <div className="thread-citations">
                      <strong className="thread-citations-title">Sources & References</strong>
                      <div className="thread-citations-list">
                        {msg.citations.map((citation, index) => (
                          <button
                            key={`${citation.document_id}-${index}`}
                            type="button"
                            className="citation-pill-btn"
                            onClick={() => setActiveCitation(citation)}
                            aria-label={`View citation for ${citation.document_name}${citation.page_number ? ` page ${citation.page_number}` : ""}`}
                          >
                            <span className="citation-pill-icon">📄</span>
                            <span className="citation-pill-name">{citation.document_name}</span>
                            {citation.page_number ? (
                              <span className="citation-pill-page">p. {citation.page_number}</span>
                            ) : null}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </article>
              ))}

              {loading && (
                <div className="thread-message thread-assistant thread-thinking">
                  <strong className="thread-role">Answer</strong>
                  <p>Searching documents and generating response...</p>
                </div>
              )}

              {conversationId && (
                <Link
                  to={`/conversations/${conversationId}`}
                  className="view-conversation-link"
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
                applySuggestion(
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
                applySuggestion(
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
                applySuggestion("How is the internship evaluated?")
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
          onClick={() => navigate("/dashboard")}
        >
          ← Back to dashboard
        </button>

        {activeCitation && (
          <div
            className="citation-modal-overlay"
            onClick={() => setActiveCitation(null)}
            role="dialog"
            aria-modal="true"
            aria-labelledby="citation-modal-title"
          >
            <div
              className="citation-modal-card"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="citation-modal-header">
                <div className="citation-modal-title-group">
                  <span className="citation-modal-icon">📄</span>
                  <div>
                    <h3 id="citation-modal-title" className="citation-modal-doc-title">
                      {activeCitation.document_name}
                    </h3>
                    {activeCitation.page_number && (
                      <span className="citation-modal-page-badge">
                        Page {activeCitation.page_number}
                      </span>
                    )}
                  </div>
                </div>
                <button
                  type="button"
                  className="citation-modal-close-btn"
                  onClick={() => setActiveCitation(null)}
                  aria-label="Close excerpt preview"
                >
                  ✕
                </button>
              </div>

              <div className="citation-modal-body">
                <h4 className="citation-modal-section-label">Source Document Excerpt</h4>
                <div className="citation-modal-snippet">
                  {activeCitation.snippet ||
                    "This institutional document was retrieved by InternAssist to ground the answer with verified university guidelines."}
                </div>
              </div>

              <div className="citation-modal-footer">
                <a
                  href={`${API_URL}/api/documents/${activeCitation.document_id}/download`}
                  target="_blank"
                  rel="noreferrer"
                  className="citation-modal-download-link"
                >
                  Open Original Document ↗
                </a>
                <button
                  type="button"
                  className="citation-modal-done-btn"
                  onClick={() => setActiveCitation(null)}
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
