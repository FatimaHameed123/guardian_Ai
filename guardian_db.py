"""
SQLite schema and seed data for Guardian AI secured investigation DB.
File: CriminalInvestigation_Secured.db (project root — not committed to git by default)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import bcrypt


def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def init_secured_db(db_path: Path, hash_fn=hash_password) -> None:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Users (
            u_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            assigned_area TEXT,
            login_attempts INTEGER DEFAULT 0,
            locked_until DATETIME,
            last_login DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Criminal_Cases (
            case_id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_title TEXT NOT NULL,
            crime_type TEXT NOT NULL,
            area TEXT NOT NULL,
            status TEXT DEFAULT 'Open',
            sho_id INTEGER,
            investigator_name TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Case_Details (
            detail_id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER UNIQUE,
            full_story TEXT,
            suspect_info TEXT,
            evidence_notes TEXT,
            is_encrypted INTEGER DEFAULT 1
        )""")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            action TEXT NOT NULL,
            table_affected TEXT,
            ip_address TEXT,
            status TEXT DEFAULT 'SUCCESS',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS CSRF_Tokens (
            token_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            token TEXT UNIQUE,
            expires_at DATETIME,
            used INTEGER DEFAULT 0
        )""")

    users = [
        ("admin_alishba", hash_fn("admin123"), "Admin", "All"),
        ("sho_faisalabad", hash_fn("sho456"), "SHO", "Hollywood"),
        ("public_user", hash_fn("user789"), "User", "None"),
        ("insp_bilal", hash_fn("bilal123"), "Inspector", "Hollywood"),
        ("insp_sana", hash_fn("sana123"), "Inspector", "Central"),
        ("insp_raza", hash_fn("raza123"), "Inspector", "Newton"),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO Users (username, password_hash, role, assigned_area) VALUES (?,?,?,?)",
        users,
    )

    case_count = cursor.execute("SELECT COUNT(*) FROM Criminal_Cases").fetchone()[0]
    if case_count == 0:
        sample_cases = [
            ("Bank Robbery", "Theft", "Hollywood", "Open", 2, "Inspector Bilal"),
            ("Cyber Fraud", "Fraud", "Central", "Open", 2, "Inspector Sana"),
            ("Assault Case", "Assault", "Newton", "Closed", 2, "Inspector Raza"),
            ("Vehicle Theft Ring", "Theft", "77Th Street", "Open", 2, "Inspector Ahmed"),
            ("Burglary Series", "Burglary", "Pacific", "Under Investigation", 2, "Inspector Bilal"),
        ]
        cursor.executemany(
            """INSERT INTO Criminal_Cases
               (case_title, crime_type, area, status, sho_id, investigator_name)
               VALUES (?,?,?,?,?,?)""",
            sample_cases,
        )

    conn.commit()
    conn.close()
