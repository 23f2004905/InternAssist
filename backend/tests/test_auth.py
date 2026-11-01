from models import User


def test_password_is_hashed():
    user = User(name="Test User", email="test@example.com")
    user.set_password("TestPassword123!")

    assert user.password_hash != "TestPassword123!"
    assert user.password_hash is not None


def test_correct_password_is_accepted():
    user = User(name="Test User", email="test@example.com")
    user.set_password("TestPassword123!")

    assert user.check_password("TestPassword123!") is True


def test_incorrect_password_is_rejected():
    user = User(name="Test User", email="test@example.com")
    user.set_password("TestPassword123!")

    assert user.check_password("WrongPassword123!") is False


def test_user_dict_does_not_expose_password():
    user = User(name="Test User", email="test@example.com")
    user.set_password("TestPassword123!")

    user_data = user.to_dict()

    assert "password_hash" not in user_data
    assert "password" not in user_data


def register_test_user(client):
    return client.post(
        "/api/auth/register",
        json={
            "name": "Test User",
            "email": "test@example.com",
            "password": "TestPassword123!",
            "role": "student"
        }
    )


def test_register_user(client):
    response = register_test_user(client)

    assert response.status_code == 201
    data = response.get_json()
    assert data["user"]["email"] == "test@example.com"
    assert "password_hash" not in data["user"]


def test_duplicate_registration(client):
    register_test_user(client)
    response = register_test_user(client)

    assert response.status_code == 409


def test_admin_role_cannot_be_self_registered(client):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Test Admin",
            "email": "admin-test@example.com",
            "password": "TestPassword123!",
            "role": "admin"
        }
    )

    assert response.status_code == 400


def test_login_and_current_user(client):
    register_test_user(client)

    response = client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "TestPassword123!"
        }
    )

    assert response.status_code == 200

    me_response = client.get("/api/auth/me")
    assert me_response.status_code == 200
    assert me_response.get_json()["user"]["email"] == "test@example.com"


def test_login_with_wrong_password(client):
    register_test_user(client)

    response = client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "WrongPassword123!"
        }
    )

    assert response.status_code == 401


def test_logout(client):
    register_test_user(client)

    client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "TestPassword123!"
        }
    )

    response = client.post("/api/auth/logout")
    assert response.status_code == 200

    me_response = client.get("/api/auth/me")
    assert me_response.status_code == 401


def test_protected_route(client):
    response = client.get("/api/protected")
    assert response.status_code == 401

    register_test_user(client)

    client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "TestPassword123!"
        }
    )

    response = client.get("/api/protected")
    assert response.status_code == 200


def register_test_admin(client):
    from models import User
    from app import db

    admin = User(
        name="Test Admin",
        email="admin-test@example.com",
        role="admin"
    )
    admin.set_password("AdminPassword123!")
    db.session.add(admin)
    db.session.commit()

    return client.post(
        "/api/auth/login",
        json={
            "email": "admin-test@example.com",
            "password": "AdminPassword123!"
        }
    )


def test_document_upload_requires_login(client):
    from io import BytesIO

    response = client.post(
        "/api/documents",
        data={"file": (BytesIO(b"Test document content"), "test.txt")},
        content_type="multipart/form-data"
    )
    assert response.status_code == 401


def test_student_cannot_upload_document(client):
    from io import BytesIO

    register_test_user(client)
    client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "TestPassword123!"
        }
    )

    response = client.post(
        "/api/documents",
        data={"file": (BytesIO(b"Test document content"), "test.txt")},
        content_type="multipart/form-data"
    )
    assert response.status_code == 403


def test_unsupported_document_type(client):
    from io import BytesIO

    register_test_admin(client)

    response = client.post(
        "/api/documents",
        data={"file": (BytesIO(b"Test content"), "test.exe")},
        content_type="multipart/form-data"
    )
    assert response.status_code == 400


def test_admin_can_upload_document(client, monkeypatch):
    from io import BytesIO
    import app as app_module

    register_test_admin(client)
    monkeypatch.setattr(app_module, "add_chunks", lambda chunks, document_id: None)

    response = client.post(
        "/api/documents",
        data={"file": (BytesIO(b"InternAssist test document content"), "test.txt")},
        content_type="multipart/form-data"
    )

    assert response.status_code == 201
    assert response.get_json()["document"]["filename"] == "test.txt"


def test_admin_can_download_document(client, monkeypatch):
    from io import BytesIO

    import app as app_module
    from models import Document

    register_test_admin(client)
    monkeypatch.setattr(app_module, "add_chunks", lambda chunks, document_id: None)

    upload = client.post(
        "/api/documents",
        data={"file": (BytesIO(b"Download test content"), "download.txt")},
        content_type="multipart/form-data"
    )
    assert upload.status_code == 201

    document_id = upload.get_json()["document"]["id"]

    response = client.get(f"/api/documents/{document_id}/download")
    assert response.status_code == 200


def test_admin_delete_cleans_up_document(client, monkeypatch):
    from io import BytesIO

    import app as app_module
    from models import Document

    deleted_ids = []
    monkeypatch.setattr(app_module, "add_chunks", lambda chunks, document_id: None)
    monkeypatch.setattr(
        app_module,
        "delete_document_chunks",
        lambda document_id: deleted_ids.append(document_id)
    )

    register_test_admin(client)

    upload = client.post(
        "/api/documents",
        data={"file": (BytesIO(b"Delete test content"), "delete.txt")},
        content_type="multipart/form-data"
    )
    assert upload.status_code == 201

    document_id = upload.get_json()["document"]["id"]

    response = client.delete(f"/api/documents/{document_id}")
    assert response.status_code == 200
    assert document_id in deleted_ids

    assert Document.query.get(document_id) is None
