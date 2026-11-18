"""Datenmodell des Controllers."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, TypeDecorator, UniqueConstraint
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
    """Ein Caddy-Server. In Phase 1 gibt es genau einen lokalen Node."""

    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    location: Mapped[str] = mapped_column(String(128), default="")
    admin_url: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_applied_at: Mapped[datetime | None]
    last_apply_error: Mapped[str | None]
    # Prüfsumme der zuletzt übertragenen Config
    applied_hash: Mapped[str | None] = mapped_column(String(64))


class Host(Base):
    __tablename__ = "hosts"

    id: Mapped[int] = mapped_column(primary_key=True)
    domain: Mapped[str] = mapped_column(String(253), unique=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"))
    upstream_scheme: Mapped[str] = mapped_column(String(5), default="http")
    upstream_host: Mapped[str] = mapped_column(String(253))
    upstream_port: Mapped[int]
    websockets: Mapped[bool] = mapped_column(default=True)
    force_https: Mapped[bool] = mapped_column(default=True)
    compression: Mapped[bool] = mapped_column(default=False)
    # "public" oder "mtls"
    access: Mapped[str] = mapped_column(String(16), default="public")
    # Verhalten ohne gültiges Zertifikat: "reject" (TLS-Handshake scheitert) oder "hint"
    no_cert_action: Mapped[str] = mapped_column(String(16), default="reject")
    # Entwürfe werden gespeichert, aber nicht an Caddy übertragen
    draft: Mapped[bool] = mapped_column(default=False)
    enabled: Mapped[bool] = mapped_column(default=True)
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

    groups: Mapped[list[Group]] = relationship(
        secondary="person_groups", back_populates="persons", order_by="Group.name"
    )
    devices: Mapped[list["Device"]] = relationship(
        back_populates="person", cascade="all, delete-orphan", order_by="Device.created_at"
    )


class Device(Base):
    """Ein Gerät = ein Client-Zertifikat. Der private Schlüssel wird nie gespeichert."""

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
