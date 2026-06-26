"""
Case CRUD + encrypted Case_Details — ported from Jupyter notebook Cell 5.
"""

from __future__ import annotations

from flask import jsonify, request

from guardian_security import generate_csrf_token, log_action, require_auth, verify_csrf_token


def register_cases_routes(app, *, get_db, sanitize_input, fernet, jwt_secret, limiter=None):
    def _limit(rule):
        return limiter.limit(rule) if limiter else lambda f: f

    auth = lambda roles=None: require_auth(get_db, jwt_secret, roles)

    @_limit("60 per minute")
    @app.route("/cases", methods=["GET"])
    @auth(["Admin", "SHO", "Inspector"])
    def get_cases():
        user = request.current_user
        conn = get_db()
        if user["role"] == "Admin":
            rows = conn.execute(
                "SELECT * FROM Criminal_Cases ORDER BY case_id DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM Criminal_Cases WHERE area=? ORDER BY case_id DESC",
                (user["area"],),
            ).fetchall()
        conn.close()
        log_action(get_db, user["user_id"], user["username"], "Viewed cases", "Criminal_Cases")
        return jsonify({"status": "ok", "cases": [dict(r) for r in rows]})

    @_limit("30 per minute")
    @app.route("/cases/add", methods=["POST"])
    @auth(["Admin", "SHO", "Inspector"])
    def add_case():
        from heatmap_service import invalidate_heatmap_cache

        user = request.current_user
        d = request.json or {}
        if not verify_csrf_token(get_db, d.get("csrf_token", ""), user["user_id"]):
            return jsonify({"status": "denied", "message": "Invalid CSRF token"}), 403

        case_title = sanitize_input(d.get("case_title", "Untitled"), 100)
        crime_type = sanitize_input(d.get("crime_type", "Unknown"), 50)
        area = sanitize_input(d.get("area", ""), 50)
        investigator_name = sanitize_input(d.get("investigator_name", "Unknown"), 100)
        if not case_title or not area:
            return jsonify({"status": "fail", "message": "case_title and area are required"}), 400

        conn = get_db()
        cur = conn.execute(
            """INSERT INTO Criminal_Cases
               (case_title, crime_type, area, status, sho_id, investigator_name)
               VALUES (?,?,?,?,?,?)""",
            (case_title, crime_type, area, "Open", user["user_id"], investigator_name),
        )
        new_id = cur.lastrowid
        conn.commit()
        conn.close()
        invalidate_heatmap_cache()
        log_action(
            get_db, user["user_id"], user["username"],
            f"Added Case #{new_id}: {case_title}", "Criminal_Cases",
        )
        return jsonify({
            "status": "success",
            "case_id": new_id,
            "csrf_token": generate_csrf_token(get_db, user["user_id"]),
        })

    @_limit("30 per minute")
    @app.route("/cases/update/<int:case_id>", methods=["POST"])
    @auth(["Admin", "SHO", "Inspector"])
    def update_case(case_id):
        user = request.current_user
        d = request.json or {}
        if not verify_csrf_token(get_db, d.get("csrf_token", ""), user["user_id"]):
            return jsonify({"status": "denied", "message": "Invalid CSRF token"}), 403

        allowed = ["Open", "Closed", "Under Investigation"]
        new_status = d.get("status", "Open")
        if new_status not in allowed:
            return jsonify({"status": "fail", "message": "Invalid status"}), 400

        investigator = sanitize_input(d.get("investigator_name", ""), 100)
        conn = get_db()
        conn.execute(
            "UPDATE Criminal_Cases SET status=?, investigator_name=? WHERE case_id=?",
            (new_status, investigator, case_id),
        )
        conn.commit()
        conn.close()
        log_action(
            get_db, user["user_id"], user["username"],
            f"Updated Case #{case_id} → {new_status}", "Criminal_Cases",
        )
        return jsonify({
            "status": "success",
            "csrf_token": generate_csrf_token(get_db, user["user_id"]),
        })

    @_limit("20 per minute")
    @app.route("/cases/delete/<int:case_id>", methods=["POST"])
    @auth(["Admin"])
    def delete_case(case_id):
        from heatmap_service import invalidate_heatmap_cache

        user = request.current_user
        d = request.json or {}
        if not verify_csrf_token(get_db, d.get("csrf_token", ""), user["user_id"]):
            return jsonify({"status": "denied", "message": "Invalid CSRF token"}), 403

        conn = get_db()
        conn.execute("DELETE FROM Case_Details WHERE case_id=?", (case_id,))
        conn.execute("DELETE FROM Criminal_Cases WHERE case_id=?", (case_id,))
        conn.commit()
        conn.close()
        invalidate_heatmap_cache()
        log_action(
            get_db, user["user_id"], user["username"],
            f"DELETED Case #{case_id}", "Criminal_Cases",
        )
        return jsonify({
            "status": "success",
            "csrf_token": generate_csrf_token(get_db, user["user_id"]),
        })

    @_limit("30 per minute")
    @app.route("/cases/<int:case_id>/details", methods=["POST"])
    @auth(["Admin", "SHO", "Inspector"])
    def save_case_details(case_id):
        from guardian_security import encrypt_data

        user = request.current_user
        d = request.json or {}
        if not verify_csrf_token(get_db, d.get("csrf_token", ""), user["user_id"]):
            return jsonify({"status": "denied", "message": "Invalid CSRF token"}), 403

        enc_story = encrypt_data(fernet, sanitize_input(d.get("full_story", ""), 2000))
        enc_suspect = encrypt_data(fernet, sanitize_input(d.get("suspect_info", ""), 1000))
        enc_evidence = encrypt_data(fernet, sanitize_input(d.get("evidence_notes", ""), 1000))

        conn = get_db()
        conn.execute(
            """INSERT OR REPLACE INTO Case_Details
               (case_id, full_story, suspect_info, evidence_notes, is_encrypted)
               VALUES (?,?,?,?,1)""",
            (case_id, enc_story, enc_suspect, enc_evidence),
        )
        conn.commit()
        conn.close()
        log_action(
            get_db, user["user_id"], user["username"],
            f"Saved details for Case #{case_id}", "Case_Details",
        )
        return jsonify({
            "status": "success",
            "message": "Details saved (AES encrypted)",
            "csrf_token": generate_csrf_token(get_db, user["user_id"]),
        })

    @_limit("60 per minute")
    @app.route("/cases/<int:case_id>/details", methods=["GET"])
    @auth(["Admin", "SHO", "Inspector"])
    def get_case_details(case_id):
        from guardian_security import decrypt_data

        user = request.current_user
        conn = get_db()
        row = conn.execute("SELECT * FROM Case_Details WHERE case_id=?", (case_id,)).fetchone()
        conn.close()
        if not row:
            return jsonify({"status": "not_found"}), 404
        log_action(
            get_db, user["user_id"], user["username"],
            f"Viewed details Case #{case_id}", "Case_Details",
        )
        return jsonify({
            "status": "ok",
            "full_story": decrypt_data(fernet, row["full_story"]),
            "suspect_info": decrypt_data(fernet, row["suspect_info"]),
            "evidence_notes": decrypt_data(fernet, row["evidence_notes"]),
        })

    @_limit("30 per minute")
    @app.route("/api/db/info", methods=["GET"])
    @auth(["Admin", "SHO", "Inspector"])
    def db_info():
        """Where the SQLite file lives and table counts."""
        from pathlib import Path

        root = Path(__file__).resolve().parent
        db_file = root / "CriminalInvestigation_Secured.db"
        conn = get_db()
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        counts = {}
        for t in ("Users", "Criminal_Cases", "Case_Details", "Logs"):
            if t in tables:
                counts[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        conn.close()
        return jsonify({
            "status": "ok",
            "database_file": str(db_file),
            "exists": db_file.exists(),
            "size_bytes": db_file.stat().st_size if db_file.exists() else 0,
            "tables": tables,
            "counts": counts,
        })

    print("[OK] Case CRUD APIs: /cases, /cases/add, /cases/update, /cases/delete, /cases/<id>/details")
