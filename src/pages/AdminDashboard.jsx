import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import "./Dashboard.css";

const API_URL = "http://localhost:5000";

export default function AdminDashboard() {

  const navigate = useNavigate();

  const [stats, setStats] = useState({
    users: 0,
    documents: 0,
    conversations: 0
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");


  // --------------------------------
  // Load dashboard statistics
  // --------------------------------

  async function loadStats() {

    try {

      setLoading(true);
      setError("");

      const response = await fetch(
        `${API_URL}/api/admin/stats`,
        {
          credentials: "include"
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.error ||
          "Unable to load dashboard statistics."
        );
      }

      setStats({
        users: data.users ?? 0,
        documents: data.documents ?? 0,
        conversations: data.conversations ?? 0
      });

    } catch (err) {

      setError(err.message);

    } finally {

      setLoading(false);

    }
  }


  useEffect(() => {
    loadStats();
  }, []);


  return (
    <div className="admin-page">

      <Navbar />

      <main className="admin-main">

        {/* --------------------------------
            Header
        -------------------------------- */}

        <section className="admin-welcome">

          <p className="admin-eyebrow">
            ADMINISTRATION
          </p>

          <h1>
            System Overview
          </h1>

          <p className="admin-subtitle">
            Manage users, documents and conversations
            across InternAssist.
          </p>

        </section>


        {/* --------------------------------
            Error
        -------------------------------- */}

        {error && (
          <div className="admin-error-message">
            {error}
          </div>
        )}


        {/* --------------------------------
            Overview cards
        -------------------------------- */}

        <section className="admin-overview-grid">


          {/* Users */}

          <div
            className="admin-stat-card clickable"
            onClick={() => navigate("/users")}
          >

            <div className="admin-stat-top">

              <span>
                USERS
              </span>

              <div className="admin-stat-icon">
                01
              </div>

            </div>

            <strong className="admin-stat-value">

              {loading
                ? "—"
                : stats.users
              }

            </strong>

            <p>
              Registered accounts
            </p>

          </div>


          {/* Documents */}

          <div
            className="admin-stat-card clickable"
            onClick={() => navigate("/documents")}
          >

            <div className="admin-stat-top">

              <span>
                DOCUMENTS
              </span>

              <div className="admin-stat-icon">
                02
              </div>

            </div>

            <strong className="admin-stat-value">

              {loading
                ? "—"
                : stats.documents
              }

            </strong>

            <p>
              Institutional documents
            </p>

          </div>


          {/* Conversations */}

          <div
            className="admin-stat-card clickable"
            onClick={() => navigate("/conversations")}
          >

            <div className="admin-stat-top">

              <span>
                CONVERSATIONS
              </span>

              <div className="admin-stat-icon">
                03
              </div>

            </div>

            <strong className="admin-stat-value">

              {loading
                ? "—"
                : stats.conversations
              }

            </strong>

            <p>
              Assistant conversations
            </p>

          </div>

        </section>


        {/* --------------------------------
            Management
        -------------------------------- */}

        <section className="admin-section">

          <div className="admin-section-heading">

            <h2>
              Management
            </h2>

            <p>
              Manage the main resources used by InternAssist.
            </p>

          </div>


          <div className="admin-management-list">


            {/* Documents */}

            <button
              className="admin-management-item"
              onClick={() =>
                navigate("/documents")
              }
            >

              <div className="admin-management-number">
                01
              </div>

              <div className="admin-management-content">

                <h3>
                  Documents
                </h3>

                <p>
                  Upload and manage institutional documents
                  used by the assistant.
                </p>

              </div>

              <div className="admin-management-action">

                Manage

                <span>
                  →
                </span>

              </div>

            </button>


            {/* Users */}

            <button
              className="admin-management-item"
              onClick={() =>
                navigate("/users")
              }
            >

              <div className="admin-management-number">
                02
              </div>

              <div className="admin-management-content">

                <h3>
                  Users
                </h3>

                <p>
                  View and manage student and faculty accounts.
                </p>

              </div>

              <div className="admin-management-action">

                Manage

                <span>
                  →
                </span>

              </div>

            </button>


            {/* Conversations */}

            <button
              className="admin-management-item"
              onClick={() =>
                navigate("/conversations")
              }
            >

              <div className="admin-management-number">
                03
              </div>

              <div className="admin-management-content">

                <h3>
                  Conversations
                </h3>

                <p>
                  View assistant conversations across the system.
                </p>

              </div>

              <div className="admin-management-action">

                View

                <span>
                  →
                </span>

              </div>

            </button>

          </div>

        </section>

      </main>

    </div>
  );
}