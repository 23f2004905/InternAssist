# InternAssist Backend

Backend API for InternAssist, an internship placement platform built with Flask, Flask-SQLAlchemy, Flask-Session, Redis, ChromaDB, and Google Gemini.

## Table of Contents
- [Local Setup and Startup](#local-setup-and-startup)
- [Running Automated Tests](#running-automated-tests)
- [Environment Variables Reference](#environment-variables-reference)
- [Deployment Dependencies & Considerations](#deployment-dependencies--considerations)

---

## Local Setup and Startup

### 1. Prerequisites
- Python 3.11+ (Python 3.13 supported)
- Optional: Redis running on `localhost:6379` (routes operate gracefully with or without Redis)

### 2. Virtual Environment Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy the sanitized environment template:
```bash
cp .env.example .env
```
Populate `.env` with appropriate development credentials and keys.

### 4. Run the Development Server
```bash
python app.py
```
The server will start on `http://127.0.0.1:5001`.

---

## Running Automated Tests

Run the full test suite using `pytest`:
```bash
python3 -m pytest -v
```
All existing tests and deployment readiness tests will execute against isolated test databases and in-memory/mocked services.

Run Python compilation checks:
```bash
python3 -m py_compile *.py services/*.py tests/*.py
```

Run whitespace / git check:
```bash
git diff --check
```

---

## Environment Variables Reference

| Variable | Default | Purpose / Allowed Values |
|---|---|---|
| `FLASK_ENV` | `development` | Set to `production` in production mode (enforces security checks). |
| `SECRET_KEY` | `development-secret-key` | Session and cryptographic secret. Required to be non-default in production. |
| `PORT` | `5001` | HTTP port for Flask development server. |
| `DATABASE_URL` | `sqlite:///internassist.db` | SQLAlchemy database URI. Supports SQLite and PostgreSQL (`postgresql://...` or `postgres://...`). |
| `DB_POOL_RECYCLE` | `300` | Connection pool recycle interval in seconds. |
| `ADMIN_NAME` | `System Administrator` | Full name of default administrator created at startup. |
| `ADMIN_EMAIL` | *(None)* | Email for initial administrator. If omitted, admin creation is skipped. |
| `ADMIN_PASSWORD` | *(None)* | Secure password for initial administrator. If omitted, admin creation is skipped. |
| `SESSION_TYPE` | `filesystem` | Session storage backend: `filesystem`, `redis`, or `sqlalchemy`. |
| `SESSION_FILE_DIR` | `flask_session` | Directory path for filesystem session files. |
| `SESSION_COOKIE_SECURE`| `false` | Set to `true` in production to enforce HTTPS-only cookies. |
| `SESSION_COOKIE_SAMESITE`| `Lax` | SameSite cookie policy (`Lax`, `Strict`, `None`). |
| `REDIS_URL` | *(None)* | Redis connection URL (e.g., `redis://:password@host:6379/0`). |
| `REDIS_HOST` | `localhost` | Redis server hostname if `REDIS_URL` is unset. |
| `REDIS_PORT` | `6379` | Redis server port. |
| `REDIS_PASSWORD` | *(None)* | Redis password if authentication is required. |
| `REDIS_DB` | `0` | Redis logical database number. |
| `REDIS_CONNECT_TIMEOUT`| `2.0` | Socket connection timeout in seconds. |
| `REDIS_TIMEOUT` | `2.0` | Socket read/write timeout in seconds. |
| `REDIS_CHAT_TTL` | `3600` | Cache time-to-live for conversation history in seconds. |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated list of allowed frontend origins. |
| `UPLOAD_FOLDER` | `backend/uploads` | Path for storing uploaded documents (PDF, DOCX, PPTX, TXT). |
| `CHROMA_DB_PATH` | `chroma_db` | Persistent directory for ChromaDB vector embeddings. |
| `GEMINI_API_KEY` | *(None)* | Google Gemini API key for RAG assistant answers. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model name (e.g. `gemini-2.5-flash`, `gemini-2.0-flash`). |
| `GEMINI_REQUEST_TIMEOUT` | *(None)* | Request timeout in seconds or milliseconds for Gemini API requests. |

---

## Deployment Dependencies & Considerations

1. **PostgreSQL Driver**:
   - `psycopg2-binary>=2.9.9` is included in `requirements.txt`.
   - When deploying with PostgreSQL (`DATABASE_URL=postgresql://...`), ensure the environment installs `requirements.txt`. The application automatically converts legacy `postgres://` URLs to `postgresql://`.

2. **Redis Service**:
   - Production deployments can use Redis for both conversation caching and session persistence (`SESSION_TYPE=redis`).
   - If Redis becomes unavailable, the application gracefully degrades by reading/writing conversation messages directly from the relational database without route failures.

3. **Persistent Volume Storage on Render & Containers**:
   - `UPLOAD_FOLDER` and `CHROMA_DB_PATH` store uploaded files and vector embeddings on the local filesystem.
   - **Render Warning**: Filesystem storage on Render web services is **ephemeral**. Any files stored in the container are **wiped on restarts, redeploys, or free-tier sleep cycles** unless a Render Persistent Disk is attached and configured via `UPLOAD_FOLDER` and `CHROMA_DB_PATH` (e.g., `/var/data/uploads` and `/var/data/chroma_db`).
   - For persistence across restarts, provision a persistent disk or volume and map these paths accordingly. Do not assume persistence without a persistent disk.

4. **Production Gunicorn Startup Command on Render**:
   - To prevent worker timeouts and 502 Bad Gateway errors during ChromaDB embeddings and Gemini API calls, run Gunicorn with 1 worker, thread concurrency, and an extended 120-second timeout:
   ```bash
   gunicorn --chdir backend --workers 1 --threads 4 --timeout 120 app:app
   ```
   - Running multiple worker processes on constrained hosts (such as Render's 512MB RAM tier) causes memory exhaustion (OOM killer SIGKILL) due to ONNX runtime embedding models duplicated across processes. Using 1 worker with multiple threads keeps memory usage well under 512MB while supporting concurrent requests.

5. **Cross-Site Authentication (Vercel Frontend + Render Backend)**:
   - When the frontend is hosted on Vercel and the backend on Render, browsers treat API requests as cross-site.
   - In production (`FLASK_ENV=production`), session cookies automatically configure `SameSite=None` and `Secure=True` so credentials persist across cross-site fetch requests (`credentials: "include"`). Ensure `CORS_ORIGINS` includes your Vercel deployment URL (e.g., `https://your-app.vercel.app`).

6. **Production Startup Safety**:
   - When `FLASK_ENV=production` or `ENVIRONMENT=production`, the application validates that `SECRET_KEY` is explicitly set to a strong secret (at least 32 characters) and not the default `development-secret-key`, failing startup safely if missing.

7. **Live Demonstration & Production Verification Checklist**:
   - **Step 1: Set Render Environment Variables**:
     Ensure `CORS_ORIGINS=https://internassist.vercel.app`, `FLASK_ENV=production`, `SECRET_KEY`, `DATABASE_URL`, and `GEMINI_API_KEY` are all set in Render Dashboard.
   - **Step 2: Log in as Administrator**:
     Log in using `ADMIN_EMAIL` and `ADMIN_PASSWORD` (configured via Render environment variables).
   - **Step 3: Upload Knowledge Base Documents**:
     Because Render's filesystem is ephemeral by default, navigate to the **Documents** page as admin and upload the internship policy document (e.g. `Annexure_2.3.A__Internship_SOP.pdf`). Text extraction and ChromaDB chunk embedding will occur automatically.
   - **Step 4: Test Assistant Question**:
     Navigate to **Ask Assistant**, ask a question (e.g., "What documents are required to apply for an internship?"), and verify that the AI answers with markdown formatting and clickable source citations.
   - **Step 5: Verify Conversation History**:
     Click **View conversation history →** or navigate to **My Conversations** and open the conversation to confirm that both the student question and AI response are persisted and displayed.

## Durable document storage migration

Before deploying a release that uses `DocumentFile`, apply `migrations/001_document_files.sql`
against the existing PostgreSQL database (for Neon, use the SQL editor). The table stores
original upload bytes in PostgreSQL; Render's local `UPLOAD_FOLDER` is only a cache and is
recreated automatically when a document is downloaded. Existing documents uploaded before
this migration do not have recoverable bytes in the database: re-upload those files once.

Rollback: `DROP TABLE IF EXISTS document_files;` (this removes stored document bytes, so
export/back up the table before rolling back). Keep the table for normal application rollback.
