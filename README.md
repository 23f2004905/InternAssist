# InternAssist

InternAssist is a React + Flask application for browsing institutional documents and asking source-grounded questions about them.

## Frontend features

- Session-based login, registration, current-user restoration and logout
- Cookie credentials on every authenticated API request
- Role-aware dashboards and navigation
- Document library with authenticated download
- Admin upload for PDF, DOCX, PPTX and TXT, including validation and upload progress
- Admin document deletion with confirmation and in-progress states
- Conversation history, new/continued chats and message persistence
- Atomic `POST /api/conversations/:id/ask` integration using persisted context
- AI answers with document/page citations
- Responsive layouts, loading states and accessible error/success feedback

## Frontend environment variables

Copy `.env.example` to `.env` when the Flask API is not running at the default address.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `VITE_API_BASE_URL` | No | `http://localhost:5001/api` | Full Flask API root, without a trailing slash. |

Vite reads environment variables at startup, so restart the frontend after changing `.env`.

## Run locally

### Backend

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
flask --app app db upgrade
cd ..
python backend/app.py
```

The backend runs at `http://localhost:5001`. Configure `SECRET_KEY`, `FRONTEND_ORIGINS`, and `GEMINI_API_KEY` in `backend/.env`; HTTPS production deployments must use `SESSION_COOKIE_SECURE=true`. `REDIS_URL` is optional and is only a cache—SQLite is always the source of truth for ordered messages and citations. A default administrator is created only when both `DEFAULT_ADMIN_EMAIL` and `DEFAULT_ADMIN_PASSWORD` are explicitly set.

Uploads support validated PDF, DOCX, PPTX, and UTF-8 TXT files up to `MAX_UPLOAD_BYTES` (20 MiB by default). Failed extraction or indexing is rolled back. Deletion removes the stored file, database row, and all associated vector chunks.

### Frontend

```bash
npm ci
npm run dev
```

The frontend runs at `http://localhost:5173`.

## Verified backend contracts

- `POST /api/auth/register`: JSON `name`, `email`, `password`, `role`
- `POST /api/auth/login`: JSON `email`, `password`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `GET /api/documents`
- `POST /api/documents`: multipart fields `title`, `file` (admin)
- `GET /api/documents/:id/download`
- `DELETE /api/documents/:id` (admin)
- `GET|POST /api/conversations`
- `GET|DELETE /api/conversations/:id`
- `POST /api/conversations/:id/messages`: JSON user `role`, `content`
- `POST /api/conversations/:id/ask`: JSON `question`; persists the user message, contextual answer, and citations
- `GET /api/admin/conversations` (admin)
- `POST /api/ask`: JSON `question`; returns `answer` and `citations`

All frontend calls send cookie credentials and mutating requests send the token obtained from `GET /api/auth/csrf`.

## Screenshots

- [Login](docs/screenshots/01-login.png)
- [Admin dashboard](docs/screenshots/02-dashboard.png)
- [Document upload](docs/screenshots/03-upload.png)
- [Chat](docs/screenshots/04-chat.png)
- [Mobile documents](docs/screenshots/05-mobile-documents.png)

## Checks

```bash
npm run lint
npm run build
npm test
python -m compileall backend
cd backend && pytest -q
```
