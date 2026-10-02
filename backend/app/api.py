import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, Response, UploadFile
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .auth import current_user, digest, new_token, optional_user, require_role, verify_csrf, verify_password
from .config import get_settings
from .database import get_db
from .models import (
    Asset, AuditEvent, BrowserSession, ChangeRequest, ContentStatus, EntityRevision,
    IdempotencyRecord, KnowledgeMap, Layer, Placement, Region, Relationship, Role,
    TerrainFeature, Topic, TopicRevision, Trail, TrailEdge, TrailStep, User,
)
from .schemas import (
    LoginInput, PlacementInput, PlacementPatch, RegionCreate, RelationshipCreate,
    TerrainFeatureInput, TopicCreate, TopicRevisionCreate, TrailCreate,
)
from .services import (
    create_revision, create_topic, create_trail, placement_json, publish_revision,
    region_json, revision_json, search_topics, topic_json, validate_placement_context, viewport,
)

settings = get_settings()
router = APIRouter(prefix="/api/v1")


def fail(status: int, code: str, message: str, details: dict[str, Any] | None = None) -> None:
    raise HTTPException(status, detail={"code": code, "message": message, "details": details or {}})


def audit(db: Session, request: Request, actor: User | None, action: str, entity_type: str, entity_id: uuid.UUID | None) -> None:
    db.add(AuditEvent(
        actor_id=actor.id if actor else None, action=action, entity_type=entity_type,
        entity_id=entity_id, request_id=getattr(request.state, "request_id", "unknown"),
    ))


def idempotent_start(
    db: Session, actor: User, key: str | None, operation: str, payload: dict[str, Any]
) -> tuple[IdempotencyRecord | None, dict[str, Any] | None]:
    if not key:
        return None, None
    if len(key) > 100:
        fail(422, "invalid_idempotency_key", "Idempotency-Key is too long")
    request_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    existing = db.scalar(select(IdempotencyRecord).where(
        IdempotencyRecord.actor_id == actor.id,
        IdempotencyRecord.key == key,
        IdempotencyRecord.operation == operation,
    ))
    if existing:
        if existing.request_hash != request_hash:
            fail(409, "idempotency_conflict", "The key was already used with a different request")
        return existing, existing.response
    return IdempotencyRecord(
        actor_id=actor.id, key=key, operation=operation, request_hash=request_hash,
        response={}, expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    ), None


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def ready(db: Session = Depends(get_db)) -> dict[str, Any]:
    db.execute(text("select 1"))
    settings.asset_root.mkdir(parents=True, exist_ok=True)
    probe = settings.asset_root / ".ready"
    probe.touch(exist_ok=True)
    return {"status": "ready", "database": "ok", "assets": "ok"}


@router.get("/capabilities")
def capabilities() -> dict[str, Any]:
    return {
        "application": "Alkemata Knowledge Map", "version": "1.0.0",
        "stage": "A", "content_schema_versions": [1], "coordinate_version": 1,
        "world_coordinates": {"x": "east/right", "y": "north/up"},
        "semantic_zoom": {"overview": [-4, -2], "district": [-2, 0], "detail": [0, 5]},
        "mcp": {"enabled": settings.mcp_enabled, "url": f"{settings.public_origin}/mcp", "writes": settings.mcp_write_enabled},
        "limits": {"page_max": 200, "upload_bytes": settings.max_upload_bytes, "geometry_vertices": 500},
        "publishing": "Drafts require editor review; public reads never include drafts.",
    }


@router.get("/maps")
def maps(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [
        {"id": str(item.id), "title": item.title, "description": item.description,
         "coordinate_version": item.coordinate_version, "default_camera": item.default_camera, "version": item.version}
        for item in db.scalars(select(KnowledgeMap).order_by(KnowledgeMap.title))
    ]


@router.get("/maps/{map_id}")
def get_map(map_id: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(KnowledgeMap, map_id)
    if not item:
        fail(404, "map_not_found", "Map not found")
    bounds = db.execute(select(
        func.min(Region.min_x), func.min(Region.min_y), func.max(Region.max_x), func.max(Region.max_y)
    ).where(Region.map_id == map_id, Region.status == ContentStatus.published)).one()
    return {
        "id": str(item.id), "title": item.title, "description": item.description,
        "coordinate_version": item.coordinate_version, "default_camera": item.default_camera,
        "bounds": {"min_x": bounds[0], "min_y": bounds[1], "max_x": bounds[2], "max_y": bounds[3]},
        "version": item.version,
    }


@router.get("/maps/{map_id}/regions")
def map_regions(map_id: uuid.UUID, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [region_json(item) for item in db.scalars(select(Region).where(
        Region.map_id == map_id, Region.status == ContentStatus.published
    ).order_by(Region.title))]


@router.get("/maps/{map_id}/viewport")
def map_viewport(
    map_id: uuid.UUID, min_x: float, min_y: float, max_x: float, max_y: float,
    zoom: float, db: Session = Depends(get_db),
) -> dict[str, Any]:
    if min_x >= max_x or min_y >= max_y:
        fail(422, "invalid_bounds", "Viewport bounds are invalid")
    return viewport(db, map_id, (min_x, min_y, max_x, max_y), zoom)


@router.get("/topics")
def topics(
    q: str = "", language: str | None = None, limit: int = 50,
    cursor: str | None = None, db: Session = Depends(get_db),
) -> dict[str, Any]:
    if cursor:
        fail(422, "cursor_not_supported", "This dataset currently fits in one bounded page")
    items = search_topics(db, q, language, limit)
    return {"items": items, "next_cursor": None}


@router.get("/topics/{topic_id}")
def get_topic(topic_id: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(Topic, topic_id)
    if not item:
        fail(404, "topic_not_found", "Topic not found")
    return topic_json(db, item)


@router.get("/topics/{topic_id}/relationships")
def topic_relationships(topic_id: uuid.UUID, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(select(Relationship).where(
        (Relationship.source_topic_id == topic_id) | (Relationship.target_topic_id == topic_id),
        Relationship.status == ContentStatus.published,
        Relationship.archived_at.is_(None),
    ))
    return [
        {"id": str(item.id), "source_topic_id": str(item.source_topic_id),
         "target_topic_id": str(item.target_topic_id), "kind": item.kind,
         "explanation": item.explanation, "version": item.version}
        for item in rows
    ]


@router.get("/topics/{topic_id}/placements")
def topic_placements(topic_id: uuid.UUID, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [placement_json(item) for item in db.scalars(select(Placement).where(
        Placement.topic_id == topic_id, Placement.status == ContentStatus.published,
        Placement.archived_at.is_(None),
    ))]


@router.post("/auth/login")
def login(data: LoginInput, response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    user = db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    if not user or user.disabled_at or not verify_password(user.password_hash, data.password):
        fail(401, "invalid_credentials", "Invalid credentials")
    raw = new_token()
    csrf = secrets.token_urlsafe(24)
    db.add(BrowserSession(
        user_id=user.id, hashed_token=digest(raw), csrf_token=csrf,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours),
    ))
    db.commit()
    response.set_cookie(
        "km_session", raw, secure=settings.app_env == "production", httponly=True,
        samesite="strict", max_age=settings.session_ttl_hours * 3600, path="/",
    )
    return {"user": {"id": str(user.id), "display_name": user.display_name, "role": user.role.value}, "csrf_token": csrf}


@router.post("/auth/logout")
def logout(request: Request, response: Response, user: User = Depends(verify_csrf), db: Session = Depends(get_db)) -> dict[str, bool]:
    session = getattr(request.state, "browser_session", None)
    if session:
        session.revoked_at = datetime.now(timezone.utc)
        db.commit()
    response.delete_cookie("km_session", path="/")
    return {"logged_out": True}


@router.get("/auth/me")
def me(request: Request, user: User | None = Depends(optional_user)) -> dict[str, Any]:
    if not user:
        return {"authenticated": False}
    session = getattr(request.state, "browser_session", None)
    return {
        "authenticated": True, "id": str(user.id), "display_name": user.display_name,
        "role": user.role.value, "identity_type": user.identity_type.value,
        "csrf_token": session.csrf_token if session else None,
    }


@router.post("/topics", status_code=201)
def post_topic(
    data: TopicCreate, request: Request, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    actor: User = Depends(verify_csrf), db: Session = Depends(get_db),
) -> dict[str, Any]:
    if actor.role == Role.reader:
        fail(403, "forbidden", "Contributor role required")
    record, cached = idempotent_start(db, actor, idempotency_key, "create_topic", data.model_dump(mode="json"))
    if cached:
        return cached
    item = create_topic(db, data, actor, publish=actor.role in {Role.editor, Role.administrator})
    result = {"id": str(item.id), "status": item.status.value, "canonical_url": f"{settings.public_origin}/topics/{item.id}/{item.slug}"}
    if record:
        record.response = result
        db.add(record)
    audit(db, request, actor, "topic.create", "topic", item.id)
    db.commit()
    return result


@router.post("/topics/{topic_id}/revisions", status_code=201)
def post_revision(
    topic_id: uuid.UUID, data: TopicRevisionCreate, request: Request,
    actor: User = Depends(verify_csrf), db: Session = Depends(get_db),
) -> dict[str, Any]:
    if actor.role == Role.reader:
        fail(403, "forbidden", "Contributor role required")
    topic = db.get(Topic, topic_id)
    if not topic:
        fail(404, "topic_not_found", "Topic not found")
    revision = create_revision(db, topic, data, actor)
    audit(db, request, actor, "topic.revise", "topic", topic.id)
    db.commit()
    return revision_json(revision)


@router.post("/topics/{topic_id}/submit")
def submit_topic(topic_id: uuid.UUID, revision_id: uuid.UUID, request: Request, actor: User = Depends(verify_csrf), db: Session = Depends(get_db)) -> dict[str, Any]:
    revision = db.get(TopicRevision, revision_id)
    if not revision or revision.topic_id != topic_id:
        fail(404, "revision_not_found", "Revision not found")
    if actor.role not in {Role.contributor, Role.editor, Role.administrator}:
        fail(403, "forbidden", "Contributor role required")
    revision.review_state = "review"
    audit(db, request, actor, "topic.submit", "topic", topic_id)
    db.commit()
    return {"topic_id": str(topic_id), "revision_id": str(revision_id), "status": "review"}


@router.post("/topics/{topic_id}/publish")
def publish_topic(
    topic_id: uuid.UUID, revision_id: uuid.UUID, request: Request,
    actor: User = Depends(require_role(Role.editor)), db: Session = Depends(get_db),
) -> dict[str, Any]:
    topic = db.get(Topic, topic_id)
    revision = db.get(TopicRevision, revision_id)
    if not topic or not revision:
        fail(404, "not_found", "Topic or revision not found")
    publish_revision(db, topic, revision, actor)
    audit(db, request, actor, "topic.publish", "topic", topic.id)
    db.commit()
    return topic_json(db, topic)


@router.get("/topics/{topic_id}/revisions")
def revisions(topic_id: uuid.UUID, actor: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [revision_json(item) for item in db.scalars(select(TopicRevision).where(
        TopicRevision.topic_id == topic_id
    ).order_by(TopicRevision.revision_number.desc()))]


@router.post("/placements", status_code=201)
def post_placement(data: PlacementInput, topic_id: uuid.UUID, request: Request, actor: User = Depends(verify_csrf), db: Session = Depends(get_db)) -> dict[str, Any]:
    if actor.role == Role.reader:
        fail(403, "forbidden", "Contributor role required")
    if not db.get(Topic, topic_id):
        fail(404, "topic_not_found", "Topic not found")
    validate_placement_context(db, data)
    item = Placement(
        topic_id=topic_id, map_id=data.map_id, region_id=data.region_id, x=data.x, y=data.y,
        icon=data.icon, min_zoom=data.min_zoom, max_zoom=data.max_zoom, label_priority=data.label_priority,
        status=ContentStatus.published if actor.role in {Role.editor, Role.administrator} else ContentStatus.draft,
    )
    db.add(item)
    db.flush()
    audit(db, request, actor, "placement.create", "placement", item.id)
    db.commit()
    return placement_json(item)


@router.patch("/placements/{placement_id}")
def move_placement(placement_id: uuid.UUID, data: PlacementPatch, request: Request, actor: User = Depends(require_role(Role.editor)), db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(Placement, placement_id)
    if not item or item.archived_at:
        fail(404, "placement_not_found", "Placement not found")
    if item.version != data.base_version:
        fail(409, "version_conflict", "Placement changed", {"current_version": item.version, "x": item.x, "y": item.y})
    region = db.get(Region, item.region_id) if item.region_id else None
    if region and not (region.min_x <= data.x <= region.max_x and region.min_y <= data.y <= region.max_y):
        fail(422, "outside_region", "Position is outside region bounds")
    db.add(EntityRevision(
        entity_type="placement", entity_id=item.id, version=item.version,
        snapshot=placement_json(item), created_by=actor.id,
    ))
    item.x, item.y, item.version = data.x, data.y, item.version + 1
    audit(db, request, actor, "placement.move", "placement", item.id)
    db.commit()
    return placement_json(item)


@router.delete("/placements/{placement_id}")
def archive_placement(placement_id: uuid.UUID, request: Request, actor: User = Depends(require_role(Role.editor)), db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(Placement, placement_id)
    if not item:
        fail(404, "placement_not_found", "Placement not found")
    item.status = ContentStatus.archived
    item.archived_at = datetime.now(timezone.utc)
    item.version += 1
    audit(db, request, actor, "placement.archive", "placement", item.id)
    db.commit()
    return {"id": str(item.id), "status": "archived", "version": item.version}


@router.post("/relationships", status_code=201)
def post_relationship(data: RelationshipCreate, request: Request, actor: User = Depends(verify_csrf), db: Session = Depends(get_db)) -> dict[str, Any]:
    if actor.role == Role.reader:
        fail(403, "forbidden", "Contributor role required")
    if not db.get(Topic, data.source_topic_id) or not db.get(Topic, data.target_topic_id):
        fail(422, "invalid_topic", "Both topics must exist")
    item = Relationship(
        **data.model_dump(), created_by=actor.id,
        status=ContentStatus.published if actor.role in {Role.editor, Role.administrator} else ContentStatus.draft,
    )
    db.add(item)
    db.flush()
    audit(db, request, actor, "relationship.create", "relationship", item.id)
    db.commit()
    return {"id": str(item.id), "status": item.status.value, "version": item.version}


@router.get("/trails")
def trails(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [{"id": str(item.id), "title": item.title, "summary": item.summary, "map_id": str(item.map_id) if item.map_id else None, "version": item.version}
            for item in db.scalars(select(Trail).where(Trail.status == ContentStatus.published).order_by(Trail.title))]


@router.get("/trails/{trail_id}")
def get_trail(trail_id: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = db.get(Trail, trail_id)
    if not item or item.status != ContentStatus.published:
        fail(404, "trail_not_found", "Trail not found")
    steps = list(db.scalars(select(TrailStep).where(TrailStep.trail_id == trail_id)))
    edges = list(db.scalars(select(TrailEdge).where(TrailEdge.trail_id == trail_id)))
    return {
        "id": str(item.id), "title": item.title, "summary": item.summary,
        "map_id": str(item.map_id) if item.map_id else None, "start_step_id": str(item.start_step_id),
        "version": item.version,
        "steps": [{"id": str(s.id), "topic_id": str(s.topic_id), "preferred_placement_id": str(s.preferred_placement_id) if s.preferred_placement_id else None, "note": s.note} for s in steps],
        "edges": [{"id": str(e.id), "from_step_id": str(e.from_step_id), "to_step_id": str(e.to_step_id), "label": e.label, "is_default": e.is_default} for e in edges],
    }


@router.post("/trails", status_code=201)
def post_trail(data: TrailCreate, request: Request, actor: User = Depends(verify_csrf), db: Session = Depends(get_db)) -> dict[str, Any]:
    if actor.role == Role.reader:
        fail(403, "forbidden", "Contributor role required")
    item = create_trail(db, data, actor, publish=actor.role in {Role.editor, Role.administrator})
    audit(db, request, actor, "trail.create", "trail", item.id)
    db.commit()
    return {"id": str(item.id), "status": item.status.value, "version": item.version, "canonical_url": f"{settings.public_origin}/trails/{item.id}"}


@router.post("/maps/{map_id}/regions", status_code=201)
def post_region(map_id: uuid.UUID, data: RegionCreate, request: Request, actor: User = Depends(require_role(Role.editor)), db: Session = Depends(get_db)) -> dict[str, Any]:
    if not db.get(KnowledgeMap, map_id):
        fail(404, "map_not_found", "Map not found")
    item = Region(
        map_id=map_id, title=data.title, min_x=data.bounds.min_x, min_y=data.bounds.min_y,
        max_x=data.bounds.max_x, max_y=data.bounds.max_y, style=data.style, status=ContentStatus.published,
    )
    db.add(item)
    db.flush()
    audit(db, request, actor, "region.create", "region", item.id)
    db.commit()
    return region_json(item)


@router.post("/regions/{region_id}/layers", status_code=201)
def post_layer(region_id: uuid.UUID, kind: str, z_index: int, request: Request, actor: User = Depends(require_role(Role.editor)), db: Session = Depends(get_db)) -> dict[str, Any]:
    if not db.get(Region, region_id):
        fail(404, "region_not_found", "Region not found")
    if kind not in {"background", "water", "terrain", "roads", "buildings", "markers", "labels"}:
        fail(422, "invalid_layer_kind", "Unsupported layer kind")
    item = Layer(region_id=region_id, kind=kind, z_index=z_index)
    db.add(item)
    db.flush()
    audit(db, request, actor, "layer.create", "layer", item.id)
    db.commit()
    return {"id": str(item.id), "kind": item.kind, "z_index": item.z_index, "version": item.version}


@router.post("/layers/{layer_id}/features", status_code=201)
def post_feature(layer_id: uuid.UUID, data: TerrainFeatureInput, request: Request, actor: User = Depends(require_role(Role.editor)), db: Session = Depends(get_db)) -> dict[str, Any]:
    if not db.get(Layer, layer_id):
        fail(404, "layer_not_found", "Layer not found")
    item = TerrainFeature(
        layer_id=layer_id, feature_type=data.feature_type, geometry=data.geometry,
        symbol=data.symbol, style=data.style,
    )
    db.add(item)
    db.flush()
    audit(db, request, actor, "terrain.create", "terrain_feature", item.id)
    db.commit()
    return {"id": str(item.id), "version": item.version}


def validate_svg(data: bytes) -> None:
    if len(data) > settings.max_upload_bytes:
        fail(413, "asset_too_large", "Asset exceeds upload limit")
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError:
        fail(422, "invalid_svg", "SVG is not well formed")
    allowed = {"svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "defs", "linearGradient", "radialGradient", "stop", "title", "desc"}
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1]
        if tag not in allowed:
            fail(422, "unsafe_svg", f"Unsupported SVG element: {tag}")
        for name, value in node.attrib.items():
            local = name.rsplit("}", 1)[-1].lower()
            if local.startswith("on") or local in {"href", "src"} or "url(" in value.lower():
                fail(422, "unsafe_svg", "SVG contains an external or executable reference")


@router.post("/assets", status_code=201)
async def post_asset(
    request: Request, file: UploadFile = File(), credit: str = "", license: str = "",
    actor: User = Depends(verify_csrf), db: Session = Depends(get_db),
) -> dict[str, Any]:
    if actor.role == Role.reader:
        fail(403, "forbidden", "Contributor role required")
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        fail(413, "asset_too_large", "Asset exceeds upload limit")
    mime = file.content_type or "application/octet-stream"
    if mime not in {"image/png", "image/jpeg", "image/webp", "image/svg+xml"}:
        fail(422, "unsupported_mime", "Unsupported asset type")
    if mime == "image/svg+xml":
        validate_svg(data)
    checksum = hashlib.sha256(data).hexdigest()
    ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/svg+xml": ".svg"}[mime]
    key = f"{uuid.uuid4()}{ext}"
    settings.asset_root.mkdir(parents=True, exist_ok=True)
    (settings.asset_root / key).write_bytes(data)
    item = Asset(
        storage_key=key, mime=mime, byte_count=len(data), checksum=checksum,
        credit=credit[:500], license=license[:120], access_policy="private", created_by=actor.id,
    )
    db.add(item)
    db.flush()
    audit(db, request, actor, "asset.create", "asset", item.id)
    db.commit()
    return {"id": str(item.id), "mime": mime, "bytes": len(data), "checksum": checksum, "access_policy": item.access_policy}


@router.post("/change-requests", status_code=201)
def post_change_request(entity_type: str, payload: dict[str, Any], entity_id: uuid.UUID | None = None, base_version: int | None = None, actor: User = Depends(verify_csrf), db: Session = Depends(get_db)) -> dict[str, Any]:
    if actor.role == Role.reader:
        fail(403, "forbidden", "Contributor role required")
    item = ChangeRequest(entity_type=entity_type, entity_id=entity_id, payload=payload, base_version=base_version, created_by=actor.id)
    db.add(item)
    db.commit()
    return {"id": str(item.id), "status": item.status}

