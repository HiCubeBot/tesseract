"""Datenmodell des Controllers."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Speichert UTC ohne Zeitzone (SQLite) und liefert immer zeitzonenbewusste Werte."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        return None if value is None else value.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, datetime: UTCDateTime}


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    password_changed_at: Mapped[datetime] = mapped_column(default=utcnow)
    # "local" (Passwort/Passkey) oder "oidc" (Anmeldung über SSO, kein Passwort)
    source: Mapped[str] = mapped_column(String(16), default="local")
    # OIDC: Aussteller + „sub“ – eindeutig je Anbieter
    oidc_subject: Mapped[str | None] = mapped_column(String(512), unique=True)
    email: Mapped[str | None] = mapped_column(String(255))
    last_login_at: Mapped[datetime | None]

    passkeys: Mapped[list["AdminPasskey"]] = relationship(
        back_populates="admin", cascade="all, delete-orphan", order_by="AdminPasskey.id"
    )


class AdminPasskey(Base):
    """Passkey (WebAuthn) eines Admins – Anmeldung ohne Passwort."""

    __tablename__ = "admin_passkeys"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admins.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(64))
    # Base64url der Credential-ID
    credential_id: Mapped[str] = mapped_column(String(1024), unique=True)
    public_key: Mapped[bytes]
    sign_count: Mapped[int] = mapped_column(default=0)
    transports: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_used_at: Mapped[datetime | None]

    admin: Mapped[Admin] = relationship(back_populates="passkeys")


class AdminSession(Base):
    __tablename__ = "admin_sessions"

    # SHA-256 des Session-Tokens – das Token selbst steht nur im Cookie
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admins.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime]
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))

    admin: Mapped[Admin] = relationship()


class Node(Base):
    """Ein Caddy-Server: der lokale im Compose-Stack oder ein entfernter mit Agent (Phase 4)."""

    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    location: Mapped[str] = mapped_column(String(128), default="")
    # "local" = Controller spricht direkt mit der Admin-API, "agent" = Agent holt die Config ab
    kind: Mapped[str] = mapped_column(String(16), default="local")
    admin_url: Mapped[str] = mapped_column(String(255), default="")
    # Adresse der Admin-API in der erzeugten Config (None = TESSERACT_CADDY_ADMIN_LISTEN)
    admin_listen: Mapped[str | None] = mapped_column(String(255))
    # Öffentliche IPs des Servers – „Host anlegen“ prüft, ob der DNS-Eintrag dorthin zeigt
    public_ips: Mapped[list[str] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_applied_at: Mapped[datetime | None]
    last_apply_error: Mapped[str | None]
    # Prüfsumme der zuletzt übertragenen (beim Agent: geladenen) Config
    applied_hash: Mapped[str | None] = mapped_column(String(64))

    # --- Agent: Beitritt ---
    # SHA-256 des Beitritts-Tokens (einmalig, 30 Min.)
    join_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    join_expires_at: Mapped[datetime | None]
    # Anfrage des Agents: CSR, Rechnername, Fingerabdruck seines öffentlichen Schlüssels
    join_csr: Mapped[str | None]
    join_key_fp: Mapped[str | None] = mapped_column(String(64))
    join_hostname: Mapped[str | None] = mapped_column(String(255))
    join_requested_at: Mapped[datetime | None]
    # SHA-256 des Geheimnisses, mit dem der Agent nach der Bestätigung sein Zertifikat abholt
    join_secret_hash: Mapped[str | None] = mapped_column(String(64))
    # "pending" | "approved" | "rejected" (None = keine Anfrage)
    join_state: Mapped[str | None] = mapped_column(String(16))

    # --- Agent: Identität ---
    cert_pem: Mapped[str | None]
    cert_fingerprint: Mapped[str | None] = mapped_column(String(64), unique=True)
    cert_not_after: Mapped[datetime | None]
    # SHA-256 des Agent-Tokens (zusätzlich zum Zertifikat)
    agent_token_hash: Mapped[str | None] = mapped_column(String(64))

    # --- Status (vom Agent gemeldet bzw. vom Controller beim lokalen Node ermittelt) ---
    last_seen_at: Mapped[datetime | None]
    agent_version: Mapped[str | None] = mapped_column(String(32))
    caddy_version: Mapped[str | None] = mapped_column(String(64))
    # Adresse, unter der der Agent den Controller erreicht, und IP, von der er kommt
    controller_url: Mapped[str | None] = mapped_column(String(255))
    agent_ip: Mapped[str | None] = mapped_column(String(64))
    # Erkannte Caddy-Module (None = noch nicht geprüft)
    modules: Mapped[list[str] | None] = mapped_column(JSON)
    # Config, die der Controller für den Node vorsieht (Agent holt sie ab)
    desired_hash: Mapped[str | None] = mapped_column(String(64))
    # Hochzählen = Agent soll neu laden, auch wenn sich nichts geändert hat („Überschreiben“)
    force_seq: Mapped[int] = mapped_column(default=0)

    # --- Abweichung ---
    # Prüfsumme der Config, die gerade wirklich in Caddy läuft
    running_hash: Mapped[str | None] = mapped_column(String(64))
    # die laufende Config, nur gespeichert, solange sie abweicht
    running_config: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    drift_since: Mapped[datetime | None]
    # „Änderung übernehmen“: diese laufende Config gilt als in Ordnung
    accepted_hash: Mapped[str | None] = mapped_column(String(64))

    @property
    def is_agent(self) -> bool:
        return self.kind == "agent"

    @property
    def joined(self) -> bool:
        return not self.is_agent or self.cert_fingerprint is not None

    @property
    def drift(self) -> bool:
        return (
            self.running_hash is not None
            and self.applied_hash is not None
            and self.running_hash != self.applied_hash
            and self.running_hash != self.accepted_hash
        )


class Host(Base):
    __tablename__ = "hosts"

    id: Mapped[int] = mapped_column(primary_key=True)
    domain: Mapped[str] = mapped_column(String(253), unique=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"))
    upstream_scheme: Mapped[str] = mapped_column(String(5), default="http")
    upstream_host: Mapped[str] = mapped_column(String(253))
    upstream_port: Mapped[int]
    # https zum Ziel ohne Prüfung des Zertifikats (selbst signiert, z. B. Proxmox, Unifi)
    upstream_insecure: Mapped[bool] = mapped_column(default=False)
    websockets: Mapped[bool] = mapped_column(default=True)
    force_https: Mapped[bool] = mapped_column(default=True)
    compression: Mapped[bool] = mapped_column(default=False)
    # "public" oder "mtls"
    access: Mapped[str] = mapped_column(String(16), default="public")
    # Verhalten ohne gültiges Zertifikat: "reject" (TLS-Handshake scheitert) oder "hint"
    no_cert_action: Mapped[str] = mapped_column(String(16), default="reject")
    # Coraza WAF: "off" | "detect" (nur protokollieren) | "block"
    waf_mode: Mapped[str] = mapped_column(String(16), default="off")
    waf_paranoia: Mapped[int] = mapped_column(default=1)
    # Regel-IDs, die für diesen Host abgeschaltet sind (Fehlalarme)
    waf_exclusions: Mapped[list[int]] = mapped_column(JSON, default=list)
    # IP-Filter: "off" | "block" (Liste sperren) | "allow" (nur Liste erlauben)
    ip_mode: Mapped[str] = mapped_column(String(16), default="off")
    # einzelne IPs/Netze (CIDR) und IDs benannter IP-Listen
    ip_entries: Mapped[list[str]] = mapped_column(JSON, default=list)
    ip_list_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    # Login über Authelia vor dem Dienst (forward_auth)
    authelia: Mapped[bool] = mapped_column(default=False)
    # ACME-Prüfung: "http" (HTTP-01, Port 80) oder "dns" (DNS-01 über Cloudflare, auch Wildcards)
    tls_challenge: Mapped[str] = mapped_column(String(8), default="http")
    # Nur aus internen Netzen (LAN/VPN) erreichbar – alle anderen: Verbindung abbrechen
    internal: Mapped[bool] = mapped_column(default=False)
    # Zertifikatspflicht (mTLS) gilt nicht für Anfragen aus den internen Netzen
    internal_no_cert: Mapped[bool] = mapped_column(default=False, server_default="0")
    # mTLS: Tesseract selbst (Controller-Zertifikat) darf zugreifen, z. B. für ntfy
    allow_controller: Mapped[bool] = mapped_column(default=False, server_default="0")
    # Uptime-Monitor: Ziel regelmäßig prüfen; auf der öffentlichen Statusseite zeigen (mit Name)
    monitor: Mapped[bool] = mapped_column(default=True, server_default="1")
    status_public: Mapped[bool] = mapped_column(default=False, server_default="0")
    status_name: Mapped[str] = mapped_column(String(64), default="", server_default="")
    # robots.txt von Caddy: off | allow | deny | deny_ai | paths | custom (siehe robots.py)
    robots: Mapped[str] = mapped_column(String(16), default="off", server_default="off")
    robots_paths: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    robots_sitemap: Mapped[str] = mapped_column(String(500), default="", server_default="")
    robots_text: Mapped[str] = mapped_column(Text, default="", server_default="")
    # Eigenes Zertifikat statt automatisch (Let's Encrypt/Caddy-CA)
    custom_cert_id: Mapped[int | None] = mapped_column(
        ForeignKey("custom_certs.id", ondelete="SET NULL")
    )
    # Entwürfe werden gespeichert, aber nicht an Caddy übertragen
    draft: Mapped[bool] = mapped_column(default=False)
    enabled: Mapped[bool] = mapped_column(default=True)
    # Herkunft: "ui" (Oberfläche/API) oder "docker" (Container-Labels, siehe dockerlabels.py)
    source: Mapped[str] = mapped_column(String(16), default="ui", server_default="ui")
    # bei Docker: "<node_id>:<Container-Name>"
    source_ref: Mapped[str | None] = mapped_column(String(255))
    # Prüfsumme der zuletzt übernommenen Labels
    source_hash: Mapped[str | None] = mapped_column(String(64))
    # von der Docker-Anbindung abgeschaltet (Container gestoppt/entfernt)
    source_disabled: Mapped[bool] = mapped_column(default=False, server_default="0")
    # DNS-Eintrag bei Cloudflare (dnsrecords.py): None = keiner, "cname" oder "address" (A/AAAA)
    dns_type: Mapped[str | None] = mapped_column(String(16))
    # leer = Wert der Zone; bei "address" IPs kommagetrennt
    dns_target: Mapped[str] = mapped_column(String(500), default="", server_default="")
    dns_proxied: Mapped[bool] = mapped_column(default=False, server_default="0")
    # von Tesseract angelegte Einträge (IDs bei Cloudflare) und letzter Fehler
    dns_records: Mapped[list[dict] | None] = mapped_column(JSON)
    dns_error: Mapped[str | None] = mapped_column(String(1000))
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    node: Mapped[Node] = relationship()
    versions: Mapped[list["HostVersion"]] = relationship(
        back_populates="host", cascade="all, delete-orphan", order_by="HostVersion.version"
    )
    # Pfade mit abweichendem Zugriff: bei "public" geschützt, bei "mtls" öffentlich
    paths: Mapped[list["HostPath"]] = relationship(
        cascade="all, delete-orphan", order_by="HostPath.position"
    )
    grants: Mapped[list["HostGrant"]] = relationship(cascade="all, delete-orphan")
    areas: Mapped[list["HostArea"]] = relationship(
        cascade="all, delete-orphan", order_by="HostArea.position"
    )


class HostVersion(Base):
    """Jede gespeicherte Änderung eines Hosts – nichts wird überschrieben."""

    __tablename__ = "host_versions"
    __table_args__ = (UniqueConstraint("host_id", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    host_id: Mapped[int] = mapped_column(ForeignKey("hosts.id", ondelete="CASCADE"))
    version: Mapped[int]
    snapshot: Mapped[dict[str, Any]]
    actor: Mapped[str] = mapped_column(String(64))
    comment: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    host: Mapped[Host] = relationship(back_populates="versions")


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict[str, Any]]


class AuditEntry(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64), index=True)
    target: Mapped[str] = mapped_column(String(255), default="")
    details: Mapped[dict[str, Any]] = mapped_column(default=dict)
    ip: Mapped[str | None] = mapped_column(String(64))
    # Phase 5: Kette – siehe tesseract.audit
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    hash: Mapped[str | None] = mapped_column(String(64), index=True)


# ---------- Phase 2: PKI und Identitäten ----------


class Authority(Base):
    """Root- und Zwischenzertifikat. Der Root-Schlüssel wird nie gespeichert."""

    __tablename__ = "authorities"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # "root" | "intermediate"
    cert_pem: Mapped[str]
    # verschlüsselt mit dem Hauptschlüssel (secretbox); None beim Root
    key_enc: Mapped[str | None]
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    not_before: Mapped[datetime]
    not_after: Mapped[datetime]
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class PersonGroup(Base):
    __tablename__ = "person_groups"

    person_id: Mapped[int] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True
    )
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True
    )


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(String(255), default="")
    # eingebaute Gruppen (z. B. "Admin") lassen sich nicht löschen
    builtin: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    # Aus LDAP übernommen (DN); Mitglieder pflegt dann der Abgleich
    ldap_dn: Mapped[str | None] = mapped_column(String(1024), unique=True)

    persons: Mapped[list["Person"]] = relationship(
        secondary="person_groups", back_populates="groups", order_by="Person.name"
    )


class Person(Base):
    """Rechte gehören zur Person; jedes ihrer Geräte hat ein eigenes Zertifikat."""

    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    note: Mapped[str] = mapped_column(String(255), default="")
    max_devices: Mapped[int] = mapped_column(default=3)
    disabled: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    email: Mapped[str | None] = mapped_column(String(255))
    # Aus LDAP übernommen (DN); Name, E-Mail, LDAP-Gruppen und Sperre kommen dann von dort
    ldap_dn: Mapped[str | None] = mapped_column(String(1024), unique=True)
    # Zugriff auf Tesseract nur per Gerätezertifikat: none | read | own | admin (uiaccess.py)
    ui_role: Mapped[str] = mapped_column(String(8), default="none", server_default="none")

    groups: Mapped[list[Group]] = relationship(
        secondary="person_groups", back_populates="persons", order_by="Group.name"
    )
    devices: Mapped[list["Device"]] = relationship(
        back_populates="person", cascade="all, delete-orphan", order_by="Device.created_at"
    )


class Device(Base):
    """Ein Gerät = ein Client-Zertifikat. Die .p12 (mit Schlüssel) und ihr Passwort liegen
    verschlüsselt vor, solange „Zertifikate zum erneuten Abruf aufbewahren“ an ist."""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(64))
    platform: Mapped[str] = mapped_column(String(32), default="")
    serial: Mapped[str] = mapped_column(String(64))
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    cert_pem: Mapped[str]
    not_before: Mapped[datetime]
    not_after: Mapped[datetime]
    unlimited: Mapped[bool] = mapped_column(default=False)
    # .p12 und Passwort verschlüsselt (SecretBox), für späteres Herunterladen
    p12_enc: Mapped[str | None]
    p12_password_enc: Mapped[str | None] = mapped_column(String(255))
    revoked_at: Mapped[datetime | None]
    revoke_reason: Mapped[str] = mapped_column(String(255), default="")
    last_seen_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    person: Mapped[Person] = relationship(back_populates="devices")

    @property
    def status(self) -> str:
        if self.revoked_at is not None:
            return "revoked"
        if self.not_after <= utcnow():
            return "expired"
        return "active"


# ---------- Phase 2: Zugriff auf Hosts ----------


class HostPath(Base):
    __tablename__ = "host_paths"

    id: Mapped[int] = mapped_column(primary_key=True)
    host_id: Mapped[int] = mapped_column(ForeignKey("hosts.id", ondelete="CASCADE"))
    path: Mapped[str] = mapped_column(String(255))
    position: Mapped[int] = mapped_column(default=0)


class HostGrant(Base):
    """Freigabe eines Hosts für eine Gruppe oder eine Person (genau eins von beiden)."""

    __tablename__ = "host_grants"
    __table_args__ = (UniqueConstraint("host_id", "group_id", "person_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    host_id: Mapped[int] = mapped_column(ForeignKey("hosts.id", ondelete="CASCADE"))
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    person_id: Mapped[int | None] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"))

    group: Mapped[Group | None] = relationship()
    person: Mapped[Person | None] = relationship()


# ---------- Phase 2: Einladungen ----------


class Invite(Base):
    """Einladungslink für eine Person. Token und Code liegen verschlüsselt vor,
    gesucht wird über den Hash des Tokens."""

    __tablename__ = "invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    token_enc: Mapped[str]
    code_enc: Mapped[str]
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    failed_attempts: Mapped[int] = mapped_column(default=0)

    person: Mapped[Person] = relationship()
    enrollments: Mapped[list["Enrollment"]] = relationship(
        back_populates="invite", cascade="all, delete-orphan", order_by="Enrollment.id"
    )


class Enrollment(Base):
    """Registrierungsanfrage eines Geräts über eine Einladung."""

    __tablename__ = "enrollments"

    id: Mapped[int] = mapped_column(primary_key=True)
    invite_id: Mapped[int] = mapped_column(ForeignKey("invites.id", ondelete="CASCADE"))
    device_name: Mapped[str] = mapped_column(String(64))
    platform: Mapped[str] = mapped_column(String(32), default="")
    user_agent: Mapped[str] = mapped_column(String(255), default="")
    ip: Mapped[str | None] = mapped_column(String(64))
    # Hash des Geheimnisses, mit dem der Gast den Status abfragt
    secret_hash: Mapped[str] = mapped_column(String(64))
    # pending → approved → delivered · oder rejected
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    decided_at: Mapped[datetime | None]
    decided_by: Mapped[str | None] = mapped_column(String(64))
    delivered_at: Mapped[datetime | None]
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"))

    invite: Mapped[Invite] = relationship(back_populates="enrollments")


# ---------- Phase 3: IP-Listen ----------


class IpList(Base):
    """Benannte Liste von IPs/Netzen, z. B. „Heimnetz“, „Scanner“ oder „Cloudflare“."""

    __tablename__ = "ip_lists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(String(255), default="")
    entries: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


# ---------- Phase 3: Host-Bereiche ----------


class HostArea(Base):
    """Pfade eines Hosts mit abweichenden Regeln. None = wie beim Host."""

    __tablename__ = "host_areas"

    id: Mapped[int] = mapped_column(primary_key=True)
    host_id: Mapped[int] = mapped_column(ForeignKey("hosts.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(default=0)
    name: Mapped[str] = mapped_column(String(64), default="")
    paths: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Zugriff: None | "public" | "mtls" (mit eigenen Freigaben, leer = wie Host)
    access: Mapped[str | None] = mapped_column(String(16))
    grant_group_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    grant_person_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    waf_mode: Mapped[str | None] = mapped_column(String(16))
    # zusätzliche Regel-Ausnahmen nur für diesen Bereich
    waf_exclusions: Mapped[list[int]] = mapped_column(JSON, default=list)
    authelia: Mapped[bool | None]
    ip_mode: Mapped[str | None] = mapped_column(String(16))
    ip_entries: Mapped[list[str]] = mapped_column(JSON, default=list)
    ip_list_ids: Mapped[list[int]] = mapped_column(JSON, default=list)


# ---------- Phase 3: Auto-Sperre ----------


class Ban(Base):
    """Gesperrte IP – automatisch nach WAF-Treffern oder von Hand."""

    __tablename__ = "bans"

    id: Mapped[int] = mapped_column(primary_key=True)
    ip: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime | None]  # leer = dauerhaft
    reason: Mapped[str] = mapped_column(String(255), default="")
    hits: Mapped[int] = mapped_column(default=0)
    host: Mapped[str] = mapped_column(String(253), default="")
    created_by: Mapped[str] = mapped_column(String(64), default="system")
    lifted_at: Mapped[datetime | None]
    lifted_by: Mapped[str | None] = mapped_column(String(64))


# ---------- Phase 3b: Eigene Zertifikate ----------


class CustomCert(Base):
    """Hochgeladenes Zertifikat (z. B. von einer Firmen-CA). Schlüssel verschlüsselt."""

    __tablename__ = "custom_certs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    # Zertifikat inkl. Zwischenzertifikaten (PEM)
    cert_pem: Mapped[str]
    key_enc: Mapped[str]
    names: Mapped[list[str]] = mapped_column(JSON, default=list)
    issuer: Mapped[str] = mapped_column(String(255), default="")
    fingerprint: Mapped[str] = mapped_column(String(64))
    not_before: Mapped[datetime]
    not_after: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


# ---------- Phase 5: Logs ----------


class LogEntry(Base):
    """Ein Eintrag aus Caddys Zugriffs-Log eines Nodes, ergänzt um Grund, WAF-Regeln, Gerät."""

    __tablename__ = "log_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(index=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"), index=True)
    host: Mapped[str] = mapped_column(String(253), index=True)
    method: Mapped[str] = mapped_column(String(16), default="")
    uri: Mapped[str] = mapped_column(String(2048), default="")
    status: Mapped[int] = mapped_column(default=0)
    duration_ms: Mapped[float] = mapped_column(default=0.0)
    # Bytes der Antwort
    size: Mapped[int] = mapped_column(default=0)
    # Bytes der Anfrage (Body), HTTP-Version (1.1, 2, 3) und Kompression der Antwort
    bytes_in: Mapped[int] = mapped_column(default=0, server_default="0")
    proto: Mapped[str | None] = mapped_column(String(8))
    encoding: Mapped[str | None] = mapped_column(String(16))
    ip: Mapped[str] = mapped_column(String(64), index=True)
    country: Mapped[str | None] = mapped_column(String(2))
    # mit Stadt-Datenbank: Stadt und Koordinaten (auf ~1 km gerundet); mit ASN-Datenbank:
    # Netzbetreiber
    city: Mapped[str | None] = mapped_column(String(64))
    lat: Mapped[float | None]
    lon: Mapped[float | None]
    asn: Mapped[int | None]
    as_org: Mapped[str | None] = mapped_column(String(128))
    device_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), index=True
    )
    # ok | waf | ip | ban | mtls | internal | websocket | authelia
    reason: Mapped[str] = mapped_column(String(16), default="ok", index=True)
    # WAF: ausgelöste Regeln (auch im Modus „nur protokollieren“), Meldung, Anomalie-Score
    waf_rules: Mapped[list[int]] = mapped_column(JSON, default=list)
    waf_msg: Mapped[str | None] = mapped_column(String(255))
    waf_score: Mapped[int | None]
    user_agent: Mapped[str | None] = mapped_column(String(255))


class StatsDaily(Base):
    """Tageswerte je Host und Node – bleiben, wenn die Logs nach `logs_days` gelöscht werden.

    Grundlage für „Gesamter Zeitraum“ und die Rekorde. Zähler als Spalten, Verteilungen
    (Statuscodes, Clients) als JSON {Wert: Anzahl}."""

    __tablename__ = "stats_daily"

    day: Mapped[str] = mapped_column(String(10), primary_key=True)  # YYYY-MM-DD (UTC)
    host: Mapped[str] = mapped_column(String(253), primary_key=True)
    node: Mapped[str] = mapped_column(String(64), primary_key=True)
    requests: Mapped[int] = mapped_column(default=0)
    denied: Mapped[int] = mapped_column(default=0)
    mtls: Mapped[int] = mapped_column(default=0)
    waf: Mapped[int] = mapped_column(default=0)
    ipfilter: Mapped[int] = mapped_column(default=0)
    s2xx: Mapped[int] = mapped_column(default=0)
    s3xx: Mapped[int] = mapped_column(default=0)
    s4xx: Mapped[int] = mapped_column(default=0)
    s5xx: Mapped[int] = mapped_column(default=0)
    bytes_out: Mapped[int] = mapped_column(default=0)
    bytes_in: Mapped[int] = mapped_column(default=0)
    http1: Mapped[int] = mapped_column(default=0)
    http2: Mapped[int] = mapped_column(default=0)
    http3: Mapped[int] = mapped_column(default=0)
    browser: Mapped[int] = mapped_column(default=0)
    app: Mapped[int] = mapped_column(default=0)
    bot: Mapped[int] = mapped_column(default=0)
    compressed: Mapped[int] = mapped_column(default=0)
    compressible: Mapped[int] = mapped_column(default=0)
    visitors: Mapped[int] = mapped_column(default=0)
    median_ms: Mapped[float | None]
    codes: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    clients: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)


class StatsHourly(Base):
    """Stundenwerte über alle Hosts (für Rekorde wie „stärkste Stunde“)."""

    __tablename__ = "stats_hourly"

    hour: Mapped[datetime] = mapped_column(primary_key=True)
    requests: Mapped[int] = mapped_column(default=0)
    denied: Mapped[int] = mapped_column(default=0)
    bytes_out: Mapped[int] = mapped_column(default=0)
    top_host: Mapped[str | None] = mapped_column(String(253))
    top_denied_host: Mapped[str | None] = mapped_column(String(253))


class VisitorIp(Base):
    """Jede IP, die je eine Antwort bekam (ohne Bots) – für „verschiedene Adressen“ insgesamt."""

    __tablename__ = "visitor_ips"

    ip: Mapped[str] = mapped_column(String(64), primary_key=True)
    first_day: Mapped[str] = mapped_column(String(10))
    last_day: Mapped[str] = mapped_column(String(10))


class MonitorState(Base):
    """Aktueller Stand des Uptime-Monitors je Node bzw. Host."""

    __tablename__ = "monitor_state"

    kind: Mapped[str] = mapped_column(String(8), primary_key=True)  # node | host
    ref: Mapped[str] = mapped_column(String(253), primary_key=True)  # Name bzw. Domain
    status: Mapped[str] = mapped_column(String(8), default="unknown")  # up | down | unknown
    since: Mapped[datetime] = mapped_column(default=utcnow)
    checked_at: Mapped[datetime | None]
    ms: Mapped[float | None]
    error: Mapped[str | None] = mapped_column(String(255))


class UptimeDaily(Base):
    """Prüfungen je Tag (UTC): Anzahl, davon erreichbar, Ausfallzeit in Sekunden."""

    __tablename__ = "uptime_daily"

    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    kind: Mapped[str] = mapped_column(String(8), primary_key=True)
    ref: Mapped[str] = mapped_column(String(253), primary_key=True)
    checks: Mapped[int] = mapped_column(default=0)
    up: Mapped[int] = mapped_column(default=0)
    down_seconds: Mapped[int] = mapped_column(default=0)
    outages: Mapped[int] = mapped_column(default=0)


class Incident(Base):
    """Ein Ausfall: von – bis (offen, solange er andauert)."""

    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(8), index=True)
    ref: Mapped[str] = mapped_column(String(253), index=True)
    started_at: Mapped[datetime] = mapped_column(index=True)
    ended_at: Mapped[datetime | None]
    error: Mapped[str | None] = mapped_column(String(255))
