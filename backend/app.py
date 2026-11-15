import json
import os
import secrets
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory, session
from flask_cors import CORS
from flask_migrate import Migrate
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from database import db
from models import Conversation, Document, Message, User
from services.chunking import chunk_text
from services.document_extractor import DocumentExtractionError, extract_document_pages
from services.llm import AIConfigurationError, AIUpstreamError, ask_gemini
from services.redis_service import delete_chat_history, save_chat_history
from services.vectorstore import add_chunks, delete_document_chunks, get_document_chunks, restore_document_chunks, search

load_dotenv()
app = Flask(__name__)
environment = os.getenv("APP_ENV", "development").lower()
secret_key = os.getenv("SECRET_KEY")
if not secret_key and environment == "production":
    raise RuntimeError("SECRET_KEY must be configured in production.")

app.config.update(
    SECRET_KEY=secret_key or "development-only-secret-change-me",
    SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///internassist.db"),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAX_CONTENT_LENGTH=int(os.getenv("MAX_UPLOAD_BYTES", 20 * 1024 * 1024)),
    SESSION_PERMANENT=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE=os.getenv("SESSION_COOKIE_SAMESITE", "Lax"),
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "true" if environment == "production" else "false").lower() == "true",
)
origins = [value.strip() for value in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if value.strip()]
CORS(app, origins=origins, supports_credentials=True, allow_headers=["Content-Type", "X-CSRF-Token"])
app.config["UPLOAD_FOLDER"] = os.getenv("UPLOAD_FOLDER", os.path.join(app.root_path, "uploads"))
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
db.init_app(app)
Migrate(app, db)
ALLOWED_EXTENSIONS = {"pdf", "docx", "pptx", "txt"}


def create_default_admin():
    email = os.getenv("DEFAULT_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("DEFAULT_ADMIN_PASSWORD", "")
    if not email or not password or User.query.filter_by(email=email).first():
        return
    admin = User(name="System Administrator", email=email, role="admin")
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()


with app.app_context():
    db.create_all()
    create_default_admin()


@app.before_request
def validate_csrf():
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"} or not request.path.startswith("/api/"):
        return None
    expected = session.get("csrf_token")
    supplied = request.headers.get("X-CSRF-Token", "")
    if not expected or not supplied or not secrets.compare_digest(expected, supplied):
        return jsonify({"error": "Invalid or missing CSRF token."}), 403
    return None


def get_logged_in_user():
    user_id = session.get("user_id")
    user = db.session.get(User, user_id) if user_id else None
    if user_id and (not user or not user.active):
        session.clear()
        return None
    return user


def require_user(role=None):
    user = get_logged_in_user()
    if not user:
        return None, (jsonify({"error": "Authentication required."}), 401)
    if role and user.role != role:
        return None, (jsonify({"error": f"{role.capitalize()} access required."}), 403)
    return user, None


def allowed_file(filename):
    return bool(filename and "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS)


def ordered_messages(conversation_id):
    return Message.query.filter_by(conversation_id=conversation_id).order_by(Message.id.asc()).all()


def cache_conversation(conversation_id):
    history = [message.to_dict() for message in ordered_messages(conversation_id)]
    save_chat_history(conversation_id, history)
    return history


def citation_for_chunk(chunk):
    document = db.session.get(Document, chunk["document_id"])
    if not document:
        return None
    return {"document_id": document.id, "document_name": document.filename, "page_number": chunk.get("page_number")}


def answer_conversation(conversation, question):
    previous = [message.to_dict() for message in ordered_messages(conversation.id)]
    user_message = Message(conversation_id=conversation.id, role="user", content=question)
    conversation.updated_at = datetime.utcnow()
    db.session.add(user_message)
    db.session.commit()
    cache_conversation(conversation.id)
    retrieved = [
        chunk for chunk in search(question)
        if db.session.get(Document, chunk.get("document_id")) is not None
    ]
    citations = [citation_for_chunk(chunk) for chunk in retrieved]
    citations = [citation for citation in citations if citation]
    answer = ask_gemini("\n\n".join(chunk["text"] for chunk in retrieved), question, previous) if retrieved else "I don't have any relevant documents to answer this question yet."
    assistant = Message(conversation_id=conversation.id, role="assistant", content=answer, citations_json=json.dumps(citations))
    conversation.updated_at = datetime.utcnow()
    db.session.add(assistant)
    db.session.commit()
    return assistant, cache_conversation(conversation.id)


@app.get("/")
def home():
    return jsonify({"message": "InternAssist API is running"})


@app.get("/api/auth/csrf")
def csrf_token():
    token = session.get("csrf_token") or secrets.token_urlsafe(32)
    session["csrf_token"] = token
    return jsonify({"csrf_token": token})


@app.post("/api/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    name, email, password = data.get("name", "").strip(), data.get("email", "").strip().lower(), data.get("password", "")
    role = data.get("role", "student")
    if not name or not email or not password:
        return jsonify({"error": "Name, email and password are required."}), 400
    if role not in {"student", "faculty"}:
        return jsonify({"error": "Invalid role."}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with this email already exists."}), 409
    user = User(name=name, email=email, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "Account created successfully.", "user": user.to_dict()}), 201


@app.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    user = User.query.filter_by(email=data.get("email", "").strip().lower()).first()
    if not user or not user.check_password(data.get("password", "")):
        return jsonify({"error": "Invalid email or password."}), 401
    if not user.active:
        session.clear()
        return jsonify({"error": "Your account has been deactivated. Please contact an administrator."}), 403
    session.clear()
    session["user_id"], session["csrf_token"] = user.id, secrets.token_urlsafe(32)
    return jsonify({"message": "Login successful.", "user": user.to_dict(), "csrf_token": session["csrf_token"]})


@app.get("/api/auth/me")
def current_user():
    user = get_logged_in_user()
    return jsonify({"user": user.to_dict()}) if user else (jsonify({"error": "Not authenticated."}), 401)


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully."})


@app.get("/api/protected")
def protected():
    user, error = require_user()
    return error or jsonify({"message": "You can access this protected route.", "user": user.to_dict()})


@app.get("/api/admin/test")
def admin_test():
    user, error = require_user("admin")
    return error or jsonify({"message": "Welcome to the admin area.", "user": user.to_dict()})


@app.get("/api/documents")
def get_documents():
    _, error = require_user()
    if error:
        return error
    return jsonify({"documents": [item.to_dict() for item in Document.query.order_by(Document.uploaded_at.desc()).all()]})


@app.post("/api/documents")
def upload_document():
    user, error = require_user("admin")
    if error:
        return error
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "No file was provided."}), 400
    if not allowed_file(uploaded.filename):
        return jsonify({"error": "File type not supported. Allowed types: PDF, DOCX, PPTX and TXT."}), 400
    original = secure_filename(uploaded.filename)
    if not allowed_file(original):
        return jsonify({"error": "The filename is invalid."}), 400
    extension = original.rsplit(".", 1)[1].lower()
    stored = f"{uuid4()}.{extension}"
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], stored)
    document, indexed = None, False
    try:
        uploaded.save(file_path)
        size = os.path.getsize(file_path)
        if not size:
            raise DocumentExtractionError("The uploaded file is empty.")
        pages = extract_document_pages(file_path, extension)
        chunks = [{"text": text, "page_number": page["page_number"]} for page in pages for text in chunk_text(page["text"]) if text.strip()]
        if not chunks:
            raise DocumentExtractionError("The document does not contain extractable text.")
        document = Document(title=request.form.get("title", "").strip() or Path(original).stem, filename=original, stored_filename=stored, file_type=extension.upper(), file_size=size, status="indexed", uploaded_by_id=user.id)
        db.session.add(document)
        db.session.flush()
        indexed = True
        add_chunks(chunks, document.id)
        db.session.commit()
    except DocumentExtractionError as extraction_error:
        db.session.rollback()
        Path(file_path).unlink(missing_ok=True)
        return jsonify({"error": str(extraction_error)}), 400
    except Exception:
        db.session.rollback()
        if indexed and document and document.id:
            try:
                delete_document_chunks(document.id)
            except Exception:
                app.logger.exception("Unable to roll back vector chunks")
        Path(file_path).unlink(missing_ok=True)
        app.logger.exception("Document upload failed")
        return jsonify({"error": "The document could not be uploaded and indexed."}), 500
    return jsonify({"message": "Document uploaded and indexed successfully.", "document": document.to_dict()}), 201


@app.get("/api/documents/<int:document_id>/download")
def download_document(document_id):
    _, error = require_user()
    if error:
        return error
    document = db.session.get(Document, document_id)
    if not document:
        return jsonify({"error": "Document not found."}), 404
    if not os.path.isfile(os.path.join(app.config["UPLOAD_FOLDER"], document.stored_filename)):
        return jsonify({"error": "The stored document file is missing."}), 404
    return send_from_directory(app.config["UPLOAD_FOLDER"], document.stored_filename, as_attachment=True, download_name=document.filename)


@app.delete("/api/documents/<int:document_id>")
def delete_document(document_id):
    _, error = require_user("admin")
    if error:
        return error
    document = db.session.get(Document, document_id)
    if not document:
        return jsonify({"error": "Document not found."}), 404
    file_path = Path(app.config["UPLOAD_FOLDER"]) / document.stored_filename
    quarantine = file_path.with_suffix(file_path.suffix + ".deleting")
    chunks = []
    committed = False
    try:
        chunks = get_document_chunks(document.id)
        if file_path.exists():
            file_path.replace(quarantine)
        delete_document_chunks(document.id)
        db.session.delete(document)
        db.session.commit()
        committed = True
        quarantine.unlink(missing_ok=True)
    except Exception:
        db.session.rollback()
        if not committed:
            try:
                restore_document_chunks(chunks)
                if quarantine.exists():
                    quarantine.replace(file_path)
            except Exception:
                app.logger.exception("Document deletion rollback failed")
        return jsonify({"error": "The document could not be deleted consistently."}), 500
    return jsonify({"message": "Document and its search index were deleted successfully."})


@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(_error):
    return jsonify({"error": f"File is too large. Maximum size is {app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)} MB."}), 413


@app.get("/api/admin/users")
def get_admin_users():
    _, error = require_user("admin")
    if error:
        return error
    return jsonify({"users": [item.to_dict() for item in User.query.order_by(User.created_at.desc()).all()]})


def set_user_active(user_id, active):
    admin, error = require_user("admin")
    if error:
        return error
    target = db.session.get(User, user_id)
    if not target:
        return jsonify({"error": "User not found."}), 404
    if not active and (target.id == admin.id or target.role == "admin"):
        return jsonify({"error": "Administrator accounts cannot be deactivated."}), 400
    target.active = active
    db.session.commit()
    return jsonify({"message": f"User {'activated' if active else 'deactivated'} successfully.", "user": target.to_dict()})


@app.post("/api/admin/users/<int:user_id>/deactivate")
def deactivate_user(user_id):
    return set_user_active(user_id, False)


@app.post("/api/admin/users/<int:user_id>/activate")
def activate_user(user_id):
    return set_user_active(user_id, True)


@app.get("/api/admin/stats")
def admin_stats():
    _, error = require_user("admin")
    if error:
        return error
    return jsonify({"users": User.query.count(), "documents": Document.query.count(), "conversations": Conversation.query.count()})


@app.get("/api/conversations")
def get_conversations():
    user, error = require_user()
    if error:
        return error
    items = Conversation.query.filter_by(user_id=user.id).order_by(Conversation.updated_at.desc()).all()
    return jsonify({"conversations": [item.to_dict() for item in items]})


@app.post("/api/conversations")
def create_conversation():
    user, error = require_user()
    if error:
        return error
    title = (request.get_json(silent=True) or {}).get("title", "New Conversation").strip() or "New Conversation"
    conversation = Conversation(title=title[:200], user_id=user.id)
    db.session.add(conversation)
    db.session.commit()
    return jsonify({"message": "Conversation created successfully.", "conversation": conversation.to_dict()}), 201


@app.get("/api/conversations/<int:conversation_id>")
def get_conversation(conversation_id):
    user, error = require_user()
    if error:
        return error
    conversation = Conversation.query.filter_by(id=conversation_id, user_id=user.id).first()
    if not conversation:
        return jsonify({"error": "Conversation not found."}), 404
    return jsonify({"conversation": conversation.to_dict(), "messages": cache_conversation(conversation.id)})


@app.post("/api/conversations/<int:conversation_id>/messages")
def add_message(conversation_id):
    user, error = require_user()
    if error:
        return error
    conversation = Conversation.query.filter_by(id=conversation_id, user_id=user.id).first()
    if not conversation:
        return jsonify({"error": "Conversation not found."}), 404
    data = request.get_json(silent=True) or {}
    if data.get("role") != "user":
        return jsonify({"error": "Only user messages may be submitted by clients."}), 400
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "Message content is required."}), 400
    message = Message(conversation_id=conversation.id, role="user", content=content)
    conversation.updated_at = datetime.utcnow()
    db.session.add(message)
    db.session.commit()
    cache_conversation(conversation.id)
    return jsonify({"message": "Message saved successfully.", "data": message.to_dict()}), 201


@app.post("/api/conversations/<int:conversation_id>/ask")
def ask_in_conversation(conversation_id):
    user, error = require_user()
    if error:
        return error
    conversation = Conversation.query.filter_by(id=conversation_id, user_id=user.id).first()
    if not conversation:
        return jsonify({"error": "Conversation not found."}), 404
    question = (request.get_json(silent=True) or {}).get("question", "").strip()
    if not question:
        return jsonify({"error": "Question is required."}), 400
    try:
        assistant, history = answer_conversation(conversation, question)
    except AIConfigurationError as ai_error:
        return jsonify({"error": str(ai_error), "conversation": conversation.to_dict(), "messages": cache_conversation(conversation.id)}), 503
    except AIUpstreamError as ai_error:
        return jsonify({"error": str(ai_error), "conversation": conversation.to_dict(), "messages": cache_conversation(conversation.id)}), 502
    return jsonify({"conversation": conversation.to_dict(), "message": assistant.to_dict(), "messages": history})


@app.delete("/api/conversations/<int:conversation_id>")
def delete_conversation(conversation_id):
    user, error = require_user()
    if error:
        return error
    conversation = Conversation.query.filter_by(id=conversation_id, user_id=user.id).first()
    if not conversation:
        return jsonify({"error": "Conversation not found."}), 404
    db.session.delete(conversation)
    db.session.commit()
    delete_chat_history(conversation_id)
    return jsonify({"message": "Conversation deleted successfully."})


@app.get("/api/admin/conversations")
def get_admin_conversations():
    _, error = require_user("admin")
    if error:
        return error
    items = Conversation.query.join(User).order_by(Conversation.updated_at.desc()).all()
    return jsonify({"conversations": [{**item.to_dict(), "user_name": item.user.name, "user_email": item.user.email, "message_count": Message.query.filter_by(conversation_id=item.id).count()} for item in items]})


@app.post("/api/ask")
def ask():
    _, error = require_user()
    if error:
        return error
    question = (request.get_json(silent=True) or {}).get("question", "").strip()
    if not question:
        return jsonify({"error": "Question is required."}), 400
    retrieved = [
        chunk for chunk in search(question)
        if db.session.get(Document, chunk.get("document_id")) is not None
    ]
    if not retrieved:
        return jsonify({"question": question, "answer": "I don't have any relevant documents to answer this question yet.", "citations": []})
    citations = [citation_for_chunk(chunk) for chunk in retrieved]
    try:
        answer = ask_gemini("\n\n".join(chunk["text"] for chunk in retrieved), question)
    except AIConfigurationError as ai_error:
        return jsonify({"error": str(ai_error)}), 503
    except AIUpstreamError as ai_error:
        return jsonify({"error": str(ai_error)}), 502
    return jsonify({"question": question, "answer": answer, "citations": [item for item in citations if item]})


if __name__ == "__main__":
    app.run(debug=environment == "development", port=int(os.getenv("PORT", "5001")))
