import { useEffect, useState } from "react";
import Navbar from "../components/Navbar";
import "./Users.css";

const API_URL = "http://localhost:5001";

export default function Users() {

  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  // --------------------------------
  // Load users
  // --------------------------------

  async function loadUsers() {

    try {

      setLoading(true);
      setError("");

      const response = await fetch(
        `${API_URL}/api/admin/users`,
        {
          credentials: "include"
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.error || "Unable to load users."
        );
      }

      setUsers(data.users || []);

    } catch (err) {

      setError(err.message);

    } finally {

      setLoading(false);

    }
  }


  useEffect(() => {
    loadUsers();
  }, []);


  // --------------------------------
  // Activate / deactivate
  // --------------------------------

  async function changeUserStatus(user) {

    const action = user.active
      ? "deactivate"
      : "activate";

    const confirmed = window.confirm(
      `Are you sure you want to ${action} ${user.name}?`
    );

    if (!confirmed) {
      return;
    }

    setError("");
    setMessage("");

    try {

      const response = await fetch(
        `${API_URL}/api/admin/users/${user.id}/${action}`,
        {
          method: "POST",
          credentials: "include"
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.error ||
          `Unable to ${action} user.`
        );
      }

      setMessage(
        data.message
      );

      await loadUsers();

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


  // --------------------------------
  // Role label
  // --------------------------------

  function formatRole(role) {

    if (!role) {
      return "—";
    }

    return (
      role.charAt(0).toUpperCase() +
      role.slice(1)
    );
  }


  return (
    <div className="users-page">

      <Navbar />

      <main className="users-main">

        {/* --------------------------------
            Header
        -------------------------------- */}

        <section className="users-header">

          <div>

            <p className="users-eyebrow">
              USER MANAGEMENT
            </p>

            <h1>
              Users
            </h1>

            <p className="users-subtitle">
              View and manage student and faculty
              accounts registered in InternAssist.
            </p>

          </div>

        </section>


        {/* --------------------------------
            Messages
        -------------------------------- */}

        {message && (
          <div className="users-message success">
            {message}
          </div>
        )}

        {error && (
          <div className="users-message error">
            {error}
          </div>
        )}


        {/* --------------------------------
            User list
        -------------------------------- */}

        <section className="users-section">

          <div className="users-section-header">

            <div>

              <h2>
                Registered users
              </h2>

              <p>
                {users.length}{" "}
                {users.length === 1
                  ? "account"
                  : "accounts"
                }
              </p>

            </div>

          </div>


          {loading ? (

            <div className="users-empty">
              Loading users...
            </div>

          ) : users.length === 0 ? (

            <div className="users-empty">

              <div className="users-empty-icon">
                👥
              </div>

              <h3>
                No users found
              </h3>

              <p>
                Registered accounts will appear here.
              </p>

            </div>

          ) : (

            <div className="users-table-wrapper">

              <table className="users-table">

                <thead>

                  <tr>

                    <th>
                      USER
                    </th>

                    <th>
                      EMAIL
                    </th>

                    <th>
                      ROLE
                    </th>

                    <th>
                      JOINED
                    </th>

                    <th>
                      STATUS
                    </th>

                    <th>
                      ACTION
                    </th>

                  </tr>

                </thead>


                <tbody>

                  {users.map(
                    (user) => (

                      <tr
                        key={user.id}
                      >

                        {/* User */}

                        <td>

                          <div className="user-name-cell">

                            <div className="user-avatar">
                              {user.name
                                ?.charAt(0)
                                .toUpperCase()}
                            </div>

                            <div>

                              <strong>
                                {user.name}
                              </strong>

                            </div>

                          </div>

                        </td>


                        {/* Email */}

                        <td>
                          {user.email}
                        </td>


                        {/* Role */}

                        <td>

                          <span
                            className={`user-role ${user.role}`}
                          >
                            {formatRole(
                              user.role
                            )}
                          </span>

                        </td>


                        {/* Date */}

                        <td>
                          {formatDate(
                            user.created_at
                          )}
                        </td>


                        {/* Status */}

                        <td>

                          <span
                            className={`user-status ${
                              user.active
                                ? "active"
                                : "inactive"
                            }`}
                          >
                            {user.active
                              ? "Active"
                              : "Inactive"
                            }
                          </span>

                        </td>


                        {/* Action */}

                        <td>

                          {user.role === "admin" ? (

                            <span className="protected-label">
                              Protected
                            </span>

                          ) : (

                            <button
                              className={
                                user.active
                                  ? "deactivate-button"
                                  : "activate-button"
                              }
                              onClick={() =>
                                changeUserStatus(
                                  user
                                )
                              }
                            >
                              {user.active
                                ? "Deactivate"
                                : "Activate"
                              }
                            </button>

                          )}

                        </td>

                      </tr>

                    )
                  )}

                </tbody>

              </table>

            </div>

          )}

        </section>

      </main>

    </div>
  );
}