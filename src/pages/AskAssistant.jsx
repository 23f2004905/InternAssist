import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiRequest } from "../lib/api";
import Navbar from "../components/Navbar";
import "./AskAssistant.css";

const SUGGESTIONS = [
  "What documents are required for an internship?",
  "What are the internship approval requirements?",
  "How is the internship evaluated?",
];

export default function AskAssistant() {
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const endRef = useRef(null);
  const [conversation, setConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [loadingHistory, setLoadingHistory] = useState(Boolean(conversationId));
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!conversationId) {
      setConversation(null);
      setMessages([]);
      setLoadingHistory(false);
      return;
    }

    let active = true;
    setLoadingHistory(true);
    apiRequest(`/conversations/${conversationId}`)
      .then((data) => {
        if (!active) return;
        setConversation(data.conversation);
        setMessages(data.messages || []);
      })
      .catch((loadError) => active && setError(loadError.message))
      .finally(() => active && setLoadingHistory(false));
    return () => { active = false; };
  }, [conversationId]);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, sending]);

  async function ensureConversation(prompt) {
    if (conversationId) return Number(conversationId);
    const data = await apiRequest("/conversations", {
      method: "POST",
      body: JSON.stringify({ title: prompt.length > 64 ? `${prompt.slice(0, 61)}…` : prompt }),
    });
    setConversation(data.conversation);
    navigate(`/conversations/${data.conversation.id}`, { replace: true });
    return data.conversation.id;
  }

  async function saveMessage(id, role, content) {
    return apiRequest(`/conversations/${id}/messages`, {
      method: "POST",
      body: JSON.stringify({ role, content }),
    });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const prompt = question.trim();
    if (!prompt || sending) return;
    setSending(true);
    setError("");
    setQuestion("");
    const optimisticUserMessage = { id: `user-${Date.now()}`, role: "user", content: prompt };
    setMessages((items) => [...items, optimisticUserMessage]);

    try {
      const id = await ensureConversation(prompt);
      await saveMessage(id, "user", prompt);
      const result = await apiRequest("/ask", {
        method: "POST",
        body: JSON.stringify({ question: prompt }),
      });
      const assistantMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: result.answer,
        citations: result.citations || [],
      };
      setMessages((items) => [...items, assistantMessage]);
      await saveMessage(id, "assistant", result.answer);
    } catch (sendError) {
      setError(sendError.message);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="ask-page">
      <Navbar />
      <main className="ask-main chat-shell">
        <header className="ask-header chat-header">
          <div><p className="ask-eyebrow">INTERNASSIST</p><h1>{conversation?.title || "Ask Assistant"}</h1><p className="ask-description">Answers are grounded in uploaded institutional documents.</p></div>
          <button className="new-chat-button" onClick={() => navigate("/assistant")}>+ New chat</button>
        </header>

        <section className="assistant-panel chat-panel" aria-label="Conversation">
          {loadingHistory ? <div className="chat-empty" role="status">Loading conversation…</div> : messages.length === 0 ? (
            <div className="chat-empty">
              <div className="assistant-icon">IA</div>
              <h2>What would you like to know?</h2>
              <p>Ask about internships, academic requirements or institutional policies.</p>
              <div className="chat-suggestions">{SUGGESTIONS.map((item) => <button key={item} onClick={() => setQuestion(item)}>{item}</button>)}</div>
            </div>
          ) : (
            <div className="message-list">
              {messages.map((message, index) => (
                <article className={`chat-message ${message.role}`} key={message.id || `${message.role}-${index}`}>
                  <div className="message-avatar">{message.role === "user" ? "You" : "IA"}</div>
                  <div className="message-body">
                    <div className="message-role">{message.role === "user" ? "You" : "InternAssist"}</div>
                    <p>{message.content}</p>
                    {message.citations?.length > 0 && (
                      <div className="citations" aria-label="Sources">
                        <strong>Sources</strong>
                        <ul>{message.citations.map((citation, citationIndex) => <li key={`${citation.document_id}-${citation.page_number}-${citationIndex}`}><span>{citation.document_name}</span>{citation.page_number ? ` · Page ${citation.page_number}` : ""}</li>)}</ul>
                      </div>
                    )}
                  </div>
                </article>
              ))}
              {sending && <article className="chat-message assistant"><div className="message-avatar">IA</div><div className="message-body"><div className="message-role">InternAssist</div><div className="typing-indicator" role="status"><span /><span /><span /><em>Searching documents…</em></div></div></article>}
              <div ref={endRef} />
            </div>
          )}

          {error && <div className="chat-error" role="alert">{error} <button onClick={() => setError("")}>Dismiss</button></div>}

          <form className="chat-composer" onSubmit={handleSubmit}>
            <label htmlFor="assistant-question" className="sr-only">Ask a question</label>
            <textarea id="assistant-question" value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form.requestSubmit(); } }} placeholder="Ask a question about your documents…" rows="3" disabled={sending || loadingHistory} />
            <div className="chat-composer-footer"><span>Enter to send · Shift + Enter for a new line</span><button type="submit" disabled={sending || !question.trim()}>{sending ? "Asking…" : "Ask →"}</button></div>
          </form>
        </section>
      </main>
    </div>
  );
}
