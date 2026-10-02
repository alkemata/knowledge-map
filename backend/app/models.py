import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    reader = "reader"
    contributor = "contributor"
    editor = "editor"
    administrator = "administrator"


class IdentityType(str, enum.Enum):
    human = "human"
    agent = "agent"


class ContentStatus(str, enum.Enum):
    draft = "draft"
    review = "review"
    published = "published"
    archived = "archived"


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"), default=Role.reader)
    identity_type: Mapped[IdentityType] = mapped_column(Enum(IdentityType, name="identity_type"), default=IdentityType.human)
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str | None] = mapped_column(Text)
    external_subject: Mapped[str | None] = mapped_column(String(320), unique=True)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BrowserSession(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    hashed_token: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship()


class AgentCredential(Base):
    __tablename__ = "agent_credentials"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    hashed_token: Mapped[str] = mapped_column(String(64), unique=True)
    prefix: Mapped[str] = mapped_column(String(16), index=True)
    scopes: Mapped[list[str]] = mapped_column(JSONB, default=list)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user: Mapped[User] = relationship()


class KnowledgeMap(Base):
    __tablename__ = "maps"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    coordinate_version: Mapped[int] = mapped_column(Integer, default=1)
    default_camera: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    world_bounds: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    tile_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)


class Region(Base):
    __tablename__ = "regions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    map_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("maps.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    min_x: Mapped[float] = mapped_column(Float)
    min_y: Mapped[float] = mapped_column(Float)
    max_x: Mapped[float] = mapped_column(Float)
    max_y: Mapped[float] = mapped_column(Float)
    style: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[ContentStatus] = mapped_column(Enum(ContentStatus, name="region_status"), default=ContentStatus.draft, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class Layer(Base):
    __tablename__ = "layers"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    region_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("regions.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    z_index: Mapped[int] = mapped_column(Integer)
    min_zoom: Mapped[float] = mapped_column(Float, default=-4)
    max_zoom: Mapped[float] = mapped_column(Float, default=5)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    style: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    background_asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    version: Mapped[int] = mapped_column(Integer, default=1)


class TerrainFeature(Base):
    __tablename__ = "terrain_features"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    layer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("layers.id", ondelete="CASCADE"), index=True)
    feature_type: Mapped[str] = mapped_column(String(40))
    geometry: Mapped[dict[str, Any]] = mapped_column(JSONB)
    symbol: Mapped[str | None] = mapped_column(String(40))
    style: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(180), index=True)
    status: Mapped[ContentStatus] = mapped_column(Enum(ContentStatus, name="topic_status"), default=ContentStatus.draft, index=True)
    published_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revisions: Mapped[list["TopicRevision"]] = relationship(
        back_populates="topic", foreign_keys="TopicRevision.topic_id", order_by="TopicRevision.revision_number"
    )


class TopicRevision(Base):
    __tablename__ = "topic_revisions"
    __table_args__ = (UniqueConstraint("topic_id", "revision_number"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    revision_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(240))
    summary: Mapped[str] = mapped_column(Text)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    language: Mapped[str] = mapped_column(String(12), default="en")
    change_note: Mapped[str] = mapped_column(String(500), default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    base_revision_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topic_revisions.id"))
    review_state: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    topic: Mapped[Topic] = relationship(back_populates="revisions", foreign_keys=[topic_id])


class Placement(Base):
    __tablename__ = "placements"
    __table_args__ = (Index("ix_placements_map_xy", "map_id", "x", "y"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    map_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("maps.id", ondelete="CASCADE"), index=True)
    region_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("regions.id"), index=True)
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    icon: Mapped[str] = mapped_column(String(40), default="building")
    min_zoom: Mapped[float] = mapped_column(Float, default=-4)
    max_zoom: Mapped[float] = mapped_column(Float, default=5)
    label_priority: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[ContentStatus] = mapped_column(Enum(ContentStatus, name="placement_status"), default=ContentStatus.draft, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Relationship(Base):
    __tablename__ = "relationships"
    __table_args__ = (UniqueConstraint("source_topic_id", "target_topic_id", "kind"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id"), index=True)
    target_topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    explanation: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[ContentStatus] = mapped_column(Enum(ContentStatus, name="relationship_status"), default=ContentStatus.draft)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500))
    authors: Mapped[str] = mapped_column(String(500), default="")
    url: Mapped[str | None] = mapped_column(Text)
    doi: Mapped[str | None] = mapped_column(String(200))
    year: Mapped[int | None] = mapped_column(Integer)
    accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class RevisionSource(Base):
    __tablename__ = "revision_sources"
    topic_revision_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topic_revisions.id", ondelete="CASCADE"), primary_key=True)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True)
    claim_reference: Mapped[str | None] = mapped_column(String(200))


class Trail(Base):
    __tablename__ = "trails"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(240))
    summary: Mapped[str] = mapped_column(Text, default="")
    map_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("maps.id"))
    visibility: Mapped[str] = mapped_column(String(30), default="public")
    status: Mapped[ContentStatus] = mapped_column(Enum(ContentStatus, name="trail_status"), default=ContentStatus.draft)
    start_step_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    source_trail_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("trails.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)


class TrailStep(Base):
    __tablename__ = "trail_steps"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trail_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trails.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id"))
    preferred_placement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("placements.id"))
    note: Mapped[str] = mapped_column(Text, default="")
    suggested_camera: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class TrailEdge(Base):
    __tablename__ = "trail_edges"
    __table_args__ = (UniqueConstraint("trail_id", "from_step_id", "to_step_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trail_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trails.id", ondelete="CASCADE"), index=True)
    from_step_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trail_steps.id"))
    to_step_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trail_steps.id"))
    label: Mapped[str] = mapped_column(String(120), default="")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    storage_key: Mapped[str] = mapped_column(String(300), unique=True)
    mime: Mapped[str] = mapped_column(String(100))
    byte_count: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    credit: Mapped[str] = mapped_column(String(500), default="")
    license: Mapped[str] = mapped_column(String(120), default="")
    access_policy: Mapped[str] = mapped_column(String(30), default="private")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ChangeRequest(Base):
    __tablename__ = "change_requests"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    base_version: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    safe_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class EntityRevision(Base):
    __tablename__ = "entity_revisions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("actor_id", "key", "operation"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    key: Mapped[str] = mapped_column(String(100))
    operation: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict[str, Any]] = mapped_column(JSONB)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

