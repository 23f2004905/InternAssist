import app as app_module
from app import app
from database import db
from models import Conversation, Document, Message
from conftest import create_user, login


def test_context_order_citations_and_cross_user_denial(client, monkeypatch):
    first_id = create_user()
    _, token = login(client)
    with app.app_context():
        document = Document(title="Policy", filename="policy.pdf", stored_filename="policy.pdf", file_type="PDF", file_size=10, uploaded_by_id=first_id)
        db.session.add(document)
        db.session.commit()
        document_id = document.id
    response = client.post("/api/conversations", json={"title": "Policy"}, headers={"X-CSRF-Token": token})
    conversation_id = response.get_json()["conversation"]["id"]
    monkeypatch.setattr(app_module, "search", lambda _question: [
        {"text": "context", "document_id": document_id, "page_number": 2},
        {"text": "more context", "document_id": document_id, "page_number": 2},
    ])
    histories = []
    monkeypatch.setattr(app_module, "ask_gemini", lambda context, question, history=None: histories.append(history) or "answer")
    assert client.post(f"/api/conversations/{conversation_id}/ask", json={"question": "first"}, headers={"X-CSRF-Token": token}).status_code == 200
    response = client.post(f"/api/conversations/{conversation_id}/ask", json={"question": "follow up"}, headers={"X-CSRF-Token": token})
    assert [item["role"] for item in response.get_json()["messages"]] == ["user", "assistant", "user", "assistant"]
    assert histories[1][0]["content"] == "first"
    reloaded = client.get(f"/api/conversations/{conversation_id}").get_json()["messages"]
    assert reloaded[-1]["citations"][0]["page_number"] == 2
    assert len(reloaded[-1]["citations"]) == 1

    create_user("other@example.com")
    _, _ = login(client, "other@example.com")
    assert client.get(f"/api/conversations/{conversation_id}").status_code == 404


def test_ai_failure_keeps_user_message_only(client, monkeypatch):
    user_id = create_user()
    _, token = login(client)
    conversation_id = client.post("/api/conversations", json={}, headers={"X-CSRF-Token": token}).get_json()["conversation"]["id"]
    with app.app_context():
        document = Document(title="Policy", filename="policy.pdf", stored_filename="policy.pdf", file_type="PDF", file_size=10, uploaded_by_id=user_id)
        db.session.add(document)
        db.session.commit()
        document_id = document.id
    monkeypatch.setattr(app_module, "search", lambda _: [{"text": "context", "document_id": document_id, "page_number": 1}])
    monkeypatch.setattr(app_module, "ask_gemini", lambda *args, **kwargs: (_ for _ in ()).throw(app_module.AIUpstreamError("failed")))
    response = client.post(f"/api/conversations/{conversation_id}/ask", json={"question": "question"}, headers={"X-CSRF-Token": token})
    assert response.status_code == 502
    with app.app_context():
        messages = Message.query.filter_by(conversation_id=conversation_id).all()
        assert [(item.role, item.content) for item in messages] == [("user", "question")]


def test_orphaned_vector_chunks_are_never_used(client, monkeypatch):
    create_user()
    _, token = login(client)
    conversation_id = client.post("/api/conversations", json={}, headers={"X-CSRF-Token": token}).get_json()["conversation"]["id"]
    monkeypatch.setattr(app_module, "search", lambda _: [{"text": "deleted content", "document_id": 9999, "page_number": 1}])
    monkeypatch.setattr(app_module, "ask_gemini", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("deleted content reached the LLM")))
    response = client.post(f"/api/conversations/{conversation_id}/ask", json={"question": "question"}, headers={"X-CSRF-Token": token})
    assert response.status_code == 200
    assert response.get_json()["message"]["citations"] == []


def test_conversation_routes_reject_malformed_text_fields(client):
    create_user()
    _, token = login(client)
    created = client.post(
        "/api/conversations",
        json={"title": {"unexpected": True}},
        headers={"X-CSRF-Token": token},
    )
    assert created.status_code == 201
    conversation_id = created.get_json()["conversation"]["id"]
    assert created.get_json()["conversation"]["title"] == "New Conversation"
    message = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"role": "user", "content": ["not text"]},
        headers={"X-CSRF-Token": token},
    )
    assert message.status_code == 400
    question = client.post(
        f"/api/conversations/{conversation_id}/ask",
        json={"question": {"unexpected": True}},
        headers={"X-CSRF-Token": token},
    )
    assert question.status_code == 400
