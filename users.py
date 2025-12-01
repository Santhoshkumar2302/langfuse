# user_management.py
import sqlite3
import bcrypt
import os

DB_PATH = "users.db"

# -----------------------------
# Initialize database
# -----------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# -----------------------------
# Create a new user
# -----------------------------
def create_user(username: str, password: str, role: str = "user") -> bool:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Check if user exists
    cur.execute("SELECT username FROM users WHERE username=?", (username,))
    if cur.fetchone():
        conn.close()
        return False

    # Hash password
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    cur.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, hashed, role)
    )
    conn.commit()
    conn.close()
    return True

# -----------------------------
# Get user details
# -----------------------------
def get_user(username: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT username, password_hash, role FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()

    if row:
        return {
            "username": row[0],
            "password_hash": row[1],
            "role": row[2]
        }
    return None

# -----------------------------
# Authenticate login
# -----------------------------
def authenticate(username: str, password: str) -> bool:
    user = get_user(username)
    if not user:
        return False

    stored_hash = user["password_hash"].encode()
    return bcrypt.checkpw(password.encode(), stored_hash)
