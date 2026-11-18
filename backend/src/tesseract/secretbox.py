"""Verschlüsselung von Geheimnissen in der Datenbank (z. B. Schlüssel des Zwischenzertifikats).

Der Hauptschlüssel kommt aus `TESSERACT_SECRET_KEY` (Base64, 32 Byte) oder wird beim ersten
Start als `secret.key` im Datenverzeichnis angelegt. Ohne ihn lassen sich die Daten nicht
entschlüsseln – er gehört ins Backup, aber getrennt von der Datenbank.
"""

import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from tesseract.config import Settings

_VERSION = b"v1"


class SecretBox:
    def __init__(self, key: bytes) -> None:
        if len(key) != 32:
            raise ValueError("Der Hauptschlüssel muss 32 Byte lang sein")
        self._aead = AESGCM(key)

    def encrypt(self, data: bytes, context: str = "") -> str:
        nonce = os.urandom(12)
        ct = self._aead.encrypt(nonce, data, context.encode())
        return (_VERSION + b":" + base64.b64encode(nonce + ct)).decode()

    def decrypt(self, token: str, context: str = "") -> bytes:
        version, _, payload = token.encode().partition(b":")
        if version != _VERSION:
            raise ValueError("Unbekanntes Format")
        raw = base64.b64decode(payload)
        return self._aead.decrypt(raw[:12], raw[12:], context.encode())


def load_secretbox(settings: Settings) -> SecretBox:
    if settings.secret_key:
        return SecretBox(base64.b64decode(settings.secret_key))
    path = Path(settings.data_dir) / "secret.key"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        key = AESGCM.generate_key(bit_length=256)
        # Datei nur für den eigenen Nutzer lesbar anlegen
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(base64.b64encode(key))
    return SecretBox(base64.b64decode(path.read_bytes().strip()))
