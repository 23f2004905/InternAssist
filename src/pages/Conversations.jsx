import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import "./Conversations.css";

const API_URL = "http://localhost:5001";

export default function Conversations() {

  const navigate = useNavigate();

  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");


  // --------------------------------
  // Load conversations
  // --------------------------------

  async function loadConversations() {

    try {

      setLoading(true);
      setError("");

      const response = await fetch(
        `${API_URL}/api/conversations`,
        {
          credentials: "include"
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.error ||
          "Unable to load conversations."
        );
      }

      setConversations(
        data.conversations || []
      );

    } catch (err) {

      setError(err.message);

    } finally {

      setLoading(false);

    }
  }


  useEffect(() => {
    loadConversations();
  }, []);


  // --------------------------------
  // Create conversation
  // --------------------------------

  async function createConversation() {

    try {

      const response = await fetch(
        `${API_URL}/api/conversations`,
        {
          method: "POST",

          headers: {
            "Content-Type": "application/json"
          },

          credentials: "include",

          body: JSON.stringify({
            title: "New Conversation"
          })
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.error ||
          "Unable to create conversation."
        );
      }

      navigate(
        `/conversations/${data.conversation.id}`
      );

    } catch (err) {

      setError(err.message);

    }
  }


  // --------------------------------
  // Delete conversation
  // --------------------------------

  async function deleteConversation(
    conversationId
  ) {

    const confirmed = window.confirm(
      "Delete this conversation?"
    );

    if (!confirmed) {
      return;
    }

    try {

      const response = await fetch(
        `${API_URL}/api/conversations/${conversationId}`,
        {
          method: "DELETE",
          credentials: "include"
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.error ||
          "Unable to delete conversation."
        );
      }

      await loadConversations();

    } catch (err) {

      setError(err.message);

    }
  }


  // --------------------------------
  // Format date
  // --------------------------------

  function formatDate(dateString) {

    if (!dateString) {
      return "—";
    }

    return new Date(
      dateString
    ).toLocaleDateString(
      "en-IN",
      {
        day: "2-digit",
        month: "short",
        year: "numeric"
      }
    );
  }


  return (
    <div className="conversations-page">

      <Navbar />

      <main className="conversations-main">

        <section className="conversations-header">

          <div>

            <p className="conversations-eyebrow">
              CONVERSATIONS
            </p>

            <h1>
              My Conversations
            </h1>

            <p className="conversations-subtitle">
              Review your previous questions and
              assistant interactions.
            </p>

          </div>


          <button
            className="new-conversation-button"
            onClick={createConversation}
          >
            + New conversation
          </button>

        </section>


        {error && (
          <div className="conversation-error">
            {error}
          </div>
        )}


        {loading ? (

          <div className="conversation-empty">
            Loading conversations...
          </div>

        ) : conversations.length === 0 ? (

          <div className="conversation-empty">

            <div className="conversation-empty-icon">
              ?
            </div>

            <h2>
              No conversations yet
            </h2>

            <p>
              Start a conversation with InternAssist
              to see your questions and answers here.
            </p>

            <button
              className="empty-start-button"
              onClick={createConversation}
            >
              Start a conversation
            </button>

          </div>

        ) : (

          <section className="conversation-list">

            {conversations.map(
              (conversation) => (

                <div
                  className="conversation-card"
                  key={conversation.id}
                >

                  <div
                    className="conversation-card-main"
                    onClick={() =>
                      navigate(
                        `/conversations/${conversation.id}`
                      )
                    }
                  >

                    <div className="conversation-icon">
                      ?
                    </div>

                    <div>

                      <h2>
                        {conversation.title}
                      </h2>

                      <p>
                        Updated{" "}
                        {formatDate(
                          conversation.updated_at
                        )}
                      </p>

                    </div>

                  </div>


                  <button
                    className="conversation-delete"
                    onClick={() =>
                      deleteConversation(
                        conversation.id
                      )
                    }
                  >
                    Delete
                  </button>

                </div>

              )
            )}

          </section>

        )}

      </main>

    </div>
  );
}