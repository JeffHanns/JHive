"""Serve the local JHive dashboard without connecting to a broker or market feed."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import time
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

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path == "/api/session":
            email = self._session_email()
            self._json(
                200,
                {
                    "authenticated": email is not None,
                    "email": email,
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
            self._serve_file("jhive-logo.png", "image/png")
            return
        else:
            self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
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
