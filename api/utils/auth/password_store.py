"""Read/write helpers for the password-file auth store.

Shared by the PasswordFileProvider (read path, every request) and the
``scripts/auth_admin.py`` CLI (write path) so the on-disk format and the bcrypt
hashing never drift between them.

File schema (JSON)::

    {
      "version": 1,
      "users": {
        "alice": {
          "password_hash": "<bcrypt>",
          "email": "alice@example.org",
          "name": "Alice",
          "permissions": ["enroll:autodiscovery_admin"],
          "disabled": false
        }
      }
    }
"""

import json
import os
import tempfile
from pathlib import Path

import bcrypt

SCHEMA_VERSION = 1


class UserExistsError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


class PasswordStore:
    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)

    # --- read path (used by the provider on every request) ---

    def load(self) -> dict:
        """Return the full store, or an empty store if the file does not exist."""
        if not self.path.exists():
            return {"version": SCHEMA_VERSION, "users": {}}
        with self.path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("users", {})
        return data

    def get_user(self, username: str) -> dict | None:
        return self.load().get("users", {}).get(username)

    def verify_credentials(self, username: str, password: str) -> dict | None:
        """Return the user record if username+password match and not disabled."""
        user = self.get_user(username)
        if not user or user.get("disabled"):
            return None
        if not verify_password(password, user.get("password_hash", "")):
            return None
        return user

    # --- write path (used by the CLI) ---

    def save(self, data: dict) -> None:
        """Atomically write the store (temp file in same dir + os.replace)."""
        data.setdefault("version", SCHEMA_VERSION)
        data.setdefault("users", {})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=".auth-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True)
                f.write("\n")
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def add_user(
        self,
        username: str,
        password: str,
        email: str | None = None,
        name: str | None = None,
        permissions: list[str] | None = None,
    ) -> None:
        data = self.load()
        if username in data["users"]:
            raise UserExistsError(f"User '{username}' already exists")
        data["users"][username] = {
            "password_hash": hash_password(password),
            "email": email,
            "name": name,
            "permissions": sorted(set(permissions or [])),
            "disabled": False,
        }
        self.save(data)

    def _mutate(self, username: str, fn) -> None:
        data = self.load()
        if username not in data["users"]:
            raise UserNotFoundError(f"User '{username}' not found")
        fn(data["users"][username])
        self.save(data)

    def set_password(self, username: str, password: str) -> None:
        self._mutate(username, lambda u: u.__setitem__("password_hash", hash_password(password)))

    def set_disabled(self, username: str, disabled: bool) -> None:
        self._mutate(username, lambda u: u.__setitem__("disabled", disabled))

    def update_profile(
        self, username: str, email: str | None = None, name: str | None = None
    ) -> None:
        def apply(u):
            if email is not None:
                u["email"] = email
            if name is not None:
                u["name"] = name

        self._mutate(username, apply)

    def add_permissions(self, username: str, permissions: list[str]) -> None:
        def apply(u):
            u["permissions"] = sorted(set(u.get("permissions", [])) | set(permissions))

        self._mutate(username, apply)

    def remove_permissions(self, username: str, permissions: list[str]) -> None:
        def apply(u):
            u["permissions"] = sorted(set(u.get("permissions", [])) - set(permissions))

        self._mutate(username, apply)

    def delete_user(self, username: str) -> None:
        data = self.load()
        if username not in data["users"]:
            raise UserNotFoundError(f"User '{username}' not found")
        del data["users"][username]
        self.save(data)
