def test_mutating_routes_require_session_bound_csrf(client):
    client.application.config["TEST_CSRF_ENABLED"] = True
    try:
        assert client.post("/api/auth/register", json={}).status_code == 403
        token = client.get("/api/auth/csrf").get_json()["csrf_token"]
        response = client.post(
            "/api/auth/register",
            json={
                "name": "CSRF User",
                "email": "csrf@example.com",
                "password": "password123",
                "role": "student",
            },
            headers={"X-CSRF-Token": token},
        )
        assert response.status_code == 201
    finally:
        client.application.config["TEST_CSRF_ENABLED"] = False
