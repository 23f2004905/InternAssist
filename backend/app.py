from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
from flask_session import Session
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from services.document_extractor import extract_pdf_pages
from services.chunking import chunk_text
from services.vectorstore import add_chunks, search
from services.llm import ask_gemini
from uuid import uuid4

import os

from database import db
from models import User, Document, Conversation, Message

from services.redis_service import (
    get_chat_history,
    save_chat_history,
    delete_chat_history
)

load_dotenv()


app = Flask(__name__)

CORS(
    app,
    origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    supports_credentials=True
)


#Flask configuration

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "development-secret-key"
)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///internassist.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


# Document upload 

UPLOAD_FOLDER = os.path.join(
    app.root_path,
    "uploads"
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


app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_USE_SIGNER"] = True

Session(app)

# Database + CORS


db.init_app(app)

def create_default_admin():
    admin_email = "admin@internassist.edu"
    admin_password = "Admin@12345"

    existing_admin = User.query.filter_by(
        email=admin_email
    ).first()

    if existing_admin:
        return

    admin = User(
        name="System Administrator",
        email=admin_email,
        role="admin"
    )

    admin.set_password(admin_password)

    db.session.add(admin)
    db.session.commit()

    print("Default admin account created.")
    print("Email:", admin_email)
    print("Password:", admin_password)


with app.app_context():
    db.create_all()
    create_default_admin()

# Helper function
def get_logged_in_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    return User.query.get(user_id)

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

# Register

@app.route("/api/auth/register", methods=["POST"])
def register():

    data = request.get_json()

    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    role = data.get("role", "student")

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

    db.session.add(user)
    db.session.commit()

    return jsonify({
        "message": "Account created successfully.",
        "user": user.to_dict()
    }), 201



# Login
@app.route("/api/auth/login", methods=["POST"])
def login():

    data = request.get_json()

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

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
    

# Upload document
@app.route("/api/documents", methods=["POST"])
def upload_document():

    user = get_logged_in_user()

    if not user:
        return jsonify({
            "error": "Authentication required."
        }), 401

    if user.role != "admin":
        return jsonify({
            "error": "Admin access required."
        }), 403

    if "file" not in request.files:
        return jsonify({
            "error": "No file was provided."
        }), 400

    file = request.files["file"]

    if not file.filename:
        return jsonify({
            "error": "Please select a file."
        }), 400

    if not allowed_file(file.filename):
        return jsonify({
            "error": "File type not supported. "
                     "Allowed types: PDF, DOCX, PPTX and TXT."
        }), 400

    title = request.form.get(
        "title",
        ""
    ).strip()

    if not title:
        title = os.path.splitext(
            file.filename
        )[0]

    original_filename = secure_filename(
        file.filename
    )

    extension = get_file_extension(
        original_filename
    )

    unique_name = (
        str(uuid4())
        + "."
        + extension
    )

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        unique_name
    )

    file.save(file_path)

    file_size = os.path.getsize(
        file_path
    )

    document = Document(
        title=title,
        filename=original_filename,
        stored_filename=unique_name,
        file_type=extension.upper(),
        file_size=file_size,
        status="uploaded",
        uploaded_by_id=user.id
    )

    db.session.add(document)
    db.session.commit()

    if extension == "pdf":
        pages = extract_pdf_pages(file_path)
        chunks = []

    for page in pages:
        if page["text"].strip():
            page_chunks = chunk_text(page["text"])

            for chunk in page_chunks:
                chunks.append({
                    "text": chunk,
                    "page_number": page["page_number"]
                })

    

    if chunks:
        add_chunks(chunks, document.id)
    return jsonify({
        "message": "Document uploaded successfully.",
        "document": document.to_dict()
    }), 201
    

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

    document = Document.query.get(
        document_id
    )

    if not document:
        return jsonify({
            "error": "Document not found."
        }), 404

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        document.stored_filename,
        as_attachment=False,
        download_name=document.filename
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

    document = Document.query.get(
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

    if os.path.exists(file_path):
        os.remove(file_path)

    db.session.delete(document)

    db.session.commit()

    return jsonify({
        "message": "Document deleted successfully."
    }), 200
    
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
            current_user.to_dict()
            for current_user in users
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

    target_user = User.query.get(user_id)

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

    target_user = User.query.get(user_id)

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

    data = request.get_json() or {}

    title = data.get(
        "title",
        "New Conversation"
    ).strip()

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

    if not history:
        history = [
            message.to_dict()
            for message in conversation.messages
        ]

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

    data = request.get_json() or {}

    role = data.get("role", "").strip()
    content = data.get("content", "").strip()

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

    conversation.updated_at = datetime.utcnow()

    db.session.commit()

    
    history = get_chat_history(conversation.id)

    history.append(message.to_dict())

    save_chat_history(
        conversation.id,
        history
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
@app.route("/api/ask", methods=["POST"])
def ask():

    user = get_logged_in_user()

    if not user:
        return jsonify({
            "error": "Authentication required."
        }), 401

    data = request.get_json() or {}

    question = data.get("question", "").strip()

    if not question:
        return jsonify({
            "error": "Question is required."
        }), 400

    retrieved_chunks = search(question)

    if not retrieved_chunks:
        return jsonify({
            "question": question,
            "answer": "I don't have any relevant documents to answer this question yet.",
            "citations": []
             
        }), 200

    context = "\n\n".join(
        chunk["text"] for chunk in retrieved_chunks
    )

    citations = []
    for chunk in retrieved_chunks:
        document = Document.query.get(chunk["document_id"])

        citations.append({
            "document_id": chunk["document_id"],
            "document_name": document.filename if document else "Unknown document",
            "page_number": chunk["page_number"]
        })  

    answer = ask_gemini(
        context=context,
        question=question
    )

    return jsonify({
        "question": question,
        "answer": answer,
        "citations": citations
    }), 200

# Run application
if __name__ == "__main__":
    app.run(
        debug=True,
        port=5001
    )