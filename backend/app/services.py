import re
import math
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import (
    ContentStatus, KnowledgeMap, Layer, Placement, Region, Relationship,
    TerrainFeature, Topic, TopicRevision, Trail, TrailEdge, TrailStep, User,
)
from .schemas import PlacementInput, TopicCreate, TopicRevisionCreate, TrailCreate

settings = get_settings()


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value[:160] or "topic"


def public_revision(db: Session, topic: Topic) -> TopicRevision | None:
    if topic.status != ContentStatus.published or topic.archived_at or not topic.published_revision_id:
        return None
    return db.get(TopicRevision, topic.published_revision_id)


def revision_json(revision: TopicRevision) -> dict[str, Any]:
    return {
        "id": str(revision.id),
        "revision_number": revision.revision_number,
        "title": revision.title,
        "summary": revision.summary,
        "content": revision.content,
        "language": revision.language,
        "change_note": revision.change_note,
        "review_state": revision.review_state,
        "created_at": revision.created_at.isoformat(),
    }


def topic_json(db: Session, topic: Topic, include_content: bool = True) -> dict[str, Any]:
    revision = public_revision(db, topic)
    if revision is None:
        raise HTTPException(404, detail={"code": "topic_not_found", "message": "Published topic not found"})
    result = {
        "id": str(topic.id),
        "slug": topic.slug,
        "status": topic.status.value,
        "version": revision.revision_number,
        "title": revision.title,
        "summary": revision.summary,
        "language": revision.language,
        "updated_at": revision.created_at.isoformat(),
        "canonical_url": f"{settings.public_origin}/topics/{topic.id}/{topic.slug}",
    }
    if include_content:
        result["content"] = revision.content
    return result


def region_json(region: Region) -> dict[str, Any]:
    return {
        "id": str(region.id), "map_id": str(region.map_id), "title": region.title,
        "bounds": {"min_x": region.min_x, "min_y": region.min_y, "max_x": region.max_x, "max_y": region.max_y},
        "style": region.style, "status": region.status.value, "version": region.version,
    }


def placement_json(placement: Placement, topic: dict[str, Any] | None = None) -> dict[str, Any]:
    value = {
        "id": str(placement.id), "topic_id": str(placement.topic_id), "map_id": str(placement.map_id),
        "region_id": str(placement.region_id) if placement.region_id else None,
        "x": placement.x, "y": placement.y, "icon": placement.icon,
        "min_zoom": placement.min_zoom, "max_zoom": placement.max_zoom,
        "label_priority": placement.label_priority, "status": placement.status.value,
        "version": placement.version,
    }
    if topic:
        value["topic"] = topic
    return value


def validate_placement_context(db: Session, data: PlacementInput) -> Region | None:
    knowledge_map = db.get(KnowledgeMap, data.map_id)
    if knowledge_map is None:
        raise HTTPException(422, detail={"code": "invalid_map", "message": "Map does not exist"})
    bounds = knowledge_map.world_bounds
    if bounds and not (
        bounds["min_x"] <= data.x <= bounds["max_x"]
        and bounds["min_y"] <= data.y <= bounds["max_y"]
    ):
        raise HTTPException(422, detail={
            "code": "outside_map",
            "message": "Position is outside the map world bounds",
        })
    if data.region_id:
        region = db.get(Region, data.region_id)
        if region is None or region.map_id != data.map_id:
            raise HTTPException(422, detail={"code": "invalid_region", "message": "Region is not on the selected map"})
        if not (region.min_x <= data.x <= region.max_x and region.min_y <= data.y <= region.max_y):
            raise HTTPException(422, detail={"code": "outside_region", "message": "Position is outside region bounds"})
        return region
    return None


def destination_region(regions: list[Region], current_region_id: uuid.UUID | None,
                       x: float, y: float) -> uuid.UUID | None:
    """Keep the current region when possible, otherwise choose the smallest containing region."""
    containing = [region for region in regions if (
        region.min_x <= x <= region.max_x and region.min_y <= y <= region.max_y
    )]
    current = next((region for region in containing if region.id == current_region_id), None)
    if current:
        return current.id
    if not containing:
        return None
    return min(containing, key=lambda region: (
        (region.max_x - region.min_x) * (region.max_y - region.min_y), str(region.id),
    )).id


def category_parents(db: Session, map_id: uuid.UUID) -> dict[uuid.UUID, uuid.UUID]:
    """Use published broader-than links as the map's single-parent category tree."""
    placed = set(db.scalars(select(Placement.topic_id).where(
        Placement.map_id == map_id, Placement.archived_at.is_(None),
        Placement.status == ContentStatus.published,
    )))
    parents: dict[uuid.UUID, uuid.UUID] = {}
    links = db.scalars(select(Relationship).where(
        Relationship.kind == "broader_than", Relationship.status == ContentStatus.published,
        Relationship.archived_at.is_(None),
    ).order_by(Relationship.id))
    for link in links:
        if link.source_topic_id in placed and link.target_topic_id in placed:
            parents.setdefault(link.target_topic_id, link.source_topic_id)
    return parents


def category_depth(topic_id: uuid.UUID, parents: dict[uuid.UUID, uuid.UUID]) -> int:
    seen = {topic_id}
    depth = 0
    while topic_id in parents:
        topic_id = parents[topic_id]
        if topic_id in seen:
            raise ValueError("Category links contain a cycle")
        seen.add(topic_id)
        depth += 1
    return depth


def depth_min_zoom(depth: int) -> float:
    # Overview -> district -> detail. The configured frontend maximum is 4.
    return min(3.5, -4 + 2 * depth)


def suggest_position(db: Session, knowledge_map: KnowledgeMap, parent: Placement | None) -> tuple[float, float]:
    center = (parent.x, parent.y) if parent else (
        float(knowledge_map.default_camera["x"]), float(knowledge_map.default_camera["y"]),
    )
    bounds = knowledge_map.world_bounds
    occupied = [(p.x, p.y) for p in db.scalars(select(Placement).where(
        Placement.map_id == knowledge_map.id, Placement.archived_at.is_(None),
        Placement.status == ContentStatus.published,
    ))]
    spacing = 180 if parent else 420
    for ring in range(1, 24):
        radius = spacing * ring
        count = max(12, ring * 12)
        for index in range(count):
            angle = 2 * math.pi * index / count
            x = center[0] + radius * math.cos(angle)
            y = center[1] + radius * math.sin(angle)
            if bounds and not (bounds["min_x"] <= x <= bounds["max_x"] and bounds["min_y"] <= y <= bounds["max_y"]):
                continue
            if all(math.hypot(x - px, y - py) >= spacing * 0.8 for px, py in occupied):
                return x, y
    raise ValueError("No free position is available near this category")


def create_topic(db: Session, data: TopicCreate, actor: User, publish: bool = False, commit: bool = True) -> Topic:
    if data.placement:
        validate_placement_context(db, data.placement)
    topic = Topic(slug=slugify(data.title), created_by=actor.id)
    db.add(topic)
    db.flush()
    revision = TopicRevision(
        topic_id=topic.id, revision_number=1, title=data.title, summary=data.summary,
        content=data.content.model_dump(mode="json"), language=data.language,
        change_note=data.change_note, created_by=actor.id,
        review_state="published" if publish else "draft",
    )
    db.add(revision)
    db.flush()
    if publish:
        topic.status = ContentStatus.published
        topic.published_revision_id = revision.id
    if data.placement:
        p = data.placement
        db.add(Placement(
            topic_id=topic.id, map_id=p.map_id, region_id=p.region_id, x=p.x, y=p.y,
            icon=p.icon, min_zoom=p.min_zoom, max_zoom=p.max_zoom,
            label_priority=p.label_priority,
            status=ContentStatus.published if publish else ContentStatus.draft,
        ))
    if commit:
        db.commit()
    else:
        db.flush()
    return topic


def create_revision(db: Session, topic: Topic, data: TopicRevisionCreate, actor: User) -> TopicRevision:
    latest = db.scalar(select(func.max(TopicRevision.revision_number)).where(TopicRevision.topic_id == topic.id)) or 0
    if latest != data.expected_revision:
        raise HTTPException(
            409,
            detail={"code": "revision_conflict", "message": "Topic changed since it was opened", "details": {"current_revision": latest}},
        )
    base = db.scalar(
        select(TopicRevision).where(TopicRevision.topic_id == topic.id, TopicRevision.revision_number == latest)
    )
    revision = TopicRevision(
        topic_id=topic.id, revision_number=latest + 1, title=data.title, summary=data.summary,
        content=data.content.model_dump(mode="json"), language=data.language, change_note=data.change_note,
        created_by=actor.id, base_revision_id=base.id if base else None, review_state="draft",
    )
    db.add(revision)
    db.commit()
    return revision


def publish_revision(db: Session, topic: Topic, revision: TopicRevision, reviewer: User) -> Topic:
    if revision.topic_id != topic.id:
        raise HTTPException(422, detail={"code": "revision_mismatch", "message": "Revision does not belong to topic"})
    revision.review_state = "published"
    revision.reviewed_by = reviewer.id
    revision.reviewed_at = datetime.now(timezone.utc)
    topic.published_revision_id = revision.id
    topic.status = ContentStatus.published
    db.query(Placement).filter(Placement.topic_id == topic.id, Placement.status != ContentStatus.archived).update(
        {Placement.status: ContentStatus.published}
    )
    db.query(Relationship).filter(
        Relationship.target_topic_id == topic.id, Relationship.kind == "broader_than",
        Relationship.status == ContentStatus.draft,
    ).update({Relationship.status: ContentStatus.published})
    db.commit()
    return topic


def search_topics(db: Session, query: str = "", language: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    stmt = (
        select(Topic, TopicRevision)
        .join(TopicRevision, Topic.published_revision_id == TopicRevision.id)
        .where(Topic.status == ContentStatus.published, Topic.archived_at.is_(None))
        .order_by(TopicRevision.title)
        .limit(min(max(limit, 1), 200))
    )
    if query:
        pattern = f"%{query}%"
        stmt = stmt.where(or_(TopicRevision.title.ilike(pattern), TopicRevision.summary.ilike(pattern)))
    if language:
        stmt = stmt.where(TopicRevision.language == language)
    return [
        {
            "id": str(topic.id), "slug": topic.slug, "title": revision.title,
            "summary": revision.summary, "language": revision.language,
            "version": revision.revision_number,
            "canonical_url": f"{settings.public_origin}/topics/{topic.id}/{topic.slug}",
        }
        for topic, revision in db.execute(stmt)
    ]


def viewport(db: Session, map_id: uuid.UUID, bounds: tuple[float, float, float, float], zoom: float, limit: int = 1000) -> dict[str, Any]:
    min_x, min_y, max_x, max_y = bounds
    stmt = (
        select(Placement, Topic, TopicRevision)
        .join(Topic, Placement.topic_id == Topic.id)
        .join(TopicRevision, Topic.published_revision_id == TopicRevision.id)
        .where(
            Placement.map_id == map_id, Placement.status == ContentStatus.published,
            Placement.archived_at.is_(None), Topic.status == ContentStatus.published,
            Placement.x >= min_x, Placement.x <= max_x, Placement.y >= min_y, Placement.y <= max_y,
            Placement.min_zoom <= zoom, Placement.max_zoom > zoom,
        )
        .order_by(Placement.label_priority.desc())
        .limit(limit + 1)
    )
    rows = list(db.execute(stmt))
    parents = category_parents(db, map_id)
    visible_rows = [(p, t, r, category_depth(t.id, parents)) for p, t, r in rows
                    if zoom >= depth_min_zoom(category_depth(t.id, parents))]
    has_more = len(visible_rows) > limit
    placements = [
        {**placement_json(p, {
            "id": str(t.id), "slug": t.slug, "title": r.title, "summary": r.summary,
            "canonical_url": f"{settings.public_origin}/topics/{t.id}/{t.slug}",
        }), "depth": depth, "category_topic_id": str(parents[t.id]) if t.id in parents else None}
        for p, t, r, depth in visible_rows[:limit]
    ]
    regions = [region_json(r) for r in db.scalars(select(Region).where(Region.map_id == map_id, Region.status == ContentStatus.published))]
    layers = [
        {"id": str(l.id), "region_id": str(l.region_id), "kind": l.kind, "z_index": l.z_index,
         "min_zoom": l.min_zoom, "max_zoom": l.max_zoom, "visible": l.visible, "style": l.style, "version": l.version}
        for l in db.scalars(select(Layer).join(Region).where(Region.map_id == map_id, Layer.visible.is_(True), Layer.min_zoom <= zoom, Layer.max_zoom > zoom))
    ]
    features = [
        {"id": str(f.id), "layer_id": str(f.layer_id), "feature_type": f.feature_type,
         "geometry": f.geometry, "symbol": f.symbol, "style": f.style, "version": f.version}
        for f in db.scalars(select(TerrainFeature).join(Layer).join(Region).where(
            Region.map_id == map_id, TerrainFeature.archived_at.is_(None),
            Layer.visible.is_(True), Layer.min_zoom <= zoom, Layer.max_zoom > zoom,
        ).limit(2000))
    ]
    return {"placements": placements, "regions": regions, "layers": layers, "features": features, "has_more": has_more}


def create_trail(db: Session, data: TrailCreate, actor: User, publish: bool = False) -> Trail:
    trail = Trail(
        title=data.title, summary=data.summary, map_id=data.map_id, created_by=actor.id,
        status=ContentStatus.published if publish else ContentStatus.draft,
    )
    db.add(trail)
    db.flush()
    step_ids: dict[str, uuid.UUID] = {}
    for item in data.steps:
        step = TrailStep(
            trail_id=trail.id, topic_id=item.topic_id,
            preferred_placement_id=item.preferred_placement_id, note=item.note,
        )
        db.add(step)
        db.flush()
        step_ids[item.client_id] = step.id
    trail.start_step_id = step_ids[data.start_client_id]
    for item in data.edges:
        db.add(TrailEdge(
            trail_id=trail.id, from_step_id=step_ids[item.from_client_id],
            to_step_id=step_ids[item.to_client_id], label=item.label, is_default=item.is_default,
        ))
    db.commit()
    return trail

