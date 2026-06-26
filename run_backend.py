"""
Run Guardian AI Flask backend without Jupyter.
Usage: python run_backend.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ML_DIR = ROOT / "ml"
DB_PATH = ROOT / "CriminalInvestigation_Secured.db"
sys.path.insert(0, str(ML_DIR))
sys.path.insert(0, str(ROOT))

from cryptography.fernet import Fernet
import bcrypt
import bleach
import jwt
import sqlite3
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from guardian_db import init_secured_db, hash_password
from guardian_security import (
    generate_csrf_token,
    generate_jwt,
    load_or_create_secret,
    require_auth,
)

JWT_SECRET_KEY = load_or_create_secret(ROOT / ".guardian_jwt.secret")
AES_KEY_FILE = ROOT / ".guardian_fernet.key"
if AES_KEY_FILE.exists():
    fernet = Fernet(AES_KEY_FILE.read_bytes().strip())
else:
    key = Fernet.generate_key()
    AES_KEY_FILE.write_bytes(key)
    fernet = Fernet(key)

init_secured_db(DB_PATH, hash_password)


def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


# ─── ML ─────────────────────────────────────────────────────────────────────
from chat_predict_service import load_chat_artifacts, process_chat_message

_chat = load_chat_artifacts(ML_DIR / "artifacts")
rf_model = _chat["rf_model"]
encoders = _chat["encoders"]
aggregates = _chat["aggregates"]
print(f"ML ready — {len(_chat['le'].classes_)} areas")

# ─── Flask ──────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = load_or_create_secret(ROOT / ".guardian_flask.secret")
CORS(
    app,
    supports_credentials=True,
    origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
)

limiter = Limiter(get_remote_address, app=app, default_limits=["200 per day", "50 per hour"])


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def sanitize_input(text, max_length=200):
    if not text or not isinstance(text, str):
        return ""
    clean = bleach.clean(str(text), tags=[], strip=True)[:max_length]
    for p in ["'--", "; DROP", "UNION SELECT", "1=1"]:
        clean = clean.replace(p, "")
    return clean.strip()


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "security": "enabled",
        "model": "RandomForest",
        "database": str(DB_PATH),
        "database_exists": DB_PATH.exists(),
    })


@app.route("/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    d = request.json or {}
    username = sanitize_input(d.get("username", ""), 50)
    password = d.get("password", "")
    conn = get_db()
    row = conn.execute("SELECT * FROM Users WHERE username=?", (username,)).fetchone()
    conn.close()
    if not row or not verify_password(password, row["password_hash"]):
        return jsonify({"status": "fail", "message": "Invalid credentials"}), 401
    token = generate_jwt(row["u_id"], row["username"], row["role"], row["assigned_area"], JWT_SECRET_KEY)
    csrf = generate_csrf_token(get_db, row["u_id"])
    return jsonify({
        "status": "success",
        "username": row["username"],
        "role": row["role"],
        "area": row["assigned_area"],
        "token": token,
        "csrf_token": csrf,
    })


@app.route("/chat_predict", methods=["POST"])
@limiter.limit("30 per minute")
def chat_predict():
    raw = (request.json or {}).get("message", "")
    user_query = sanitize_input(raw, max_length=500)

    def _live(area_name):
        conn = get_db()
        row = conn.execute(
            "SELECT case_title, investigator_name FROM Criminal_Cases WHERE area=? AND status='Open' LIMIT 1",
            (area_name,),
        ).fetchone()
        conn.close()
        if row:
            return {"case_title": row["case_title"], "investigator_name": row["investigator_name"]}
        return None

    return jsonify(
        process_chat_message(
            user_query,
            rf_model,
            encoders,
            aggregates,
            get_live_case=_live,
            artifacts_dir=ML_DIR / "artifacts",
        )
    )


from guardian_api_extensions import register_extension_routes
from guardian_cases_api import register_cases_routes

register_extension_routes(app, sanitize_input, limiter)
register_cases_routes(app, get_db=get_db, sanitize_input=sanitize_input, fernet=fernet, jwt_secret=JWT_SECRET_KEY, limiter=limiter)


@app.route("/csrf", methods=["GET"])
@require_auth(get_db, JWT_SECRET_KEY)
def refresh_csrf():
    user = request.current_user
    return jsonify({"csrf_token": generate_csrf_token(get_db, user["user_id"])})

if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("GUARDIAN AI BACKEND RUNNING")
    print("=" * 50)
    print(f"  Database: {DB_PATH}")
    print("  Health:   http://127.0.0.1:5000/health")
    print("  Cases:    GET  http://127.0.0.1:5000/cases")
    print("  Heatmap:  GET  http://127.0.0.1:5000/api/heatmap")
    print("=" * 50 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
