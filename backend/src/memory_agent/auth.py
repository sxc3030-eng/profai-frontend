# -*- coding: utf-8 -*-
"""Authentification SaaS — AI Formateur.

JWT-based auth avec refresh tokens. Stockage local (JSON + SQLite).
Prêt pour migration PostgreSQL/Cosmos.

Usage:
    from memory_agent.auth import AuthManager
    auth = AuthManager()
    token = auth.create_token("alice@ecole.qc.ca", "student")
    user = auth.verify_token(token)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


AUTH_DIR = Path(__file__).resolve().parents[2] / "auth_data"
AUTH_DIR.mkdir(parents=True, exist_ok=True)

# ── Config ──────────────────────────────────────────────────────────────────

JWT_SECRET = secrets.token_hex(32)  # Généré au premier lancement
TOKEN_EXPIRY_MINUTES = 60
REFRESH_EXPIRY_DAYS = 30


@dataclass
class User:
    """Utilisateur du SaaS."""

    user_id: str
    email: str
    password_hash: str
    name: str = ""
    plan: str = "free"
    grade: str = "secondary_5"
    lang: str = "fr"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_login: str = ""
    email_verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "name": self.name,
            "plan": self.plan,
            "grade": self.grade,
            "lang": self.lang,
            "created_at": self.created_at,
            "email_verified": self.email_verified,
        }


class AuthManager:
    """Gestionnaire d'authentification JWT."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = storage_dir or AUTH_DIR
        self.db_path = self.storage_dir / "users.db"
        self._init_db()
        self._load_secret()

    # ── DB ───────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT DEFAULT '',
                plan TEXT DEFAULT 'free',
                grade TEXT DEFAULT 'secondary_5',
                lang TEXT DEFAULT 'fr',
                created_at TEXT NOT NULL,
                last_login TEXT DEFAULT '',
                email_verified INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)
        conn.commit()
        conn.close()

    def _load_secret(self) -> None:
        global JWT_SECRET
        secret_file = self.storage_dir / ".jwt_secret"
        if secret_file.exists():
            JWT_SECRET = secret_file.read_text().strip()
        else:
            JWT_SECRET = secrets.token_hex(32)
            secret_file.write_text(JWT_SECRET)

    # ── Auth API ─────────────────────────────────────────────────────────

    def signup(self, email: str, password: str, name: str = "", plan: str = "free") -> dict[str, Any]:
        """Crée un compte utilisateur."""
        email = email.strip().lower()
        if not email or "@" not in email:
            return {"error": "Email invalide"}
        if len(password) < 6:
            return {"error": "Mot de passe trop court (min 6 caractères)"}

        conn = sqlite3.connect(str(self.db_path))
        existing = conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            conn.close()
            return {"error": "Cet email est déjà utilisé"}

        user_id = hashlib.sha256(email.encode()).hexdigest()[:16]
        password_hash = self._hash_password(password)

        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO users (user_id, email, password_hash, name, plan, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, email, password_hash, name or email.split("@")[0], plan, now),
        )
        conn.commit()
        conn.close()

        token = self._create_token(user_id, email, plan)
        refresh = self._create_refresh_token(user_id)

        return {
            "user": {
                "user_id": user_id,
                "email": email,
                "name": name or email.split("@")[0],
                "plan": plan,
            },
            "token": token,
            "refresh_token": refresh,
        }

    def login(self, email: str, password: str) -> dict[str, Any]:
        """Connecte un utilisateur."""
        email = email.strip().lower()
        conn = sqlite3.connect(str(self.db_path))
        row = conn.execute(
            "SELECT user_id, email, password_hash, name, plan, grade, lang FROM users WHERE email = ?",
            (email,),
        ).fetchone()

        if not row:
            conn.close()
            return {"error": "Email ou mot de passe incorrect"}

        user_id, db_email, pw_hash, name, plan, grade, lang = row

        if not self._verify_password(password, pw_hash):
            conn.close()
            return {"error": "Email ou mot de passe incorrect"}

        # Mettre à jour last_login
        now = datetime.now(timezone.utc).isoformat()
        conn.execute("UPDATE users SET last_login = ? WHERE user_id = ?", (now, user_id))
        conn.commit()
        conn.close()

        token = self._create_token(user_id, db_email, plan)
        refresh = self._create_refresh_token(user_id)

        return {
            "user": {
                "user_id": user_id,
                "email": db_email,
                "name": name,
                "plan": plan,
                "grade": grade,
                "lang": lang,
            },
            "token": token,
            "refresh_token": refresh,
        }

    def verify_token(self, token: str) -> dict[str, Any] | None:
        """Vérifie un token JWT."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None

            header_b64, payload_b64, actual_sig = parts

            # Vérifier signature d'abord
            expected_sig = self._sign(f"{header_b64}.{payload_b64}")
            if not hmac.compare_digest(expected_sig, actual_sig):
                return None

            # Décoder le payload
            payload_b64_padded = payload_b64 + "=" * (4 - len(payload_b64) % 4)
            payload = json.loads(self._b64decode(payload_b64_padded))

            # Vérifier expiration
            if payload.get("exp", 0) < time.time():
                return None

            return {
                "user_id": payload["sub"],
                "email": payload["email"],
                "plan": payload.get("plan", "free"),
            }
        except Exception:
            return None

    def refresh_token(self, refresh_token: str) -> dict[str, Any] | None:
        """Rafraîchit un token expiré."""
        conn = sqlite3.connect(str(self.db_path))
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        row = conn.execute(
            "SELECT user_id, expires_at FROM refresh_tokens WHERE token_hash = ?",
            (token_hash,),
        ).fetchone()

        if not row:
            conn.close()
            return None

        user_id, expires_at = row
        if datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
            conn.execute("DELETE FROM refresh_tokens WHERE token_hash = ?", (token_hash,))
            conn.commit()
            conn.close()
            return None

        # Récupérer l'utilisateur
        user_row = conn.execute(
            "SELECT email, plan FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        conn.close()

        if not user_row:
            return None

        email, plan = user_row
        new_token = self._create_token(user_id, email, plan)
        new_refresh = self._create_refresh_token(user_id)

        return {"token": new_token, "refresh_token": new_refresh}

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        """Récupère les infos d'un utilisateur."""
        conn = sqlite3.connect(str(self.db_path))
        row = conn.execute(
            "SELECT email, name, plan, grade, lang, created_at, last_login, email_verified FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        conn.close()

        if not row:
            return None

        email, name, plan, grade, lang, created_at, last_login, verified = row
        return {
            "user_id": user_id,
            "email": email,
            "name": name,
            "plan": plan,
            "grade": grade,
            "lang": lang,
            "created_at": created_at,
            "last_login": last_login,
            "email_verified": bool(verified),
        }

    def update_user(self, user_id: str, updates: dict[str, Any]) -> bool:
        """Met à jour les infos utilisateur."""
        allowed = {"name", "grade", "lang", "plan"}
        fields = {k: v for k, v in updates.items() if k in allowed}
        if not fields:
            return False

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [user_id]

        conn = sqlite3.connect(str(self.db_path))
        conn.execute(f"UPDATE users SET {set_clause} WHERE user_id = ?", values)
        conn.commit()
        conn.close()
        return True

    # ── Internes ─────────────────────────────────────────────────────────

    def _create_token(self, user_id: str, email: str, plan: str) -> str:
        now = int(time.time())
        header = self._b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
        payload = self._b64encode(json.dumps({
            "sub": user_id,
            "email": email,
            "plan": plan,
            "iat": now,
            "exp": now + TOKEN_EXPIRY_MINUTES * 60,
        }, separators=(",", ":")))
        sig = self._sign(f"{header}.{payload}")
        return f"{header}.{payload}.{sig}"

    def _create_refresh_token(self, user_id: str) -> str:
        token = secrets.token_hex(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires = (datetime.now(timezone.utc) + timedelta(days=REFRESH_EXPIRY_DAYS)).isoformat()

        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            "INSERT OR REPLACE INTO refresh_tokens (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (token_hash, user_id, expires),
        )
        conn.commit()
        conn.close()
        return token

    def _sign(self, data: str) -> str:
        return hmac.new(JWT_SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()

    def _hash_password(self, password: str) -> str:
        salt = secrets.token_hex(16)
        h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
        return f"{salt}${h.hex()}"

    def _verify_password(self, password: str, password_hash: str) -> bool:
        salt, h = password_hash.split("$", 1)
        computed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
        return hmac.compare_digest(computed.hex(), h)

    @staticmethod
    def _b64encode(data: str) -> str:
        import base64
        return base64.urlsafe_b64encode(data.encode()).decode().rstrip("=")

    @staticmethod
    def _b64decode(data: str) -> bytes:
        import base64
        padding = 4 - len(data) % 4
        if padding != 4:
            data += "=" * padding
        return base64.urlsafe_b64decode(data)