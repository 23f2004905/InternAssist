import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import "./Dashboard.css";

export default function FacultyDashboard() {
  const { currentUser } = useAuth();
  const navigate = useNavigate();

  const [question, setQuestion] = useState("");

  function handleAsk() {
    if (!question.trim()) {
      navigate("/assistant");
      return;
    }

    navigate("/assistant", {
      state: {
        question: question.trim(),
      },
    });
  }

  function handleKeyDown(e) {
    if (e.key === "Enter") {
      handleAsk();
    }
  }

  return (
    <div className="faculty-page">

      <Navbar />

      <main className="faculty-main">

        {/* --------------------------------
            Welcome
        -------------------------------- */}

        <section className="faculty-welcome">

          <div>

            <p className="dashboard-eyebrow">
              FACULTY DASHBOARD
            </p>

            <h1>
              Welcome back,{" "}
              {currentUser?.name?.split(" ")[0]}
            </h1>

            <p className="dashboard-subtitle">
              Access institutional information and support
              students with internship-related queries.
            </p>

          </div>

          <div className="faculty-role">
            Faculty
          </div>

        </section>


        {/* --------------------------------
            Assistant
        -------------------------------- */}

        <section className="faculty-assistant">

          <div className="faculty-assistant-heading">

            <div className="faculty-assistant-symbol">
              ?
            </div>

            <div>

              <p className="faculty-assistant-label">
                INTERNASSIST
              </p>

              <h2>
                Find institutional information
              </h2>

              <p>
                Ask about internship guidelines, academic
                policies and institutional procedures.
              </p>

            </div>

          </div>


          <div className="faculty-question-wrapper">

            <input
              type="text"
              value={question}
              onChange={(e) =>
                setQuestion(e.target.value)
              }
              onKeyDown={handleKeyDown}
              placeholder="Ask about a policy, guideline or procedure..."
            />

            <button
              className="faculty-ask-button"
              onClick={handleAsk}
            >
              Ask
              <span>→</span>
            </button>

          </div>


          <div className="faculty-suggestion-row">

            <span>
              Try:
            </span>

            <button
              onClick={() =>
                setQuestion(
                  "What are the internship evaluation requirements?"
                )
              }
            >
              Internship evaluation requirements
            </button>

            <button
              onClick={() =>
                setQuestion(
                  "What documents are required for internship approval?"
                )
              }
            >
              Internship approval documents
            </button>

          </div>

        </section>


        {/* --------------------------------
            Faculty tools
        -------------------------------- */}

        <section className="faculty-section">

          <div className="section-heading">

            <div>

              <h2>
                Faculty tools
              </h2>

              <p>
                Access the main areas of InternAssist.
              </p>

            </div>

          </div>


          <div className="faculty-actions">

            <button
              className="faculty-action"
              onClick={() =>
                navigate("/assistant")
              }
            >

              <div className="faculty-action-icon">
                ?
              </div>

              <div className="faculty-action-content">

                <h3>
                  Ask Assistant
                </h3>

                <p>
                  Search institutional information using
                  natural language.
                </p>

              </div>

              <span>
                →
              </span>

            </button>


            <button
              className="faculty-action"
              onClick={() =>
                navigate("/documents")
              }
            >

              <div className="faculty-action-icon">
                □
              </div>

              <div className="faculty-action-content">

                <h3>
                  Documents
                </h3>

                <p>
                  Review policies, guidelines and available
                  institutional documents.
                </p>

              </div>

              <span>
                →
              </span>

            </button>


            <button
              className="faculty-action"
              onClick={() =>
                navigate("/conversations")
              }
            >

              <div className="faculty-action-icon">
                ◷
              </div>

              <div className="faculty-action-content">

                <h3>
                  Conversations
                </h3>

                <p>
                  Revisit your previous assistant interactions.
                </p>

              </div>

              <span>
                →
              </span>

            </button>

          </div>

        </section>


        {/* --------------------------------
            Information areas
        -------------------------------- */}

        <section className="faculty-section">

          <div className="section-heading">

            <div>

              <h2>
                Information areas
              </h2>

              <p>
                Topics commonly relevant to faculty.
              </p>

            </div>

          </div>


          <div className="faculty-topic-grid">

            <div className="faculty-topic-card">

              <span className="faculty-topic-number">
                01
              </span>

              <h3>
                Internship guidelines
              </h3>

              <p>
                Procedures, requirements and evaluation
                guidelines related to student internships.
              </p>

            </div>


            <div className="faculty-topic-card">

              <span className="faculty-topic-number">
                02
              </span>

              <h3>
                Academic policies
              </h3>

              <p>
                Institutional rules and academic requirements
                available through uploaded documents.
              </p>

            </div>


            <div className="faculty-topic-card">

              <span className="faculty-topic-number">
                03
              </span>

              <h3>
                Student support
              </h3>

              <p>
                Quickly find information that can help answer
                common student questions.
              </p>

            </div>

          </div>

        </section>


        {/* --------------------------------
            Source information
        -------------------------------- */}

        <section className="faculty-source-note">

          <div className="faculty-source-mark">
            ✓
          </div>

          <div>

            <strong>
              Source-based responses
            </strong>

            <p>
              InternAssist is designed to show the document
              and page used to support an answer.
            </p>

          </div>

        </section>

      </main>

    </div>
  );
}