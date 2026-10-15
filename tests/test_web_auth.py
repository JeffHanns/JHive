import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from jhive.web import DashboardHandler


class QuietHandler(DashboardHandler):
    def log_message(self, fmt, *args):
        pass


@pytest.fixture
def app_server(tmp_path, monkeypatch):
    monkeypatch.setenv("JHIVE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("JHIVE_GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("JHIVE_GOOGLE_CLIENT_SECRET", raising=False)
    DashboardHandler.sessions.clear()
    DashboardHandler.admin_codes.clear()
    DashboardHandler.email_codes.clear()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
    except PermissionError:
        pytest.skip("this environment does not allow binding a local test server")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)
    DashboardHandler.sessions.clear()


def request(app_server, path, payload=None, cookie=None):
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if body else {}
    if cookie:
        headers["Cookie"] = cookie.split(";", 1)[0]
    req = urllib.request.Request(app_server + path, data=body, headers=headers)
    try:
        response = urllib.request.urlopen(req, timeout=3)
    except urllib.error.HTTPError as error:
        response = error
    return response.code, response.headers, json.loads(response.read() or b"{}")


def test_register_login_profile_and_logout(app_server, tmp_path):
    status, headers, result = request(app_server, "/api/register", {
        "email": "Member@Example.test", "password": "correct horse battery",
        "display_name": "Morgan Lee",
    })
    assert status == 200 and result["email"] == "member@example.test"
    cookie = headers["Set-Cookie"]
    status, _, session = request(app_server, "/api/session", cookie=cookie)
    assert status == 200
    assert session == {"authenticated": True, "email": "member@example.test",
                       "display_name": "Morgan Lee", "role": "Member"}

    status, _, updated = request(app_server, "/api/profile", {"display_name": "Morgan L."}, cookie)
    assert status == 200 and updated["display_name"] == "Morgan L."
    assert (tmp_path / "data" / "accounts.sqlite3").is_file()

    status, _, _ = request(app_server, "/api/logout", {}, cookie)
    assert status == 200
    _, _, signed_out = request(app_server, "/api/session", cookie=cookie)
    assert signed_out["authenticated"] is False

    status, headers, result = request(app_server, "/api/login", {
        "email": "MEMBER@example.test", "password": "correct horse battery",
    })
    assert status == 200 and result["ok"] is True
    assert headers.get("Set-Cookie")


@pytest.mark.parametrize(("path", "payload", "expected"), [
    ("/api/register", {"email": "not-an-email", "password": "long enough password"}, 400),
    ("/api/register", {"email": "valid@example.test", "password": "short"}, 400),
    ("/api/login", {"email": "unknown@example.test", "password": "any password here"}, 401),
])
def test_rejects_invalid_registration_and_credentials(app_server, path, payload, expected):
    status, _, result = request(app_server, path, payload)
    assert status == expected and "error" in result


def test_duplicate_registration_and_admin_access_controls(app_server):
    account = {"email": "member@example.test", "password": "correct horse battery"}
    assert request(app_server, "/api/register", account)[0] == 200
    assert request(app_server, "/api/register", account)[0] == 409
    assert request(app_server, "/api/register", {
        "email": DashboardHandler._setting("JHIVE_ADMIN_EMAIL", "jeffhanns.cilzikmusic@gmail.com"),
        "password": "correct horse battery",
    })[0] == 403
    assert request(app_server, "/api/admin-code", {"email": "other@example.test"})[0] == 404
    assert request(app_server, "/api/admin-password", {"password": "long enough password"})[0] == 403


def test_unconfigured_identity_providers_are_not_advertised_as_ready(app_server):
    status, _, options = request(app_server, "/api/auth-options")
    assert status == 200
    assert options["google"] is False
    assert options["github"] is False
    assert options["microsoft"] is False
    assert options["apple"] is False
