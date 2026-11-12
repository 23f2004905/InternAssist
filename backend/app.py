import faulthandler as _faulthandler
import time as _time

_BOOT_STARTED = _time.perf_counter()
# Boot tripwire: if importing the app is still running after 60s, print every
# thread's Python stack to stderr so the Render logs show exactly where it stalled.
_faulthandler.dump_traceback_later(60, exit=False)

from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
from flask_session import Session
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from services.document_extractor import extract_document_pages, iter_document_pages
from services.chunking import chunk_text
import time
import faulthandler
import logging
import sys
from services.vectorstore import (
    add_chunks,
    search,
    delete_document_chunks,
    VectorStoreUnavailable,
    indexed_document_ids
)
from services.llm import ask_gemini
from uuid import uuid4
from datetime import datetime, timezone

import os
import hashlib
import threading

from database import db
from models import User, Document, DocumentFile, Conversation, Message, utcnow_naive

from services.redis_service import (
    get_chat_history,
    save_chat_history,
    delete_chat_history
)


app = Flask(__name__)

# Flask's logger defaults to WARNING under gunicorn, which silently drops
# every app.logger.info() call (including the [ASK] diagnostics).
app.logger.setLevel(logging.INFO)

# ChromaDB is ephemeral on Render. PostgreSQL document_files is the durable
# source of truth; this per-process worker repairs the local vector index once
# after the first request reaches a newly started instance.
_index_recovery_lock = threading.Lock()
_index_recovery_state = {"status": "not_started", "restored": 0, "failed": 0, "skipped": 0, "error": None, "warning": None}
_index_recovery_thread = None
_initial_recovery_done = False
_recovery_rescan_needed = False


def _cleanup_temp_file(path, document_id):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            app.logger.warning("Could not remove temporary recovered file for %s", document_id)


def _recover_chroma_index():
    """Rebuild missing document indexes one document at a time.

    PostgreSQL is authoritative. The Chroma collection is treated as a
    disposable cache and inspected with a per-document metadata filter.
    """
    global _index_recovery_state, _initial_recovery_done, _recovery_rescan_needed
    with app.app_context():
        try:
            while True:
                with _index_recovery_lock:
                    _recovery_rescan_needed = False
                    _index_recovery_state.update(
                        status="running", restored=0, failed=0, skipped=0, error=None, warning=None
                    )
                last_id = 0
                batch_size = 20
                while True:
                    documents = (Document.query
                                 .filter(Document.id > last_id)
                                 .order_by(Document.id.asc())
                                 .limit(batch_size).all())
                    if not documents:
                        break
                    for document in documents:
                        last_id = document.id
                        # Legacy synchronous uploads used status="uploaded" even
                        # after successful Chroma insertion. Preserve those indexes.
                        # New uploads use status="pending", so partial chunks from
                        # an interrupted indexing attempt must never be trusted.
                        has_chunks = indexed_document_ids(document.id)
                        if has_chunks and document.status in ("indexed", "uploaded"):
                            if document.status != "indexed":
                                document.status = "indexed"
                                db.session.commit()
                            continue

                        stored = db.session.get(DocumentFile, document.id)
                        if stored is None:
                            # A pre-migration document has no durable source bytes.
                            # Remove any partial new index and skip only this record;
                            # don't take the entire Ask endpoint offline.
                            if has_chunks:
                                delete_document_chunks(document.id)
                            document.status = "needs_reupload"
                            db.session.commit()
                            _index_recovery_state["skipped"] += 1
                            app.logger.warning(
                                "[INDEX] Document %s has no durable bytes or complete legacy index; re-upload required",
                                document.id,
                            )
                            continue
                        if hashlib.sha256(stored.content).hexdigest() != stored.sha256:
                            if has_chunks:
                                delete_document_chunks(document.id)
                            document.status = "needs_reupload"
                            db.session.commit()
                            _index_recovery_state["skipped"] += 1
                            app.logger.error(
                                "[INDEX] Document %s failed SHA-256 verification; re-upload required",
                                document.id,
                            )
                            continue

                        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
                        path = os.path.join(app.config["UPLOAD_FOLDER"], document.stored_filename)
                        try:
                            with open(path, "wb") as handle:
                                handle.write(stored.content)
                            # Release the ORM reference to the BLOB before embedding.
                            db.session.expunge(stored)
                            extension = document.file_type.lower().lstrip(".")

                            def iter_chunks():
                                for page in iter_document_pages(path, extension):
                                    page_text = page["text"].strip()
                                    if page_text:
                                        for part in chunk_text(page_text):
                                            yield {"text": part, "page_number": page["page_number"]}

                            # Delete partial prior attempts, then stream chunks in batches.
                            delete_document_chunks(document.id)
                            inserted = add_chunks(iter_chunks(), document.id, batch_size=32)
                            if not inserted:
                                document.status = "needs_reupload"
                                db.session.commit()
                                _index_recovery_state["skipped"] += 1
                                app.logger.warning(
                                    "[INDEX] Document %s contains no extractable text; re-upload required",
                                    document.id,
                                )
                                continue
                            document.status = "indexed"
                            db.session.commit()
                            _index_recovery_state["restored"] += 1
                            app.logger.info("[INDEX] Restored document %s (%d chunks)", document.id, inserted)
                        except VectorStoreUnavailable as exc:
                            db.session.rollback()
                            _index_recovery_state["failed"] += 1
                            app.logger.warning(
                                "[INDEX] Vector embedding unavailable for document %s: %s",
                                document.id,
                                exc,
                            )
                        except Exception as exc:
                            db.session.rollback()
                            app.logger.exception(
                                "[INDEX] Failed to extract/index document %s",
                                document.id,
                            )
                            document.status = "needs_reupload"
                            db.session.commit()
                            _index_recovery_state["skipped"] += 1
                        finally:
                            _cleanup_temp_file(path, document.id)
                            db.session.expire_all()

                with _index_recovery_lock:
                    if _recovery_rescan_needed:
                        continue
                    _initial_recovery_done = True
                    if _index_recovery_state["failed"]:
                        _index_recovery_state.update(
                            status="failed", error="The vector index could not be inspected or rebuilt"
                        )
                    elif _index_recovery_state["skipped"]:
                        _index_recovery_state.update(
                            status="ready_with_warnings",
                            error=None,
                            warning="Some legacy or invalid documents require re-upload",
                        )
                    else:
                        _index_recovery_state.update(status="ready", error=None, warning=None)
                    break
        except Exception as exc:
            db.session.rollback()
            app.logger.exception("[INDEX] ChromaDB recovery failed")
            with _index_recovery_lock:
                _initial_recovery_done = True
                _index_recovery_state.update(status="failed", error=type(exc).__name__)
        finally:
            db.session.remove()

def _start_index_recovery(force=False):
    global _index_recovery_thread, _recovery_rescan_needed
    with _index_recovery_lock:
        if force:
            _recovery_rescan_needed = True
        elif _index_recovery_state["status"] in ("running", "ready", "ready_with_warnings"):
            return
        if _index_recovery_thread is not None and _index_recovery_thread.is_alive():
            return
        _index_recovery_thread = threading.Thread(
            target=_recover_chroma_index, name="chroma-index-recovery", daemon=True
        )
        _index_recovery_thread.start()

@app.before_request
def start_index_recovery_on_first_request():
    if app.config.get("TESTING"):
        return
    if (request.endpoint not in (None, "static", "upload_document", "admin_index_status", "retry_index_recovery")
            and _index_recovery_state["status"] == "not_started"):
        _start_index_recovery()


@contextmanager
def _request_watchdog(stage_name, timeout_seconds=45.0):
    """Per-request watchdog that dumps thread tracebacks without clobbering concurrent requests."""
    if timeout_seconds <= 0:
        yield
        return

    def _dump():
        app.logger.warning(
            "[ASK] %s exceeded %.0fs; dumping active Python thread tracebacks",
            stage_name,
            timeout_seconds,
        )
        faulthandler.dump_traceback(file=sys.stderr, all_threads=True)

    timer = threading.Timer(timeout_seconds, _dump)
    timer.daemon = True
    timer.start()
    try:
        yield
    finally:
        timer.cancel()


def peak_rss_mb():
    """Peak resident memory of this process in MB (diagnostics only)."""
    try:
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except Exception:
        return -1.0
    # ru_maxrss is bytes on macOS but kilobytes on Linux.
    return peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024


def environment_snapshot():
    """One-line description of the container's CPU, memory and thread limits."""
    def read(*paths):  # cgroup v2 path first, then the cgroup v1 equivalent
        for path in paths:
            try:
                with open(path) as handle:
                    return handle.read().strip().replace("\n", " | ")
            except OSError:
                continue
        return "n/a"

    threads = "n/a"
    try:
        with open("/proc/self/status") as handle:
            threads = next(
                (line.split()[1] for line in handle if line.startswith("Threads:")),
                "n/a"
            )
    except OSError:
        pass

    try:
        usable_cpus = len(os.sched_getaffinity(0))
    except AttributeError:
        usable_cpus = "n/a"

    return (
        "pid=%s ppid=%s python=%s cpu_count=%s usable_cpus=%s threads=%s "
        "cpu.max=[%s] pids.max=[%s] pids.current=[%s] memory.max=[%s] memory.current=[%s]"
    ) % (
        os.getpid(), os.getppid(), sys.version.split()[0], os.cpu_count(), usable_cpus,
        threads,
        read("/sys/fs/cgroup/cpu.max", "/sys/fs/cgroup/cpu/cpu.cfs_quota_us"),
        read("/sys/fs/cgroup/pids.max", "/sys/fs/cgroup/pids/pids.max"),
        read("/sys/fs/cgroup/pids.current", "/sys/fs/cgroup/pids/pids.current"),
        read("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"),
        read("/sys/fs/cgroup/memory.current", "/sys/fs/cgroup/memory/memory.usage_in_bytes"),
    )


def is_production():
    flask_env = os.getenv("FLASK_ENV", "").strip().lower()
    app_env = os.getenv("ENVIRONMENT", "").strip().lower()
    return flask_env == "production" or app_env == "production"


def _has_module(module_name):
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


def normalize_database_url(url):
    if not url:
        return "sqlite:///internassist.db"
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://") and not _has_module("psycopg2") and _has_module("psycopg"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


WEAK_SECRET_KEYS = {
    "development-secret-key",
    "secret",
    "secret-key",
    "123456",
    "password",
    "admin",
    "changeme",
    "replace-with-a-secure-random-secret-key",
}


def validate_production_config(application):
    if is_production():
        secret = application.config.get("SECRET_KEY", "")
        if not secret or secret in WEAK_SECRET_KEYS or len(secret) < 32:
            raise RuntimeError(
                "SECRET_KEY must be securely configured with at least 32 characters when running in production."
            )


# CORS configuration
cors_origins_env = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"
)
cors_origins = [
    origin.strip()
    for origin in cors_origins_env.split(",")
    if origin.strip()
]

CORS(
    app,
    origins=cors_origins,
    supports_credentials=True
)


# Flask configuration
raw_secret_key = os.getenv("SECRET_KEY")
if is_production():
    if not raw_secret_key or raw_secret_key in WEAK_SECRET_KEYS or len(raw_secret_key) < 32:
        raise RuntimeError(
            "SECRET_KEY must be securely configured with at least 32 characters when running in production."
        )
    app.config["SECRET_KEY"] = raw_secret_key
else:
    app.config["SECRET_KEY"] = raw_secret_key or "development-secret-key"

app.config["SQLALCHEMY_DATABASE_URI"] = normalize_database_url(
    os.getenv("DATABASE_URL", "sqlite:///internassist.db")
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "300"))
}


# Document upload
UPLOAD_FOLDER = os.getenv(
    "UPLOAD_FOLDER",
    os.path.join(app.root_path, "uploads")
)

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    "pdf",
    "docx",
    "pptx",
    "txt"
}

# Session configuration
session_type = os.getenv("SESSION_TYPE", "filesystem").strip().lower()
app.config["SESSION_TYPE"] = session_type
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_USE_SIGNER"] = True

if session_type == "filesystem":
    session_file_dir = os.getenv(
        "SESSION_FILE_DIR",
        os.path.join(app.root_path, "flask_session")
    )
    os.makedirs(session_file_dir, exist_ok=True)
    app.config["SESSION_FILE_DIR"] = session_file_dir
elif session_type == "redis":
    from services.redis_service import redis_client
    app.config["SESSION_REDIS"] = redis_client
elif session_type == "sqlalchemy":
    app.config["SESSION_SQLALCHEMY"] = db


app.config["SESSION_COOKIE_HTTPONLY"] = True

samesite_default = "None" if is_production() else "Lax"
samesite_val = os.getenv("SESSION_COOKIE_SAMESITE", samesite_default)

app.config["SESSION_COOKIE_SAMESITE"] = samesite_val

secure_default = "true" if is_production() else "false"
secure_val = os.getenv("SESSION_COOKIE_SECURE", secure_default)

app.config["SESSION_COOKIE_SECURE"] = (
    True if samesite_val.lower() == "none"
    else secure_val.lower() in ("true", "1")
)
Session(app)

# Database + CORS
db.init_app(app)


def create_default_admin():
    admin_email = os.getenv("ADMIN_EMAIL") or os.getenv("DEFAULT_ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD") or os.getenv("DEFAULT_ADMIN_PASSWORD")
    admin_name = os.getenv("ADMIN_NAME") or os.getenv("DEFAULT_ADMIN_NAME", "System Administrator")

    if not admin_email or not admin_password:
        app.logger.info("Admin credentials not configured via environment variables; skipping admin creation.")
        return

    existing_admin = User.query.filter_by(
        email=admin_email
    ).first()

    if existing_admin:
        return

    admin = User(
        name=admin_name,
        email=admin_email,
        role="admin"
    )

    admin.set_password(admin_password)

    try:
        db.session.add(admin)
        db.session.commit()
        app.logger.info("Administrator account created for %s.", admin_email)
    except Exception:
        db.session.rollback()
        app.logger.exception("Failed to create default administrator account.")



# Helper function
def get_logged_in_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    return db.session.get(User, user_id)

def allowed_file(filename):
    if not filename:
        return False

    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()

    return extension in ALLOWED_EXTENSIONS


def get_file_extension(filename):
    return filename.rsplit(".", 1)[1].lower()

# Home
@app.route("/")
def home():
    return jsonify({
        "message": "InternAssist API is running"
    })

def _json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _str_field(data, key, default=""):
    value = data.get(key, default)
    if value is None:
        return default
    return value if isinstance(value, str) else str(value)


# Register

@app.route("/api/auth/register", methods=["POST"])
def register():

    data = _json_body()

    name = _str_field(data, "name").strip()
    email = _str_field(data, "email").strip().lower()
    password = _str_field(data, "password")
    role = _str_field(data, "role", "student").strip() or "student"

    if not name or not email or not password:
        return jsonify({
            "error": "Name, email and password are required."
        }), 400

    if role not in ["student", "faculty"]:
        return jsonify({
            "error": "Invalid role."
        }), 400

    existing_user = User.query.filter_by(
        email=email
    ).first()

    if existing_user:
        return jsonify({
            "error": "An account with this email already exists."
        }), 409

    user = User(
        name=name,
        email=email,
        role=role
    )

    user.set_password(password)

    try:
        db.session.add(user)
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception("Failed to register user.")
        return jsonify({
            "error": "Failed to create account. Please try again."
        }), 500

    return jsonify({
        "message": "Account created successfully.",
        "user": user.to_dict()
    }), 201



# Login
@app.route("/api/auth/login", methods=["POST"])
def login():

    data = _json_body()

    email = _str_field(data, "email").strip().lower()
    password = _str_field(data, "password")

    if not email or not password:
        return jsonify({
            "error": "Email and password are required."
        }), 400

    user = User.query.filter_by(
        email=email
    ).first()

    if not user:
        return jsonify({
            "error": "Invalid email or password."
        }), 401

    if not user.active:
        return jsonify({
        "error": "Your account has been deactivated. Please contact an administrator."
    }), 403

    if not user.check_password(password):
        return jsonify({
            "error": "Invalid email or password."
        }), 401



    session["user_id"] = user.id

    return jsonify({
        "message": "Login successful.",
        "user": user.to_dict()
    }), 200




@app.route("/api/auth/me", methods=["GET"])
def current_user():

    user = get_logged_in_user()

    if not user:
        return jsonify({
            "error": "Not authenticated."
        }), 401

    return jsonify({
        "user": user.to_dict()
    }), 200


# Logout
@app.route("/api/auth/logout", methods=["POST"])
def logout():

    session.clear()

    return jsonify({
        "message": "Logged out successfully."
    }), 200


@app.route("/api/protected", methods=["GET"])
def protected():

    user = get_logged_in_user()

    if not user:
        return jsonify({
            "error": "Authentication required."
        }), 401

    return jsonify({
        "message": "You can access this protected route.",
        "user": user.to_dict()
    })


@app.route("/api/admin/test", methods=["GET"])
def admin_test():

    user = get_logged_in_user()

    if not user:
        return jsonify({
            "error": "Authentication required."
        }), 401

    if user.role != "admin":
        return jsonify({
            "error": "Admin access required."
        }), 403

    return jsonify({
        "message": "Welcome to the admin area.",
        "user": user.to_dict()
    })


# Get all documents
@app.route("/api/documents", methods=["GET"])
def get_documents():

    user = get_logged_in_user()

    if not user:
        return jsonify({
            "error": "Authentication required."
        }), 401

    documents = Document.query.order_by(
        Document.uploaded_at.desc()
    ).all()

    return jsonify({
        "documents": [
            document.to_dict()
            for document in documents
        ]
    }), 200




# Upload: persist the original bytes first; indexing runs in the recovery worker.
@app.route("/api/documents", methods=["POST"])
def upload_document():
    user = get_logged_in_user()
    if not user:
        return jsonify({"error": "Authentication required."}), 401
    if user.role != "admin":
        return jsonify({"error": "Admin access required."}), 403
    if "file" not in request.files:
        return jsonify({"error": "No file was provided."}), 400

    uploaded = request.files["file"]
    if not uploaded.filename:
        return jsonify({"error": "Please select a file."}), 400
    if not allowed_file(uploaded.filename):
        return jsonify({"error": "File type not supported. Allowed types: PDF, DOCX, PPTX and TXT."}), 400

    extension = get_file_extension(uploaded.filename)
    original_filename = secure_filename(uploaded.filename)
    if not original_filename or "." not in original_filename:
        base = original_filename if original_filename and original_filename != extension else "document"
        original_filename = f"{base}.{extension}"
    # Read at most MAX_CONTENT_LENGTH + 1 to enforce the limit without an
    # unbounded read. Flask also enforces MAX_CONTENT_LENGTH at request level.
    content = uploaded.stream.read(app.config["MAX_CONTENT_LENGTH"] + 1)
    if not content:
        return jsonify({"error": "The uploaded file is empty."}), 400
    if len(content) > app.config["MAX_CONTENT_LENGTH"]:
        return jsonify({"error": "File is too large. Maximum size is 20 MB."}), 413

    title = request.form.get("title", "").strip() or os.path.splitext(original_filename)[0]
    unique_name = f"{uuid4()}.{extension}"
    document = Document(
        title=title, filename=original_filename, stored_filename=unique_name,
        file_type=extension.upper(), file_size=len(content), status="pending",
        uploaded_by_id=user.id
    )
    try:
        db.session.add(document)
        db.session.flush()
        db.session.add(DocumentFile(
            document_id=document.id, content=content,
            sha256=hashlib.sha256(content).hexdigest()
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception("Could not persist uploaded document")
        return jsonify({"error": "Document could not be stored. Please try again."}), 500

    # Schedule recovery/indexing after durable commit. A process restart is safe:
    # the pending document and original bytes remain in PostgreSQL.
    if not app.config.get("TESTING"):
        _start_index_recovery(force=True)
    return jsonify({
        "message": "Document uploaded and saved. Indexing is running in the background.",
        "document": document.to_dict(),
        "indexing_pending": True
    }), 202


# Download document
@app.route(
    "/api/documents/<int:document_id>/download",
    methods=["GET"]
)
def download_document(document_id):

    user = get_logged_in_user()

    if not user:
        return jsonify({
            "error": "Authentication required."
        }), 401

    document = db.session.get(
        Document,
        document_id
    )

    if not document:
        return jsonify({
            "error": "Document not found."
        }), 404

    file_path = os.path.join(app.config["UPLOAD_FOLDER"], document.stored_filename)
    if not os.path.isfile(file_path):
        stored = db.session.get(DocumentFile, document.id)
        if stored is None:
            return jsonify({"error": "Stored document bytes are unavailable."}), 410
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        if hashlib.sha256(stored.content).hexdigest() != stored.sha256:
            app.logger.error("Stored document %s failed SHA-256 verification", document.id)
            return jsonify({"error": "Stored document failed integrity verification."}), 500
        with open(file_path, "wb") as handle:
            handle.write(stored.content)
    return send_from_directory(
        app.config["UPLOAD_FOLDER"], document.stored_filename,
        as_attachment=False, download_name=document.filename
    )




# Delete document
@app.route(
    "/api/documents/<int:document_id>",
    methods=["DELETE"]
)
def delete_document(document_id):

    user = get_logged_in_user()

    if not user:
        return jsonify({
            "error": "Authentication required."
        }), 401

    if user.role != "admin":
        return jsonify({
            "error": "Admin access required."
        }), 403

    document = db.session.get(
        Document,
        document_id
    )

    if not document:
        return jsonify({
            "error": "Document not found."
        }), 404

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        document.stored_filename
    )

    try:
        delete_document_chunks(document_id)

        if os.path.exists(file_path):
            os.remove(file_path)

        db.session.delete(document)
        db.session.commit()

    except Exception:
        db.session.rollback()
        app.logger.exception("Document deletion failed.")
        return jsonify({
            "error": "Document deletion failed."
        }), 500

    return jsonify({
        "message": "Document deleted successfully."
    }), 200

@app.route("/api/admin/index-status", methods=["GET"])
def admin_index_status():
    user = get_logged_in_user()
    if not user:
        return jsonify({"error": "Authentication required."}), 401
    if user.role != "admin":
        return jsonify({"error": "Admin access required."}), 403
    if _index_recovery_state["status"] == "not_started":
        _start_index_recovery()
    return jsonify(dict(_index_recovery_state)), 200

@app.route("/api/admin/index-recovery/retry", methods=["POST"])
def retry_index_recovery():
    global _index_recovery_thread
    user = get_logged_in_user()
    if not user:
        return jsonify({"error": "Authentication required."}), 401
    if user.role != "admin":
        return jsonify({"error": "Admin access required."}), 403
    with _index_recovery_lock:
        if _index_recovery_thread is not None and _index_recovery_thread.is_alive():
            return jsonify({"status": "running"}), 202
        _index_recovery_state.update(status="not_started", error=None)
    _start_index_recovery()
    return jsonify({"status": "recovery_started"}), 202

@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(error):

    return jsonify({
        "error": "File is too large. Maximum size is 20 MB."
    }), 413



@app.route("/api/admin/users", methods=["GET"])
def get_admin_users():

    user = get_logged_in_user()

    if not user:
        return jsonify({
            "error": "Authentication required."
        }), 401

    if user.role != "admin":
        return jsonify({
            "error": "Admin access required."
        }), 403

    users = User.query.order_by(
        User.created_at.desc()
    ).all()

    return jsonify({
        "users": [
            u.to_dict()
            for u in users
        ]
    }), 200


# Deactivate user


@app.route(
    "/api/admin/users/<int:user_id>/deactivate",
    methods=["POST"]
)
def deactivate_user(user_id):

    admin = get_logged_in_user()

    if not admin:
        return jsonify({
            "error": "Authentication required."
        }), 401

    if admin.role != "admin":
        return jsonify({
            "error": "Admin access required."
        }), 403

    target_user = db.session.get(User, user_id)

    if not target_user:
        return jsonify({
            "error": "User not found."
        }), 404

    if target_user.id == admin.id:
        return jsonify({
            "error": "You cannot deactivate your own account."
        }), 400

    if target_user.role == "admin":
        return jsonify({
            "error": "Administrator accounts cannot be deactivated."
        }), 400

    target_user.active = False

    db.session.commit()

    return jsonify({
        "message": "User deactivated successfully.",
        "user": target_user.to_dict()
    }), 200




# Activate user
@app.route(
    "/api/admin/users/<int:user_id>/activate",
    methods=["POST"]
)
def activate_user(user_id):

    admin = get_logged_in_user()

    if not admin:
        return jsonify({
            "error": "Authentication required."
        }), 401

    if admin.role != "admin":
        return jsonify({
            "error": "Admin access required."
        }), 403

    target_user = db.session.get(User, user_id)

    if not target_user:
        return jsonify({
            "error": "User not found."
        }), 404

    target_user.active = True

    db.session.commit()

    return jsonify({
        "message": "User activated successfully.",
        "user": target_user.to_dict()
    }), 200




# Admin dashboard statistics
@app.route("/api/admin/stats", methods=["GET"])
def admin_stats():

    user = get_logged_in_user()

    if not user:
        return jsonify({
            "error": "Authentication required."
        }), 401

    if user.role != "admin":
        return jsonify({
            "error": "Admin access required."
        }), 403

    user_count = User.query.count()

    document_count = Document.query.count()

    conversation_count = Conversation.query.count()

    return jsonify({
        "users": user_count,
        "documents": document_count,
        "conversations": conversation_count
    }), 200




# user's conversations
@app.route(
    "/api/conversations",
    methods=["GET"]
)
def get_conversations():

    user = get_logged_in_user()

    if not user:
        return jsonify({
            "error": "Authentication required."
        }), 401

    conversations = Conversation.query.filter_by(
        user_id=user.id
    ).order_by(
        Conversation.updated_at.desc()
    ).all()

    return jsonify({
        "conversations": [
            conversation.to_dict()
            for conversation in conversations
        ]
    }), 200




# Create conversation
@app.route(
    "/api/conversations",
    methods=["POST"]
)
def create_conversation():

    user = get_logged_in_user()

    if not user:
        return jsonify({
            "error": "Authentication required."
        }), 401

    data = _json_body()

    title = _str_field(data, "title", "New Conversation").strip()

    if not title:
        title = "New Conversation"

    conversation = Conversation(
        title=title,
        user_id=user.id
    )

    db.session.add(conversation)
    db.session.commit()

    return jsonify({
        "message": "Conversation created successfully.",
        "conversation": conversation.to_dict()
    }), 201




# Get one conversation
@app.route(
    "/api/conversations/<int:conversation_id>",
    methods=["GET"]
)
def get_conversation(conversation_id):

    user = get_logged_in_user()

    if not user:
        return jsonify({
            "error": "Authentication required."
        }), 401

    conversation = Conversation.query.filter_by(
        id=conversation_id,
        user_id=user.id
    ).first()

    if not conversation:
        return jsonify({
            "error": "Conversation not found."
        }), 404

    history = get_chat_history(conversation.id)

    if history is None or not history or len(history) != len(conversation.messages):
        history = [
            message.to_dict()
            for message in conversation.messages
        ]

        if history:
            save_chat_history(
                conversation.id,
                history
            )

    return jsonify({
        "conversation": conversation.to_dict(),
        "messages": history
    }), 200




# Add message to conversation
@app.route(
    "/api/conversations/<int:conversation_id>/messages",
    methods=["POST"]
)
def add_message(conversation_id):

    user = get_logged_in_user()

    if not user:
        return jsonify({
            "error": "Authentication required."
        }), 401

    conversation = Conversation.query.filter_by(
        id=conversation_id,
        user_id=user.id
    ).first()

    if not conversation:
        return jsonify({
            "error": "Conversation not found."
        }), 404

    data = _json_body()

    role = _str_field(data, "role").strip()
    content = _str_field(data, "content").strip()

    if role not in ["user", "assistant"]:
        return jsonify({
            "error": "Invalid message role."
        }), 400

    if not content:
        return jsonify({
            "error": "Message content is required."
        }), 400
    message = Message(
        conversation_id=conversation.id,
        role=role,
        content=content
    )

    db.session.add(message)

    conversation.updated_at = utcnow_naive()

    db.session.commit()



    history = get_chat_history(conversation.id)

    if history is not None:
        if history and len(history) == len(conversation.messages) - 1:
            history.append(message.to_dict())
            save_chat_history(
                conversation.id,
                history
            )
        else:
            full_history = [
                m.to_dict()
                for m in conversation.messages
            ]
            save_chat_history(
                conversation.id,
                full_history
            )
    else:
        app.logger.warning(
            "Redis chat cache was not updated for conversation %s due to Redis unavailability.",
            conversation.id
        )

    return jsonify({
        "message": "Message saved successfully.",
        "data": message.to_dict()
    }), 201



# Delete conversation
@app.route(
    "/api/conversations/<int:conversation_id>",
    methods=["DELETE"]
)
def delete_conversation(conversation_id):

    user = get_logged_in_user()

    if not user:
        return jsonify({
            "error": "Authentication required."
        }), 401

    conversation = Conversation.query.filter_by(
        id=conversation_id,
        user_id=user.id
    ).first()

    if not conversation:
        return jsonify({
            "error": "Conversation not found."
        }), 404

    db.session.delete(conversation)
    db.session.commit()
    try:
        delete_chat_history(conversation.id)
    except Exception:
        app.logger.exception(
            "Failed to delete chat history from Redis for conversation %s.",
            conversation.id
        )

    return jsonify({
        "message": "Conversation deleted successfully."
    }), 200




# Admin: all conversations
@app.route(
    "/api/admin/conversations",
    methods=["GET"]
)
def get_admin_conversations():

    user = get_logged_in_user()

    if not user:
        return jsonify({
            "error": "Authentication required."
        }), 401

    if user.role != "admin":
        return jsonify({
            "error": "Admin access required."
        }), 403

    conversations = Conversation.query.join(
        User
    ).order_by(
        Conversation.updated_at.desc()
    ).all()

    result = []

    for conversation in conversations:

        result.append({
            "id": conversation.id,
            "title": conversation.title,
            "user_id": conversation.user_id,
            "user_name": conversation.user.name,
            "user_email": conversation.user.email,
            "created_at": (
                conversation.created_at.isoformat()
                if conversation.created_at
                else None
            ),
            "updated_at": (
                conversation.updated_at.isoformat()
                if conversation.updated_at
                else None
            )
        })

    return jsonify({
        "conversations": result
    }), 200



# Ask assistant (RAG + Gemini)

def _coerce_doc_id(doc_id):
    if isinstance(doc_id, int) and not isinstance(doc_id, bool):
        return doc_id
    if isinstance(doc_id, str) and doc_id.strip().isdigit():
        return int(doc_id.strip())
    return None


_FOLLOWUP_MARKERS = {
    "it", "its", "this", "that", "these", "those",
    "they", "them", "their", "same", "above", "previous",
    "more", "else", "again",
}

_IGNORED_ASSISTANT_HISTORY = {
    "gemini is temporarily unavailable. please try again.",
    "i'm sorry, i was unable to retrieve an answer at this time. please try again.",
    "i don't have any relevant documents to answer this question yet.",
}


def _build_retrieval_query(question, history):
    """Expand short or referential follow-up queries using the previous user question."""
    if not history:
        return question
    words = [w.strip(".,?!:;\"'()[]{}").lower() for w in question.split()]
    has_reference = any(word in _FOLLOWUP_MARKERS for word in words)
    if len(words) > 7 and not (len(words) <= 16 and has_reference):
        return question
    for item in reversed(history):
        if item.get("role") == "user" and item.get("content"):
            prev = item["content"].strip()
            if prev and prev.lower() != question.strip().lower():
                return f"{prev} {question}"
    return question


@app.route("/api/ask", methods=["POST"])
def ask():
    request_started = time.perf_counter()

    user = get_logged_in_user()

    if not user:
        return jsonify({
            "error": "Authentication required."
        }), 401

    if not app.config.get("TESTING"):
        with _index_recovery_lock:
            recovery_status = _index_recovery_state["status"]
            initial_done = _initial_recovery_done
        if not initial_done and recovery_status in ("not_started", "running"):
            _start_index_recovery()
            return jsonify({"status": "index_rebuilding",
                            "message": "The document index is being restored. Please retry shortly."}), 503, {"Retry-After": "5"}
        if not initial_done and recovery_status == "failed":
            return jsonify({"status": "index_recovery_failed",
                            "error": "The document index could not be fully restored. Please contact an administrator."}), 503

    data = _json_body()
    question = _str_field(data, "question").strip()

    if not question:
        return jsonify({
            "error": "Question is required."
        }), 400

    history = []
    conv_id_raw = data.get("conversation_id")
    if conv_id_raw is not None:
        conv_id = _coerce_doc_id(conv_id_raw)
        if conv_id is not None:
            conversation = Conversation.query.filter_by(
                id=conv_id,
                user_id=user.id
            ).first()
            if conversation:
                msgs = [
                    {"role": m.role, "content": m.content}
                    for m in conversation.messages
                    if not (
                        m.role == "assistant"
                        and (m.content or "").strip().lower() in _IGNORED_ASSISTANT_HISTORY
                    )
                ]
                # Exclude the just-saved copy of this same user question if present at the tail.
                if msgs and msgs[-1]["role"] == "user" and msgs[-1]["content"].strip() == question:
                    msgs = msgs[:-1]
                history = msgs[-6:]

    retrieval_query = _build_retrieval_query(question, history)

    # 1. Vector retrieval
    app.logger.info(
        "[ASK] Request started - beginning vector retrieval (peak RSS %.0f MB)",
        peak_rss_mb()
    )
    retrieval_started = time.perf_counter()

    retrieval_error = None
    with _request_watchdog("Vector retrieval", timeout_seconds=45.0):
        try:
            retrieved_chunks = search(retrieval_query)
        except VectorStoreUnavailable as exc:
            app.logger.warning("[ASK] Vector search unavailable: %s", type(exc).__name__)
            retrieved_chunks = []
            retrieval_error = exc
        except Exception as exc:
            app.logger.exception("[ASK] Unexpected vector search failure")
            retrieved_chunks = []
            retrieval_error = exc

    app.logger.info(
        "[ASK] Vector retrieval completed in %.2fs (%d chunks, peak RSS %.0f MB)",
        time.perf_counter() - retrieval_started,
        len(retrieved_chunks),
        peak_rss_mb()
    )

    if retrieval_error is not None:
        return jsonify({"status": "retrieval_failed",
                        "error": "Document search is temporarily unavailable. Please retry shortly."}), 503

    if not retrieved_chunks:
        app.logger.info(
            "[ASK] Total request completed in %.2fs",
            time.perf_counter() - request_started
        )
        return jsonify({
            "question": question,
            "answer": "I don't have any relevant documents to answer this question yet.",
            "citations": [],
            "status": "no_relevant_chunks"
        }), 200

    # 2. PostgreSQL citation lookup (done before prompt assembly so context carries source headers)
    citation_started = time.perf_counter()

    citations = []
    seen_citations = set()
    doc_names = {}
    context_blocks = []

    for chunk in retrieved_chunks:
        doc_id = chunk.get("document_id")
        page_num = chunk.get("page_number")
        citation_key = (doc_id, page_num)

        if doc_id not in doc_names:
            coerced_id = _coerce_doc_id(doc_id)
            document = None
            if coerced_id is not None:
                try:
                    document = db.session.get(Document, coerced_id)
                except Exception:
                    db.session.rollback()
                    app.logger.exception("[ASK] Citation lookup failed")
                    document = None
            doc_names[doc_id] = document.filename if document else "Unknown document"

        doc_name = doc_names[doc_id]
        source_label = f"{doc_name}, Page {page_num}" if page_num else doc_name
        context_blocks.append(f"[Source: {source_label}]\n{chunk['text']}")

        if citation_key in seen_citations:
            continue

        seen_citations.add(citation_key)
        citations.append({
            "document_id": doc_id,
            "document_name": doc_name,
            "page_number": page_num
        })

    context = "\n\n".join(context_blocks)

    app.logger.info(
        "[ASK] Citation lookup completed in %.2fs (%d citations)",
        time.perf_counter() - citation_started,
        len(citations)
    )

    # 3. Gemini generation
    gemini_started = time.perf_counter()

    with _request_watchdog("Gemini generation", timeout_seconds=45.0):
        try:
            if history:
                answer = ask_gemini(
                    context=context,
                    question=question,
                    history=history,
                )
            else:
                answer = ask_gemini(
                    context=context,
                    question=question,
                )
        except Exception:
            app.logger.exception("[ASK] Gemini generation failed")
            answer = "Gemini is temporarily unavailable. Please try again."

    app.logger.info(
        "[ASK] Gemini generation completed in %.2fs",
        time.perf_counter() - gemini_started
    )

    # 4. Total request duration
    app.logger.info(
        "[ASK] Total request completed in %.2fs",
        time.perf_counter() - request_started
    )

    return jsonify({
        "question": question,
        "answer": answer,
        "citations": citations
    }), 200

# Initialize database tables
with app.app_context():
    _db_started = _time.perf_counter()
    db.create_all()
    app.logger.info("[BOOT] db.create_all completed in %.2fs", _time.perf_counter() - _db_started)
    create_default_admin()

_faulthandler.cancel_dump_traceback_later()
app.logger.info(
    "[BOOT] app import completed in %.2fs (peak RSS %.0f MB)",
    _time.perf_counter() - _BOOT_STARTED, peak_rss_mb()
)
app.logger.info("[ENV] %s", environment_snapshot())


# Run application locally
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    app.run(debug=(not is_production()), port=port)