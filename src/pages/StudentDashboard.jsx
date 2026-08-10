import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import "./Dashboard.css";

export default function StudentDashboard() {
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
    <div className="student-page">

      <Navbar />


      <main className="student-main">

        {/* --------------------------------
            Welcome
        -------------------------------- */}

        <section className="student-welcome">

          <div>

            <p className="dashboard-eyebrow">
              STUDENT DASHBOARD
            </p>

            <h1>
              Welcome back,{" "}
              {currentUser?.name?.split(" ")[0]}
            </h1>

            <p className="dashboard-subtitle">
              Find answers about internships, academic
              requirements and institutional policies.
            </p>

          </div>

        </section>


        {/* --------------------------------
            Main Assistant
        -------------------------------- */}

        <section className="student-assistant">

          <div className="assistant-heading">

            <div className="assistant-symbol">
              ?
            </div>

            <div>

              <p className="assistant-label">
                INTERNASSIST
              </p>

              <h2>
                What would you like to know?
              </h2>

              <p>
                Ask a question about your internship or
                institutional guidelines.
              </p>

            </div>

          </div>


          <div className="question-input-wrapper">

            <input
              type="text"
              value={question}
              onChange={(e) =>
                setQuestion(e.target.value)
              }
              onKeyDown={handleKeyDown}
              placeholder="Ask about internship rules, documents, deadlines..."
            />

            <button
              className="ask-button"
              onClick={handleAsk}
            >
              Ask
              <span>→</span>
            </button>

          </div>


          <div className="suggestion-row">

            <span>
              Try asking:
            </span>

            <button
              onClick={() => {
                setQuestion(
                  "What documents are required for an internship?"
                );
              }}
            >
              What documents are required?
            </button>

            <button
              onClick={() => {
                setQuestion(
                  "What are the internship submission requirements?"
                );
              }}
            >
              Submission requirements
            </button>

          </div>

        </section>


        {/* --------------------------------
            Quick Access
        -------------------------------- */}

        <section className="student-section">

          <div className="section-heading">

            <div>

              <h2>
                Quick access
              </h2>

              <p>
                Commonly used areas
              </p>

            </div>

          </div>


          <div className="student-actions">

            <button
              className="student-action"
              onClick={() => navigate("/assistant")}
            >

              <div className="student-action-icon">
                ?
              </div>

              <div className="student-action-content">

                <h3>
                  Ask Assistant
                </h3>

                <p>
                  Search institutional information
                  using natural language.
                </p>

              </div>

              <span className="student-action-arrow">
                →
              </span>

            </button>


            <button
              className="student-action"
              onClick={() => navigate("/documents")}
            >

              <div className="student-action-icon">
                □
              </div>

              <div className="student-action-content">

                <h3>
                  Documents
                </h3>

                <p>
                  Browse documents available to you.
                </p>

              </div>

              <span className="student-action-arrow">
                →
              </span>

            </button>


            <button
              className="student-action"
              onClick={() =>
                navigate("/conversations")
              }
            >

              <div className="student-action-icon">
                ◷
              </div>

              <div className="student-action-content">

                <h3>
                  My Conversations
                </h3>

                <p>
                  Revisit questions you have asked before.
                </p>

              </div>

              <span className="student-action-arrow">
                →
              </span>

            </button>

          </div>

        </section>


        {/* --------------------------------
            What you can ask
        -------------------------------- */}

        <section className="student-section">

          <div className="section-heading">

            <div>

              <h2>
                What can you ask?
              </h2>

              <p>
                InternAssist is designed around institutional
                information.
              </p>

            </div>

          </div>


          <div className="topic-grid">

            <div className="topic-card">

              <span className="topic-number">
                01
              </span>

              <h3>
                Internship process
              </h3>

              <p>
                Requirements, procedures and important
                internship steps.
              </p>

            </div>


            <div className="topic-card">

              <span className="topic-number">
                02
              </span>

              <h3>
                Academic policies
              </h3>

              <p>
                Guidelines and rules related to academic
                requirements.
              </p>

            </div>


            <div className="topic-card">

              <span className="topic-number">
                03
              </span>

              <h3>
                Documents
              </h3>

              <p>
                Find information contained in official
                institutional documents.
              </p>

            </div>

          </div>

        </section>


        {/* --------------------------------
            Trust / Information
        -------------------------------- */}

        <section className="student-note">

          <div className="student-note-mark">
            ✓
          </div>

          <div>

            <strong>
              Answers will include their sources
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