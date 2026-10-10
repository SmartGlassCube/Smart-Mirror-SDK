def test_login_wrong_password_rejected(client, admin_user):
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_user_rejected(client):
    resp = client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
    assert resp.status_code == 401


def test_login_success_sets_cookie_and_returns_user(client, admin_user):
    resp = client.post("/api/auth/login", json=admin_user)
    assert resp.status_code == 200
    assert resp.json() == {"username": "admin", "role": "admin"}
    assert "smartmirror_dashboard_session" in resp.cookies


def test_me_without_session_is_401(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_with_session_returns_user(logged_in_client):
    resp = logged_in_client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"


def test_content_endpoint_requires_auth(client):
    resp = client.get("/api/events")
    assert resp.status_code == 401


def test_logout_clears_session(logged_in_client):
    assert logged_in_client.get("/api/auth/me").status_code == 200
    logged_in_client.post("/api/auth/logout")
    assert logged_in_client.get("/api/auth/me").status_code == 401
