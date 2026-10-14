"""Serve the local JHive dashboard without connecting to a broker or market feed."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets
import smtplib
import ssl
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
from email.message import EmailMessage
from collections.abc import Iterator
from contextlib import contextmanager
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ADMIN_EMAIL = "jeffhanns.cilzikmusic@gmail.com"


class DashboardHandler(BaseHTTPRequestHandler):
    """Serve the bundled dashboard from a local-only development server."""

    sessions: dict[str, tuple[str, float]] = {}
    session_lock = threading.Lock()
    session_lifetime = 12 * 60 * 60
    admin_codes: dict[str, tuple[str, float, int, float]] = {}
    email_codes: dict[str, tuple[str, float, int, float]] = {}
    oauth_states: dict[str, tuple[str, float, str, str]] = {}

    @staticmethod
    def _setting(name: str, default: str = "") -> str:
        return os.environ.get(name, default).strip()

    @classmethod
    def _provider_config(cls, provider: str) -> tuple[str, str, str, str] | None:
        key = provider.upper()
        client_id = cls._setting(f"JHIVE_{key}_CLIENT_ID")
        client_secret = cls._setting(f"JHIVE_{key}_CLIENT_SECRET")
        if not client_id or not client_secret:
            return None
        if provider == "google":
            return (client_id, client_secret, "https://accounts.google.com/o/oauth2/v2/auth", "https://oauth2.googleapis.com/token")
        if provider == "microsoft":
            return (client_id, client_secret, "https://login.microsoftonline.com/common/oauth2/v2.0/authorize", "https://login.microsoftonline.com/common/oauth2/v2.0/token")
        return None

    @classmethod
    def _email_ready(cls) -> bool:
        return bool(cls._setting("JHIVE_SMTP_HOST") and cls._setting("JHIVE_SMTP_FROM"))

    @classmethod
    def _send_email_code(cls, email: str, code: str) -> None:
        message = EmailMessage()
        message["Subject"] = "Your JHive sign-in code"
        message["From"] = cls._setting("JHIVE_SMTP_FROM")
        message["To"] = email
        message.set_content(f"Your JHive sign-in code is {code}. It expires in 10 minutes.")
        host = cls._setting("JHIVE_SMTP_HOST")
        port = int(cls._setting("JHIVE_SMTP_PORT", "587"))
        with smtplib.SMTP(host, port, timeout=15) as server:
            if cls._setting("JHIVE_SMTP_STARTTLS", "true").lower() == "true":
                server.starttls(context=ssl.create_default_context())
            username = cls._setting("JHIVE_SMTP_USER")
            if username:
                server.login(username, cls._setting("JHIVE_SMTP_PASSWORD"))
            server.send_message(message)

    @staticmethod
    @contextmanager
    def _database() -> Iterator[sqlite3.Connection]:
        data_dir = Path.home() / ".jhive"
        data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            data_dir.chmod(0o700)
        except OSError:
            pass
        connection = sqlite3.connect(data_dir / "accounts.sqlite3")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "email TEXT PRIMARY KEY, salt BLOB NOT NULL, password_hash BLOB NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS user_profiles ("
            "email TEXT PRIMARY KEY, display_name TEXT NOT NULL DEFAULT '')"
        )
        connection.commit()
        try:
            (data_dir / "accounts.sqlite3").chmod(0o600)
        except OSError:
            pass
        try:
            yield connection
        finally:
            connection.close()

    def _json(self, status: int, payload: dict[str, object], headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _session_email(self) -> str | None:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookie.get("jhive_session")
        if morsel is None:
            return None
        token = morsel.value
        with self.session_lock:
            session = self.sessions.get(token)
            if session and session[1] > time.time():
                return session[0]
            self.sessions.pop(token, None)
        return None

    def _start_session(self, email: str) -> str:
        token = secrets.token_urlsafe(32)
        with self.session_lock:
            self.sessions[token] = (email, time.time() + self.session_lifetime)
        return f"jhive_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={self.session_lifetime}"

    def _read_json(self) -> dict[str, object] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 4096:
                return None
            value = json.loads(self.rfile.read(length))
            return value if isinstance(value, dict) else None
        except (ValueError, json.JSONDecodeError):
            return None

    def _redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _serve_file(self, filename: str, content_type: str) -> None:
        body = (Path(__file__).parent / "static" / filename).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _oauth_callback(self, provider: str, query: dict[str, list[str]]) -> None:
        state = query.get("state", [""])[0]
        code = query.get("code", [""])[0]
        with self.session_lock:
            challenge = self.oauth_states.pop(state, None)
        if not challenge or challenge[0] != provider or challenge[2] < time.time() or not code:
            self._redirect("/?error=signin")
            return
        _, _, redirect_uri, code_verifier = challenge
        config = self._provider_config(provider)
        if not config:
            self._redirect("/?error=setup")
            return
        client_id, client_secret, _, token_url = config
        try:
            token_body = urllib.parse.urlencode({"client_id": client_id, "client_secret": client_secret,
                "code": code, "grant_type": "authorization_code", "redirect_uri": redirect_uri,
                "code_verifier": code_verifier}).encode()
            request = urllib.request.Request(token_url, data=token_body, headers={"Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=15) as response:
                access_token = json.loads(response.read()).get("access_token")
            if not access_token:
                raise ValueError("No access token")
            user_url = "https://openidconnect.googleapis.com/v1/userinfo" if provider == "google" else "https://graph.microsoft.com/oidc/userinfo"
            request = urllib.request.Request(user_url, headers={"Authorization": f"Bearer {access_token}"})
            with urllib.request.urlopen(request, timeout=15) as response:
                profile = json.loads(response.read())
            email = str(profile.get("email") or profile.get("preferred_username") or "").strip().lower()
            if not email or "@" not in email or profile.get("email_verified") is False:
                raise ValueError("Provider did not return a verified email")
        except Exception as exc:
            print(f"JHive {provider} sign-in failed: {type(exc).__name__}")
            self._redirect("/?error=signin")
            return
        self._redirect_with_cookie("/dashboard", self._start_session(email))

    def _redirect_with_cookie(self, location: str, cookie: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/api/auth-options":
            self._json(200, {"google": self._provider_config("google") is not None,
                "microsoft": self._provider_config("microsoft") is not None, "email": self._email_ready()})
            return
        if parsed.path in {"/auth/google", "/auth/microsoft"}:
            provider = parsed.path.rsplit("/", 1)[-1]
            config = self._provider_config(provider)
            if not config:
                self._redirect("/?error=setup")
                return
            client_id, _, auth_url, _ = config
            base = self._setting("JHIVE_BASE_URL", "http://127.0.0.1:8765").rstrip("/")
            redirect_uri = f"{base}/auth/{provider}/callback"
            state = secrets.token_urlsafe(32)
            verifier = secrets.token_urlsafe(48)
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
            with self.session_lock:
                self.oauth_states[state] = (provider, time.time() + 300, redirect_uri, verifier)
            scopes = "openid email profile" + (" User.Read" if provider == "microsoft" else "")
            params = {"client_id": client_id, "response_type": "code", "redirect_uri": redirect_uri,
                "response_mode": "query", "scope": scopes, "state": state, "nonce": secrets.token_urlsafe(24),
                "code_challenge": challenge, "code_challenge_method": "S256"}
            self._redirect(auth_url + "?" + urllib.parse.urlencode(params))
            return
        if parsed.path in {"/auth/google/callback", "/auth/microsoft/callback"}:
            self._oauth_callback(parsed.path.split("/")[2], urllib.parse.parse_qs(parsed.query))
            return
        if parsed.path == "/api/session":
            email = self._session_email()
            display_name = ""
            if email:
                with self._database() as connection:
                    row = connection.execute(
                        "SELECT display_name FROM user_profiles WHERE email = ?", (email,)
                    ).fetchone()
                display_name = row[0] if row and row[0] else ""
            self._json(
                200,
                {
                    "authenticated": email is not None,
                    "email": email,
                    "display_name": display_name,
                    "role": "Super administrator" if email == ADMIN_EMAIL else "Member",
                },
            )
            return
        if self.path in {"/", "/index.html"}:
            if self._session_email():
                self._redirect("/dashboard")
                return
            self._serve_file("login.html", "text/html; charset=utf-8")
            return
        if self.path == "/dashboard":
            if not self._session_email():
                self._redirect("/")
                return
            self._serve_file("dashboard.html", "text/html; charset=utf-8")
            return
        if self.path == "/jhive-logo.png":
            self._serve_file("jhive-logo.png", "image/png")
            return
        if self.path == "/favicon.png":
            self._serve_file("favicon.png", "image/png")
            return
        if self.path == "/favicon.ico":
            self._serve_file("favicon.png", "image/png")
            return
        else:
            self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path == "/api/email-code":
            payload = self._read_json()
            email = str(payload.get("email", "")).strip().lower() if payload else ""
            if len(email) > 254 or "@" not in email or email.startswith("@") or email.endswith("@"):
                self._json(400, {"error": "Enter a valid email address."})
                return
            if not self._email_ready():
                self._json(503, {"error": "Email sign-in needs SMTP settings in your local .env file."})
                return
            now = time.time()
            with self.session_lock:
                existing = self.email_codes.get(email)
                if existing and existing[3] > now:
                    self._json(429, {"error": "Wait a minute before requesting another code."})
                    return
                code = f"{secrets.randbelow(1_000_000):06d}"
                self.email_codes[email] = (code, now + 600, 0, now + 60)
            try:
                self._send_email_code(email, code)
            except Exception as exc:
                with self.session_lock:
                    self.email_codes.pop(email, None)
                print(f"JHive email delivery failed: {type(exc).__name__}")
                self._json(503, {"error": "JHive could not send the sign-in email. Check SMTP settings."})
                return
            self._json(200, {"ok": True, "message": "Check your email for a six-digit sign-in code."})
            return

        if self.path == "/api/email-verify":
            payload = self._read_json()
            email = str(payload.get("email", "")).strip().lower() if payload else ""
            code = str(payload.get("code", "")).strip() if payload else ""
            now = time.time()
            with self.session_lock:
                challenge = self.email_codes.get(email)
                valid = bool(challenge and challenge[1] > now and challenge[2] < 5 and hmac.compare_digest(code, challenge[0]))
                if valid:
                    self.email_codes.pop(email, None)
                elif challenge:
                    if challenge[1] <= now or challenge[2] + 1 >= 5:
                        self.email_codes.pop(email, None)
                    else:
                        self.email_codes[email] = (challenge[0], challenge[1], challenge[2] + 1, challenge[3])
            if not valid:
                self._json(401, {"error": "That code is invalid or expired."})
                return
            self._json(200, {"ok": True, "email": email}, {"Set-Cookie": self._start_session(email)})
            return

        if self.path == "/api/profile":
            email = self._session_email()
            if not email:
                self._json(401, {"error": "Sign in to update your profile."})
                return
            payload = self._read_json()
            display_name = str(payload.get("display_name", "")).strip() if payload else ""
            if not 2 <= len(display_name) <= 60:
                self._json(400, {"error": "Enter a display name between 2 and 60 characters."})
                return
            with self._database() as connection:
                connection.execute(
                    "INSERT INTO user_profiles (email, display_name) VALUES (?, ?) "
                    "ON CONFLICT(email) DO UPDATE SET display_name = excluded.display_name",
                    (email, display_name),
                )
                connection.commit()
            self._json(200, {"ok": True, "display_name": display_name})
            return

        if self.path == "/api/logout":
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            morsel = cookie.get("jhive_session")
            if morsel:
                with self.session_lock:
                    self.sessions.pop(morsel.value, None)
            self._json(200, {"ok": True}, {"Set-Cookie": "jhive_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"})
            return

        if self.path == "/api/admin-code":
            payload = self._read_json()
            email = str(payload.get("email", "")).strip().lower() if payload else ""
            if email != ADMIN_EMAIL:
                self._json(404, {"error": "Admin sign-in is unavailable for this email."})
                return
            now = time.time()
            with self.session_lock:
                current = self.admin_codes.get(email)
                if current and current[3] > now:
                    self._json(429, {"error": "Wait a minute before requesting another code."})
                    return
                code = f"{secrets.randbelow(1_000_000):06d}"
                self.admin_codes[email] = (code, now + 300, 0, now + 60)
            print(f"JHive admin sign-in code for {email}: {code} (expires in 5 minutes)")
            self._json(200, {"ok": True, "message": "Check the JHive server terminal for your one-time sign-in code."})
            return

        if self.path == "/api/admin-verify":
            payload = self._read_json()
            email = str(payload.get("email", "")).strip().lower() if payload else ""
            code = str(payload.get("code", "")).strip() if payload else ""
            now = time.time()
            with self.session_lock:
                challenge = self.admin_codes.get(email)
                if email != ADMIN_EMAIL or challenge is None or challenge[1] <= now or challenge[2] >= 5:
                    self.admin_codes.pop(email, None)
                    valid = False
                else:
                    valid = hmac.compare_digest(code, challenge[0])
                    if not valid:
                        self.admin_codes[email] = (challenge[0], challenge[1], challenge[2] + 1, challenge[3])
                    else:
                        self.admin_codes.pop(email, None)
            if not valid:
                self._json(401, {"error": "That code is invalid or expired."})
                return
            self._json(200, {"ok": True, "email": email}, {"Set-Cookie": self._start_session(email)})
            return

        if self.path not in {"/api/login", "/api/register"}:
            self._json(404, {"error": "Not found."})
            return
        payload = self._read_json()
        if payload is None:
            self._json(400, {"error": "Invalid request."})
            return
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        if len(email) > 254 or "@" not in email or email.startswith("@") or email.endswith("@"):
            self._json(400, {"error": "Enter a valid email address."})
            return
        if self.path == "/api/register":
            if email == ADMIN_EMAIL:
                self._json(403, {"error": "Use administrator sign-in for this account."})
                return
            if len(password) < 12:
                self._json(400, {"error": "Use a password with at least 12 characters."})
                return
            salt = secrets.token_bytes(16)
            password_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
            try:
                with self._database() as connection:
                    connection.execute(
                        "INSERT INTO users (email, salt, password_hash) VALUES (?, ?, ?)",
                        (email, salt, password_hash),
                    )
                    connection.commit()
            except sqlite3.IntegrityError:
                self._json(409, {"error": "An account already exists for that email."})
                return
        else:
            if email == ADMIN_EMAIL:
                self._json(401, {"error": "Use administrator sign-in for this account."})
                return
            with self._database() as connection:
                row = connection.execute(
                    "SELECT salt, password_hash FROM users WHERE email = ?", (email,)
                ).fetchone()
            if row is None:
                self._json(401, {"error": "Email or password is incorrect."})
                return
            candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), row[0], 310_000)
            if not hmac.compare_digest(candidate, row[1]):
                self._json(401, {"error": "Email or password is incorrect."})
                return
        self._json(200, {"ok": True, "email": email}, {"Set-Cookie": self._start_session(email)})

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"JHive dashboard: {args[0] if args else fmt}")


def main() -> None:
    """Start the dashboard on loopback so it is only available on this computer."""
    env_file = Path.cwd() / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            os.environ.setdefault(name.strip(), value.strip().strip("\"'"))
    parser = argparse.ArgumentParser(description="Run the local JHive demo dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: loopback only)")
    parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"JHive demo dashboard running at http://{args.host}:{args.port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping JHive dashboard.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
