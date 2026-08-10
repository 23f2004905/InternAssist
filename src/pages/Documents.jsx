import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import Navbar from "../components/Navbar";
import "./Documents.css";

const API_URL = "http://localhost:5000";

export default function Documents() {
  const { currentUser } = useAuth();

  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);

  const [showUpload, setShowUpload] = useState(false);

  const [title, setTitle] = useState("");
  const [file, setFile] = useState(null);

  const [uploading, setUploading] = useState(false);

  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const isAdmin = currentUser?.role === "admin";


  // --------------------------------
  // Load documents
  // --------------------------------

  async function loadDocuments() {
    try {
      setLoading(true);
      setError("");

      const response = await fetch(
        `${API_URL}/api/documents`,
        {
          credentials: "include",
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.error || "Unable to load documents."
        );
      }

      setDocuments(data.documents || []);

    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }


  useEffect(() => {
    loadDocuments();
  }, []);


  // --------------------------------
  // Upload
  // --------------------------------

  async function handleUpload(e) {
    e.preventDefault();

    setError("");
    setMessage("");

    if (!file) {
      setError("Please select a document.");
      return;
    }

    setUploading(true);

    try {
      const formData = new FormData();

      formData.append(
        "title",
        title.trim()
      );

      formData.append(
        "file",
        file
      );

      const response = await fetch(
        `${API_URL}/api/documents`,
        {
          method: "POST",
          credentials: "include",
          body: formData,
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.error || "Upload failed."
        );
      }

      setMessage(
        "Document uploaded successfully."
      );

      setTitle("");
      setFile(null);

      // Reset file input
      document.getElementById(
        "document-file"
      ).value = "";

      setShowUpload(false);

      await loadDocuments();

    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  }


  // --------------------------------
  // Delete
  // --------------------------------

  async function handleDelete(documentId) {

    const confirmed = window.confirm(
      "Are you sure you want to delete this document?"
    );

    if (!confirmed) {
      return;
    }

    setError("");
    setMessage("");

    try {

      const response = await fetch(
        `${API_URL}/api/documents/${documentId}`,
        {
          method: "DELETE",
          credentials: "include",
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.error || "Unable to delete document."
        );
      }

      setMessage(
        "Document deleted successfully."
      );

      await loadDocuments();

    } catch (err) {
      setError(err.message);
    }
  }


  // --------------------------------
  // View / download
  // --------------------------------

  function handleView(documentId) {

    window.open(
      `${API_URL}/api/documents/${documentId}/download`,
      "_blank"
    );
  }


  // --------------------------------
  // File size
  // --------------------------------

  function formatFileSize(bytes) {

    if (!bytes) {
      return "—";
    }

    if (bytes < 1024) {
      return `${bytes} B`;
    }

    if (bytes < 1024 * 1024) {
      return `${(
        bytes / 1024
      ).toFixed(1)} KB`;
    }

    return `${(
      bytes /
      (1024 * 1024)
    ).toFixed(1)} MB`;
  }


  // --------------------------------
  // Date
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
        year: "numeric",
      }
    );
  }


  return (
    <div className="documents-page">

      <Navbar />


      <main className="documents-main">

        {/* --------------------------------
            Header
        -------------------------------- */}

        <section className="documents-header">

          <div>

            <p className="documents-eyebrow">
              DOCUMENT LIBRARY
            </p>

            <h1>
              Documents
            </h1>

            <p className="documents-subtitle">
              {isAdmin
                ? "Upload and manage institutional documents used by InternAssist."
                : "Browse institutional documents available to you."
              }
            </p>

          </div>


          {isAdmin && (
            <button
              className="upload-document-button"
              onClick={() => {
                setShowUpload(
                  !showUpload
                );

                setError("");
                setMessage("");
              }}
            >
              <span>
                +
              </span>

              Upload Document
            </button>
          )}

        </section>


        {/* --------------------------------
            Messages
        -------------------------------- */}

        {message && (
          <div className="document-message success">
            {message}
          </div>
        )}

        {error && (
          <div className="document-message error">
            {error}
          </div>
        )}


        {/* --------------------------------
            Upload form
        -------------------------------- */}

        {isAdmin && showUpload && (

          <section className="upload-card">

            <div className="upload-card-header">

              <div>

                <h2>
                  Upload document
                </h2>

                <p>
                  Add an institutional document to the
                  InternAssist library.
                </p>

              </div>

            </div>


            <form
              onSubmit={handleUpload}
              className="upload-form"
            >

              <div className="form-field">

                <label htmlFor="document-title">
                  Document title
                </label>

                <input
                  id="document-title"
                  type="text"
                  value={title}
                  onChange={(e) =>
                    setTitle(e.target.value)
                  }
                  placeholder="e.g. Internship Guidelines 2026"
                />

                <small>
                  Leave blank to use the filename.
                </small>

              </div>


              <div className="form-field">

                <label htmlFor="document-file">
                  Select file
                </label>

                <input
                  id="document-file"
                  type="file"
                  accept=".pdf,.docx,.pptx,.txt"
                  onChange={(e) =>
                    setFile(
                      e.target.files[0]
                    )
                  }
                />

                <small>
                  PDF, DOCX, PPTX or TXT · Maximum 20 MB
                </small>

              </div>


              {file && (

                <div className="selected-file">

                  <div className="selected-file-icon">
                    {file.name
                      .split(".")
                      .pop()
                      .toUpperCase()}
                  </div>

                  <div>

                    <strong>
                      {file.name}
                    </strong>

                    <p>
                      {formatFileSize(
                        file.size
                      )}
                    </p>

                  </div>

                </div>

              )}


              <div className="upload-form-actions">

                <button
                  type="button"
                  className="cancel-upload-button"
                  onClick={() => {
                    setShowUpload(false);
                    setTitle("");
                    setFile(null);
                    setError("");
                  }}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  className="confirm-upload-button"
                  disabled={uploading}
                >
                  {uploading
                    ? "Uploading..."
                    : "Upload Document"
                  }
                </button>

              </div>

            </form>

          </section>

        )}


        {/* --------------------------------
            Documents list
        -------------------------------- */}

        <section className="documents-section">

          <div className="documents-section-header">

            <div>

              <h2>
                {isAdmin
                  ? "All documents"
                  : "Available documents"
                }
              </h2>

              <p>
                {documents.length}{" "}
                {documents.length === 1
                  ? "document"
                  : "documents"
                }
              </p>

            </div>

          </div>


          {loading ? (

            <div className="documents-empty">
              Loading documents...
            </div>

          ) : documents.length === 0 ? (

            <div className="documents-empty">

              <div className="empty-icon">
                □
              </div>

              <h3>
                No documents yet
              </h3>

              <p>
                {isAdmin
                  ? "Upload the first institutional document to get started."
                  : "No institutional documents are currently available."
                }
              </p>

              {isAdmin && (
                <button
                  className="empty-upload-button"
                  onClick={() =>
                    setShowUpload(true)
                  }
                >
                  Upload Document
                </button>
              )}

            </div>

          ) : (

            <div className="documents-table-wrapper">

              <table className="documents-table">

                <thead>

                  <tr>

                    <th>
                      DOCUMENT
                    </th>

                    <th>
                      TYPE
                    </th>

                    <th>
                      SIZE
                    </th>

                    <th>
                      UPLOADED
                    </th>

                    {isAdmin && (
                      <th>
                        UPLOADED BY
                      </th>
                    )}

                    <th>
                      STATUS
                    </th>

                    <th>
                      ACTION
                    </th>

                  </tr>

                </thead>


                <tbody>

                  {documents.map(
                    (document) => (

                      <tr
                        key={document.id}
                      >

                        <td>

                          <div className="document-name-cell">

                            <div className="document-type-icon">
                              {document.file_type}
                            </div>

                            <div>

                              <strong>
                                {document.title}
                              </strong>

                              <span>
                                {document.filename}
                              </span>

                            </div>

                          </div>

                        </td>


                        <td>
                          <span className="file-type">
                            {document.file_type}
                          </span>
                        </td>


                        <td>
                          {formatFileSize(
                            document.file_size
                          )}
                        </td>


                        <td>
                          {formatDate(
                            document.uploaded_at
                          )}
                        </td>


                        {isAdmin && (
                          <td>
                            {document.uploaded_by || "—"}
                          </td>
                        )}


                        <td>

                          <span className="document-status">
                            {document.status}
                          </span>

                        </td>


                        <td>

                          <div className="document-actions">

                            <button
                              className="view-document-button"
                              onClick={() =>
                                handleView(
                                  document.id
                                )
                              }
                            >
                              View
                            </button>


                            {isAdmin && (

                              <button
                                className="delete-document-button"
                                onClick={() =>
                                  handleDelete(
                                    document.id
                                  )
                                }
                              >
                                Delete
                              </button>

                            )}

                          </div>

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