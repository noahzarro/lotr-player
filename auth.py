import json
import os
import secrets
import threading
import time
import uuid
from pathlib import Path

import jwt
from fastapi import HTTPException, Request

CODE_TTL = 300  # seconds


class Auth:
    def __init__(self, store: Path):
        self._store = store
        self._secret = secrets.token_urlsafe(32)
        self._codes: dict[str, float] = {}
        self._devices: dict[str, dict] = {}  # device_id -> info
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        try:
            data = json.loads(self._store.read_text())
            self._secret = data["secret"]
            self._devices = data["devices"]
        except (OSError, ValueError, KeyError):
            self._save()

    def _save(self):
        # caller holds the lock (or is __init__)
        tmp = self._store.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump({"secret": self._secret, "devices": self._devices}, f)
        os.replace(tmp, self._store)

    def clear(self):
        """Revoke all devices and rotate the signing secret."""
        with self._lock:
            self._devices = {}
            self._secret = secrets.token_urlsafe(32)
            self._save()

    def create_code(self) -> str:
        code = secrets.token_urlsafe(8)
        with self._lock:
            now = time.time()
            self._codes = {c: e for c, e in self._codes.items() if e > now}
            self._codes[code] = now + CODE_TTL
        return code

    def redeem(self, code: str, name: str) -> str | None:
        """Consume a one-time code and return a JWT, or None if invalid."""
        with self._lock:
            expires = self._codes.pop(code, None)  # pop => single use
            if expires is None or expires < time.time():
                return None
            device_id = uuid.uuid4().hex
            token = jwt.encode(
                {"sub": device_id, "name": name, "iat": int(time.time())},
                self._secret, algorithm="HS256",
            )
            self._devices[device_id] = {"id": device_id, "name": name, "paired_at": time.time(), "token": token}
            self._save()
            return token

    def verify(self, token: str | None) -> dict | None:
        if not token:
            return None
        try:
            claims = jwt.decode(token, self._secret, algorithms=["HS256"])
        except jwt.PyJWTError:
            return None
        with self._lock:
            dev = self._devices.get(claims.get("sub"))
            if dev is None or dev["token"] != token:
                return None
        return claims

    def devices(self) -> list[dict]:
        with self._lock:
            return [{k: v for k, v in d.items() if k != "token"} for d in self._devices.values()]

    def dependency(self):
        def require_jwt(request: Request) -> dict:
            token = request.cookies.get("token")
            header = request.headers.get("authorization", "")
            if header.lower().startswith("bearer "):
                token = header[7:].strip()
            claims = self.verify(token)
            if claims is None:
                raise HTTPException(401, "invalid or missing token")
            return claims
        return require_jwt
