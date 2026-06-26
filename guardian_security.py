"""
JWT auth, CSRF, audit logs, AES helpers for Guardian AI.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

import jwt
from flask import jsonify, request

JWT_EXPIRY_HOURS = 2


def load_or_create_secret(path: Path, nbytes: int = 32) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    value = secrets.token_hex(nbytes)
    path.write_text(value, encoding="utf-8")
    return value


def generate_jwt(user_id: int, username: str, role: str, area: str, secret: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "area": area,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def verify_jwt(token: str, secret: str) -> dict | None:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None


def log_action(get_db, user_id, username, action, table, status="SUCCESS") -> None:
    ip = request.remote_addr or "unknown"
    conn = get_db()
    conn.execute(
        "INSERT INTO Logs (user_id, username, action, table_affected, ip_address, status) VALUES (?,?,?,?,?,?)",
        (user_id, username, action, table, ip, status),
    )
    conn.commit()
    conn.close()


def generate_csrf_token(get_db, user_id: int) -> str:
    token = secrets.token_hex(32)
    expires = datetime.utcnow() + timedelta(hours=1)
    conn = get_db()
    conn.execute(
        "INSERT INTO CSRF_Tokens (user_id, token, expires_at) VALUES (?,?,?)",
        (user_id, token, expires.isoformat()),
    )
    conn.commit()
    conn.close()
    return token


def verify_csrf_token(get_db, token: str, user_id: int) -> bool:
    if not token:
        return False
    conn = get_db()
    row = conn.execute(
        """SELECT token_id FROM CSRF_Tokens
           WHERE token=? AND user_id=? AND used=0 AND expires_at > datetime('now')""",
        (token, user_id),
    ).fetchone()
    if row:
        conn.execute("UPDATE CSRF_Tokens SET used=1 WHERE token=?", (token,))
        conn.commit()
    conn.close()
    return row is not None


def require_auth(get_db, jwt_secret, allowed_roles=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            token = request.headers.get("Authorization", "").replace("Bearer ", "")
            if not token:
                return jsonify({"status": "denied", "message": "Login required"}), 401
            payload = verify_jwt(token, jwt_secret)
            if not payload:
                log_action(get_db, 0, "unknown", "Invalid JWT", "Auth", "FAILED")
                return jsonify({"status": "denied", "message": "Token expired or invalid"}), 401
            if allowed_roles and payload.get("role") not in allowed_roles:
                log_action(
                    get_db,
                    payload.get("user_id", 0),
                    payload.get("username", ""),
                    f"Forbidden: {request.path}",
                    "Auth",
                    "FORBIDDEN",
                )
                return jsonify({"status": "denied", "message": "Access forbidden"}), 403
            request.current_user = payload
            return f(*args, **kwargs)

        return wrapper

    return decorator


def encrypt_data(fernet, plain_text: str) -> str:
    if not plain_text:
        return ""
    return fernet.encrypt(plain_text.encode()).decode()


def decrypt_data(fernet, encrypted_text: str) -> str:
    if not encrypted_text:
        return ""
    try:
        return fernet.decrypt(encrypted_text.encode()).decode()
    except Exception:
        return "[Encrypted — cannot decrypt with current session key]"
