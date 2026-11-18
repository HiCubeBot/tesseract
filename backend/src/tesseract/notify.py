"""Phase 5: Benachrichtigungen per ntfy, Webhook und E-Mail.

Quelle ist das Audit-Log: Eine Hintergrundaufgabe liest neue Einträge, macht daraus Ereignisse
(z. B. `ip_banned` → „IP gesperrt“, Stufe Warnung) und verteilt sie nach den Regeln
Ereignis × Kanal. Gleiche Ereignisse werden pro Kanal gebündelt (höchstens eine Meldung pro
Zeitfenster, der Rest als Sammelmeldung), nachts kommen nur kritische sofort – der Rest wartet
bis zum Ende der Ruhezeit.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import smtplib
import ssl
import time
from dataclasses import dataclass, field
from datetime import datetime
from email.message import EmailMessage
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from tesseract.db.models import AuditEntry, Setting
from tesseract.secretbox import SecretBox

log = logging.getLogger("tesseract.notify")

LEVELS = ("info", "warn", "critical")
LEVEL_LABEL = {"info": "Info", "warn": "Warnung", "critical": "Kritisch"}
CHANNELS = ("ntfy", "email", "webhook")
SECRET_CONTEXT = "notify-secret"

# Ereignis → (Titel, Standard-Stufe, Audit-Aktionen)
EVENTS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "node_offline": ("Node offline", "critical", ("node_offline",)),
    "node_online": ("Node wieder online", "info", ("node_online",)),
    "config_failed": ("Config nicht übertragen", "critical", ("config_apply_failed",)),
    "node_drift": ("Node lokal geändert", "warn", ("node_drift_detected",)),
    "ip_banned": ("IP automatisch gesperrt", "warn", ("ip_banned",)),
    "login_failed": ("Fehlgeschlagene Anmeldung", "warn", ("login_failed",)),
    "enrollment": ("Gerät möchte sich registrieren", "info", ("enrollment_requested",)),
    "node_join": ("Agent möchte beitreten", "info", ("node_join_requested",)),
    "code_wrong": ("Falscher Einladungscode", "warn", ("enrollment_code_wrong",)),
    "backup_failed": ("Sicherung fehlgeschlagen", "critical", ("backup_failed",)),
    "device_expiring": ("Gerätezertifikat läuft ab", "warn", ("device_expiring",)),
    "ca_expiring": ("Zwischenzertifikat läuft ab", "critical", ("ca_expiring",)),
    "node_cert_expiring": ("Node-Zertifikat läuft ab", "warn", ("node_cert_expiring",)),
    "custom_cert_expiring": ("Eigenes Zertifikat läuft ab", "warn", ("custom_cert_expiring",)),
}
ACTION_EVENT = {a: ev for ev, (_, _, actions) in EVENTS.items() for a in actions}

DEFAULTS: dict[str, Any] = {
    "ntfy": {"enabled": False, "url": "", "token_enc": ""},
    "email": {
        "enabled": False,
        "host": "",
        "port": 587,
        "security": "starttls",  # starttls | ssl | none
        "user": "",
        "password_enc": "",
        "sender": "",
        "to": [],
    },
    "webhook": {"enabled": False, "url": "", "secret_enc": ""},
    # Ereignis → Kanäle (leer = aus); Stufe pro Ereignis anpassbar
    "rules": {ev: {"level": lvl, "channels": ["ntfy"]} for ev, (_, lvl, _) in EVENTS.items()},
    "quiet": {"enabled": True, "start": 22, "end": 7, "timezone": "Europe/Berlin"},
    "bundle_minutes": 15,
    # bis zu welchem Audit-Eintrag schon verarbeitet
    "cursor": 0,
}


def get_config(db: Session) -> dict[str, Any]:
    row = db.get(Setting, "notify")
    value = row.value if row else {}
    cfg = json.loads(json.dumps(DEFAULTS))
    for k, v in value.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    # neue Ereignisse späterer Versionen ergänzen
    for ev, (_, lvl, _) in EVENTS.items():
        cfg["rules"].setdefault(ev, {"level": lvl, "channels": ["ntfy"]})
    return cfg


def set_config(db: Session, value: dict[str, Any]) -> dict[str, Any]:
    cfg = {**get_config(db), **value}
    row = db.get(Setting, "notify")
    if row is None:
        db.add(Setting(key="notify", value=cfg))
    else:
        row.value = cfg
    return cfg


# ---------- Nachrichten ----------


@dataclass
class Message:
    event: str
    level: str
    title: str
    lines: list[str] = field(default_factory=list)
    at: float = field(default_factory=time.time)

    @property
    def text(self) -> str:
        if len(self.lines) <= 1:
            return self.lines[0] if self.lines else self.title
        shown = self.lines[:10]
        more = len(self.lines) - len(shown)
        return "\n".join(shown + ([f"… und {more} weitere"] if more else []))


def describe(e: AuditEntry) -> str:
    d = e.details or {}
    a = e.action
    if a == "ip_banned":
        why = (
            f"{d['hits']} WAF-Treffer auf {d.get('host') or '?'}"
            if d.get("hits")
            else d.get("reason", "von Hand")
        )
        return f"{e.target} gesperrt ({why}), {d.get('hours', '?')} Std."
    if a == "node_offline":
        return f"{e.target}: kein Kontakt seit {d.get('since', '?')}"
    if a == "node_online":
        return f"{e.target} meldet sich wieder"
    if a == "config_apply_failed":
        return f"{e.target}: {d.get('error', 'Fehler')}"
    if a == "node_drift_detected":
        return f"Die laufende Config auf {e.target} weicht vom Controller ab"
    if a == "login_failed":
        return f"Benutzer „{e.actor or '?'}“ von {e.ip or '?'}"
    if a == "enrollment_requested":
        return f"{e.target} – im Controller freigeben"
    if a == "node_join_requested":
        return f"Node {e.target} ({d.get('hostname') or '?'}) – Fingerabdruck vergleichen"
    if a in ("device_expiring", "ca_expiring", "node_cert_expiring", "custom_cert_expiring"):
        days = d.get("days", "?")
        hint = {
            "device_expiring": "Gerät unter Geräte verlängern",
            "ca_expiring": "Unter Zertifizierungsstelle auf ein neues wechseln",
            "node_cert_expiring": "Der Agent erneuert es selbst – meldet er sich noch?",
            "custom_cert_expiring": "Unter Zertifikate erneuern",
        }[a]
        return f"{e.target}: noch {days} Tage – {hint}"
    if a == "backup_failed":
        return f"Sicherung fehlgeschlagen: {d.get('error', '?')}"
    if a == "enrollment_code_wrong":
        return f"Einladung für {e.target} von {e.ip or '?'}"
    return f"{e.action} {e.target}".strip()


# ---------- Kanäle ----------


class Sender:
    """Verschickt eine Nachricht über einen Kanal. In Tests ersetzbar."""

    def __init__(self, box: SecretBox, transport: httpx.BaseTransport | None = None) -> None:
        self.box = box
        self.transport = transport
        self.smtp_factory = smtplib.SMTP
        self.smtp_ssl_factory = smtplib.SMTP_SSL

    def _secret(self, enc: str) -> str:
        return self.box.decrypt(enc, SECRET_CONTEXT).decode() if enc else ""

    def send(self, channel: str, cfg: dict[str, Any], msg: Message) -> None:
        getattr(self, f"_{channel}")(cfg[channel], msg)

    def _http(self) -> httpx.Client:
        return httpx.Client(timeout=15.0, transport=self.transport)

    def _ntfy(self, c: dict[str, Any], msg: Message) -> None:
        headers = {
            # UTF-8 im Titel über RFC-2047-Kodierung (versteht ntfy)
            "Title": "=?UTF-8?B?" + _b64(f"Tesseract: {msg.title}") + "?=",
            "Priority": {"info": "3", "warn": "4", "critical": "5"}[msg.level],
            "Tags": {"info": "information_source", "warn": "warning", "critical": "rotating_light"}[
                msg.level
            ],
        }
        token = self._secret(c.get("token_enc", ""))
        if token:
            headers["Authorization"] = f"Bearer {token}"
        with self._http() as h:
            r = h.post(c["url"], content=msg.text.encode(), headers=headers)
        r.raise_for_status()

    def _webhook(self, c: dict[str, Any], msg: Message) -> None:
        body = json.dumps(
            {
                "source": "tesseract",
                "event": msg.event,
                "level": msg.level,
                "title": msg.title,
                "message": msg.text,
                "items": msg.lines,
                "time": datetime.fromtimestamp(msg.at).astimezone().isoformat(),
            },
            ensure_ascii=False,
        ).encode()
        headers = {"Content-Type": "application/json"}
        secret = self._secret(c.get("secret_enc", ""))
        if secret:
            sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            headers["X-Tesseract-Signature"] = f"sha256={sig}"
        with self._http() as h:
            r = h.post(c["url"], content=body, headers=headers)
        r.raise_for_status()

    def _email(self, c: dict[str, Any], msg: Message) -> None:
        m = EmailMessage()
        m["Subject"] = f"[Tesseract] {LEVEL_LABEL[msg.level]}: {msg.title}"
        m["From"] = c["sender"] or c["user"]
        m["To"] = ", ".join(c["to"])
        m.set_content(msg.text + "\n\n– Tesseract")
        password = self._secret(c.get("password_enc", ""))
        ctx = ssl.create_default_context()
        if c["security"] == "ssl":
            server = self.smtp_ssl_factory(c["host"], int(c["port"]), timeout=20, context=ctx)
        else:
            server = self.smtp_factory(c["host"], int(c["port"]), timeout=20)
        with server as s:
            if c["security"] == "starttls":
                s.starttls(context=ctx)
            if c["user"]:
                s.login(c["user"], password)
            s.send_message(m)


def _b64(text: str) -> str:
    import base64

    return base64.b64encode(text.encode()).decode()


# ---------- Verteilen, Bündeln, Ruhezeit ----------


def in_quiet(cfg: dict[str, Any], now: datetime | None = None) -> bool:
    q = cfg["quiet"]
    if not q.get("enabled"):
        return False
    try:
        tz = ZoneInfo(q.get("timezone") or "Europe/Berlin")
    except Exception:  # pragma: no cover
        tz = ZoneInfo("UTC")
    hour = (now or datetime.now(tz)).astimezone(tz).hour
    start, end = int(q["start"]), int(q["end"])
    return (start <= hour or hour < end) if start > end else (start <= hour < end)


class Notifier:
    def __init__(self, sender: Sender, clock=time.time) -> None:
        self.sender = sender
        self.clock = clock
        # (Kanal, Ereignis) → letzte Sendung; wartende Nachrichten
        self.last_sent: dict[tuple[str, str], float] = {}
        self.pending: dict[tuple[str, str], Message] = {}
        self.errors: dict[str, str] = {}

    def collect(self, db: Session, cfg: dict[str, Any]) -> int:
        """Neue Audit-Einträge in wartende Nachrichten einsortieren."""
        cursor = int(cfg.get("cursor") or 0)
        if cursor == 0:
            # Erster Lauf: nicht die ganze Vergangenheit melden
            last = db.scalar(select(AuditEntry.id).order_by(AuditEntry.id.desc()).limit(1)) or 0
            set_config(db, {"cursor": last})
            db.commit()
            return 0
        entries = list(
            db.scalars(
                select(AuditEntry).where(AuditEntry.id > cursor).order_by(AuditEntry.id).limit(1000)
            )
        )
        if not entries:
            return 0
        n = 0
        for e in entries:
            ev = ACTION_EVENT.get(e.action)
            if ev is None or (e.action == "ip_banned" and e.actor != "system"):
                continue  # eigene Sperren von Hand nicht melden
            rule = cfg["rules"].get(ev) or {}
            for ch in rule.get("channels", []):
                if ch not in CHANNELS or not cfg[ch].get("enabled"):
                    continue
                key = (ch, ev)
                msg = self.pending.get(key)
                if msg is None:
                    msg = self.pending[key] = Message(
                        ev, rule.get("level", "info"), EVENTS[ev][0], at=self.clock()
                    )
                msg.lines.append(describe(e))
                n += 1
        set_config(db, {"cursor": entries[-1].id})
        db.commit()
        return n

    def due(self, cfg: dict[str, Any], now: float | None = None) -> list[tuple[str, Message]]:
        """Was jetzt raus darf: Bündelfenster abgelaufen und keine Ruhezeit (außer kritisch)."""
        now = self.clock() if now is None else now
        window = max(0, int(cfg.get("bundle_minutes") or 0)) * 60
        quiet = in_quiet(cfg)
        out = []
        for key, msg in list(self.pending.items()):
            ch, ev = key
            if quiet and msg.level != "critical":
                continue
            if now - self.last_sent.get(key, 0.0) < window and msg.level != "critical":
                continue
            out.append((ch, msg))
            del self.pending[key]
            self.last_sent[key] = now
        return out

    def flush(self, cfg: dict[str, Any]) -> int:
        sent = 0
        for ch, msg in self.due(cfg):
            try:
                self.sender.send(ch, cfg, msg)
                self.errors.pop(ch, None)
                sent += 1
            except Exception as e:  # noqa: BLE001 – jeder Kanalfehler wird gemeldet, nicht geworfen
                self.errors[ch] = str(e)[:300]
                log.warning("Benachrichtigung über %s fehlgeschlagen: %s", ch, e)
        return sent


async def watch(database, notifier: Notifier, interval: float = 10.0) -> None:
    from tesseract.audit import seal

    while True:
        try:
            with database.sessionmaker() as db:
                seal(db)
                cfg = get_config(db)
                notifier.collect(db, cfg)
                await asyncio.to_thread(notifier.flush, cfg)
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover – die Schleife darf nie sterben
            log.exception("Benachrichtigungen: Fehler")
        await asyncio.sleep(interval)
