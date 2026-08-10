import { useState } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import "./AskAssistant.css";

export default function AskAssistant() {

  const navigate = useNavigate();

  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);

  function handleSubmit(event) {
    event.preventDefault();

    const value = question.trim();

    if (!value) {
      return;
    }

    /*
      The real document-based assistant will be connected
      in the next backend phase.

      For now, we are only preparing the interface.
    */

    setLoading(true);

    setTimeout(() => {
      setLoading(false);
    }, 500);
  }


  function useSuggestion(text) {
    setQuestion(text);
  }


  return (
    <div className="ask-page">

      <Navbar />

      <main className="ask-main">

        {/* Header */}

        <section className="ask-header">

          <p className="ask-eyebrow">
            INTERNASSIST
          </p>

          <h1>
            Ask Assistant
          </h1>

          <p className="ask-description">
            Ask questions about internships, academic
            requirements and institutional policies.
          </p>

        </section>


        {/* Main assistant box */}

        <section className="assistant-panel">

          <div className="assistant-panel-header">

            <div className="assistant-icon">
              ?
            </div>

            <div>

              <h2>
                What would you like to know?
              </h2>

              <p>
                Ask your question in natural language.
              </p>

            </div>

          </div>


          <form
            onSubmit={handleSubmit}
            className="ask-form"
          >

            <textarea
              value={question}
              onChange={(event) =>
                setQuestion(event.target.value)
              }
              placeholder="For example: What documents are required to apply for an internship?"
              rows="5"
              disabled={loading}
            />

            <div className="ask-form-footer">

              <span>
                Your answer will be based on
                institutional documents.
              </span>

              <button
                type="submit"
                disabled={
                  loading ||
                  !question.trim()
                }
              >
                {loading
                  ? "Processing..."
                  : "Ask Assistant →"}
              </button>

            </div>

          </form>

        </section>


        {/* Suggested questions */}

        <section className="suggestions-section">

          <div className="section-heading">

            <h2>
              Suggested questions
            </h2>

            <p>
              You can start with one of these common queries.
            </p>

          </div>


          <div className="suggestions-grid">

            <button
              onClick={() =>
                useSuggestion(
                  "What documents are required for an internship?"
                )
              }
            >
              <span>01</span>

              <strong>
                Internship documents
              </strong>

              <small>
                Find documents required for internship applications.
              </small>
            </button>


            <button
              onClick={() =>
                useSuggestion(
                  "What are the internship approval requirements?"
                )
              }
            >
              <span>02</span>

              <strong>
                Approval requirements
              </strong>

              <small>
                Understand the process and requirements for approval.
              </small>
            </button>


            <button
              onClick={() =>
                useSuggestion(
                  "How is the internship evaluated?"
                )
              }
            >
              <span>03</span>

              <strong>
                Internship evaluation
              </strong>

              <small>
                Find information about evaluation and assessment.
              </small>
            </button>

          </div>

        </section>


        {/* Information note */}

        <section className="assistant-note">

          <div className="note-icon">
            ✓
          </div>

          <div>

            <strong>
              Source-based answers
            </strong>

            <p>
              InternAssist is designed to answer questions
              using the institution's uploaded documents
              and show the source used for the response.
            </p>

          </div>

        </section>


        <button
          className="back-to-dashboard"
          onClick={() =>
            navigate("/dashboard")
          }
        >
          ← Back to dashboard
        </button>

      </main>

    </div>
  );
}