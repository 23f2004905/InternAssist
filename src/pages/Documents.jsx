import { useCallback, useEffect, useRef, useState } from "react";
import { apiRequest, downloadDocument, uploadDocument } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import Navbar from "../components/Navbar";
import "./Documents.css";

const ALLOWED_EXTENSIONS = ["pdf", "docx", "pptx", "txt"];
const MAX_FILE_SIZE = 20 * 1024 * 1024;

function formatFileSize(bytes) {
  if (bytes === 0) return "0 B";
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export default function Documents() {
  const { currentUser } = useAuth();
  const isAdmin = currentUser?.role === "admin";
  const fileInput = useRef(null);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [title, setTitle] = useState("");
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [downloadingId, setDownloadingId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await apiRequest("/documents");
      setDocuments(data.documents || []);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadDocuments(); }, [loadDocuments]);

  function validateFile(selectedFile) {
    if (!selectedFile) return "Please select a document.";
    const extension = selectedFile.name.split(".").pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(extension)) return "Choose a PDF, DOCX, PPTX or TXT file.";
    if (selectedFile.size > MAX_FILE_SIZE) return "File is too large. Maximum size is 20 MB.";
    return "";
  }

  function handleFileChange(event) {
    const selectedFile = event.target.files?.[0] || null;
    const validationError = validateFile(selectedFile);
    setError(validationError);
    setFile(validationError ? null : selectedFile);
  }

  async function handleUpload(event) {
    event.preventDefault();
    const validationError = validateFile(file);
    if (validationError) { setError(validationError); return; }
    setUploading(true);
    setProgress(0);
    setError("");
    setMessage("");
    try {
      const body = new FormData();
      body.append("title", title.trim());
      body.append("file", file);
      const data = await uploadDocument(body, setProgress);
      setMessage(data?.message || "Document uploaded successfully.");
      setTitle("");
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
      setShowUpload(false);
      await loadDocuments();
    } catch (uploadError) {
      setError(uploadError.message);
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(id) {
    if (!window.confirm("Delete this document? This cannot be undone.")) return;
    setDeletingId(id);
    setError("");
    setMessage("");
    try {
      const data = await apiRequest(`/documents/${id}`, { method: "DELETE" });
      setDocuments((items) => items.filter((item) => item.id !== id));
      setMessage(data.message || "Document deleted successfully.");
    } catch (deleteError) {
      setError(deleteError.message);
    } finally {
      setDeletingId(null);
    }
  }

  async function handleDownload(item) {
    setDownloadingId(item.id);
    setError("");
    try { await downloadDocument(item); }
    catch (downloadError) { setError(downloadError.message); }
    finally { setDownloadingId(null); }
  }

  return (
    <div className="documents-page">
      <Navbar />
      <main className="documents-main">
        <section className="documents-header">
          <div>
            <p className="documents-eyebrow">KNOWLEDGE LIBRARY</p>
            <h1>Documents</h1>
            <p className="documents-subtitle">Browse and download the source material used by InternAssist.</p>
          </div>
          {isAdmin && <button className="upload-document-button" onClick={() => setShowUpload((value) => !value)}>{showUpload ? "Close upload" : "+ Upload document"}</button>}
        </section>

        {message && <div className="documents-message" role="status">{message}</div>}
        {error && <div className="documents-error" role="alert">{error}</div>}

        {isAdmin && showUpload && (
          <section className="upload-card" aria-labelledby="upload-title">
            <div className="upload-card-header">
              <div><h2 id="upload-title">Upload a document</h2><p>PDF, DOCX, PPTX or TXT · up to 20 MB</p></div>
            </div>
            <form className="upload-form" onSubmit={handleUpload}>
              <label htmlFor="document-title">Document title <span>(optional)</span></label>
              <input id="document-title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Defaults to the file name" disabled={uploading} />
              <label htmlFor="document-file">File</label>
              <input ref={fileInput} id="document-file" type="file" accept=".pdf,.docx,.pptx,.txt" onChange={handleFileChange} disabled={uploading} required />
              {file && <div className="selected-file"><div className="selected-file-icon">{file.name.split(".").pop().toUpperCase()}</div><div><strong>{file.name}</strong><p>{formatFileSize(file.size)}</p></div></div>}
              {uploading && <div className="upload-progress" aria-live="polite"><div className="upload-progress-label"><span>Uploading…</span><strong>{progress}%</strong></div><progress max="100" value={progress}>{progress}%</progress></div>}
              <div className="upload-form-actions">
                <button type="button" className="cancel-upload-button" disabled={uploading} onClick={() => setShowUpload(false)}>Cancel</button>
                <button type="submit" className="confirm-upload-button" disabled={uploading || !file}>{uploading ? "Uploading…" : "Upload document"}</button>
              </div>
            </form>
          </section>
        )}

        <section className="documents-section">
          <div className="documents-section-header"><div><h2>{isAdmin ? "All documents" : "Available documents"}</h2><p>{documents.length} {documents.length === 1 ? "document" : "documents"}</p></div><button className="documents-refresh" onClick={loadDocuments} disabled={loading}>Refresh</button></div>
          {loading ? <div className="documents-empty" role="status">Loading documents…</div> : documents.length === 0 ? (
            <div className="documents-empty"><div className="empty-icon">□</div><h3>No documents yet</h3><p>{isAdmin ? "Upload the first institutional document to get started." : "No institutional documents are currently available."}</p></div>
          ) : (
            <div className="documents-table-wrapper">
              <table className="documents-table">
                <thead><tr><th>DOCUMENT</th><th>TYPE</th><th>SIZE</th><th>UPLOADED</th>{isAdmin && <th>UPLOADED BY</th>}<th>STATUS</th><th>ACTIONS</th></tr></thead>
                <tbody>{documents.map((item) => (
                  <tr key={item.id}>
                    <td data-label="Document"><div className="document-name-cell"><div className="document-type-icon">{item.file_type}</div><div><strong>{item.title}</strong><span>{item.filename}</span></div></div></td>
                    <td data-label="Type"><span className="file-type">{item.file_type}</span></td>
                    <td data-label="Size">{formatFileSize(item.file_size)}</td>
                    <td data-label="Uploaded">{formatDate(item.uploaded_at)}</td>
                    {isAdmin && <td data-label="Uploaded by">{item.uploaded_by || "—"}</td>}
                    <td data-label="Status"><span className="document-status">{item.status}</span></td>
                    <td data-label="Actions"><div className="document-actions"><button className="view-document-button" onClick={() => handleDownload(item)} disabled={downloadingId === item.id}>{downloadingId === item.id ? "Downloading…" : "Download"}</button>{isAdmin && <button className="delete-document-button" onClick={() => handleDelete(item.id)} disabled={deletingId === item.id}>{deletingId === item.id ? "Deleting…" : "Delete"}</button>}</div></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
