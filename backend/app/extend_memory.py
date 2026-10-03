"""Add a small, idempotent memory-in-AI demonstration cluster to the demo map."""

import argparse
import uuid

from sqlalchemy import select

from .database import new_session
from .models import ContentStatus, KnowledgeMap, Placement, Region, Relationship, Topic, TopicRevision, User
from .seed import NAMESPACE, block
from .services import slugify

MEMORY_NOTES = [
    (
        "Context Window", 1350, 2960, -1,
        "The text and other input available to a model for one request; it is not durable memory by itself.",
        "A context window can hold the current conversation and retrieved notes, but it does not automatically preserve them for a later session.",
        "When a conversation exceeds its window, an application must select, summarize, or retrieve earlier material if it is still needed.",
    ),
    (
        "Conversational Memory", 1420, 2570, -1,
        "Information deliberately carried from one interaction to another, such as a preference, decision, or unfinished task.",
        "A useful memory records what should persist, for whom, and why; the model's current context alone cannot provide that persistence.",
        "For example, a project decision can be saved as a dated note and retrieved when the same project is discussed again.",
    ),
    (
        "Episodic Memory in AI", 1110, 2580, 0,
        "A record of particular past interactions or events, usually with time, participants, and provenance.",
        "Episodes preserve the circumstances of a statement so a later system can distinguish an observation from a lasting fact.",
        "A dated request to compare two designs is an episode; it should not silently become a permanent user preference.",
    ),
    (
        "Semantic Memory in AI", 850, 2770, 0,
        "Distilled facts and concepts retained independently of the individual interaction where they were learned.",
        "A semantic memory can make repeated work faster, but it needs a source, scope, and a way to correct stale information.",
        "A confirmed project name may be retained as a fact; a one-off example should not be treated the same way.",
    ),
    (
        "Memory Retrieval", 1450, 1890, 0,
        "Selecting relevant stored information for the present question rather than placing every memory into the prompt.",
        "Retrieval can combine keywords, semantic similarity, recency, and explicit links. Relevance is a selection rule, not proof that a memory is true.",
        "If the user asks about a map design, retrieve the design decisions and their sources before unrelated conversations.",
    ),
    (
        "Memory Consolidation", 1040, 1740, 0,
        "Combining repeated episodes into a shorter, more useful record while preserving important distinctions.",
        "Consolidation should keep provenance and uncertainty so compression does not turn a tentative remark into a firm preference.",
        "Several repeated requests for circular map notes may support a design preference, while one exploratory sketch does not.",
    ),
    (
        "Memory Correction", 730, 1840, 0,
        "Updating or superseding stored information when a user or trusted source provides a correction.",
        "A correction should identify what changed and prevent the old version from being retrieved as current truth.",
        "If a project URL changes, replace the active URL while retaining enough history to understand older references.",
    ),
    (
        "Forgetting and Consent", 430, 1970, 0,
        "Rules for limiting, reviewing, and deleting retained information according to the user's wishes.",
        "A memory system should make persistence visible and let people remove data that should no longer influence answers.",
        "A temporary test preference can expire instead of becoming an indefinite profile attribute.",
    ),
]


def add_relation(db, source_id: uuid.UUID, target_id: uuid.UUID, kind: str, actor_id: uuid.UUID) -> None:
    if kind == "related_to" and source_id.int > target_id.int:
        source_id, target_id = target_id, source_id
    existing = db.scalar(select(Relationship).where(
        Relationship.source_topic_id == source_id,
        Relationship.target_topic_id == target_id,
        Relationship.kind == kind,
    ))
    if existing is None:
        db.add(Relationship(
            source_topic_id=source_id, target_topic_id=target_id, kind=kind,
            explanation="Part of the memory lifecycle demonstrated on this map.",
            status=ContentStatus.published, created_by=actor_id,
        ))


def extend_demo() -> None:
    map_id = uuid.uuid5(NAMESPACE, "world")
    actor_id = uuid.uuid5(NAMESPACE, "demo-user")
    region_id = uuid.uuid5(NAMESPACE, "region-0")
    root_id = uuid.uuid5(NAMESPACE, "topic-memory-in-ai")
    with new_session() as db:
        if not all((db.get(KnowledgeMap, map_id), db.get(User, actor_id), db.get(Region, region_id), db.get(Topic, root_id))):
            raise RuntimeError("The original demonstration map is missing; no changes made")
        created = 0
        for title, x, y, min_zoom, summary, explanation, example in MEMORY_NOTES:
            slug = slugify(title)
            topic_id = uuid.uuid5(NAMESPACE, f"topic-{slug}")
            revision_id = uuid.uuid5(NAMESPACE, f"revision-{slug}")
            if db.get(Topic, topic_id) is None:
                db.add(Topic(
                    id=topic_id, slug=slug, status=ContentStatus.published,
                    published_revision_id=revision_id, created_by=actor_id,
                ))
                db.add(TopicRevision(
                    id=revision_id, topic_id=topic_id, revision_number=1,
                    title=title, summary=summary,
                    content={"schema_version": 1, "blocks": [
                        block("heading", {"level": 2, "text": "How it works"}),
                        block("paragraph", {"text": explanation}),
                        block("heading", {"level": 2, "text": "Example"}),
                        block("paragraph", {"text": example}),
                        block("topic_link", {"target_topic_id": str(root_id), "label": "Back to Memory in AI"}),
                    ]},
                    language="en", change_note="Memory map demonstration extension",
                    created_by=actor_id, review_state="published", reviewed_by=actor_id,
                ))
                db.flush()
                created += 1
            placement_id = uuid.uuid5(NAMESPACE, f"placement-{slug}")
            if db.get(Placement, placement_id) is None:
                db.add(Placement(
                    id=placement_id, topic_id=topic_id, map_id=map_id, region_id=region_id,
                    x=x, y=y, icon="observatory", min_zoom=min_zoom, max_zoom=5,
                    label_priority=5 - min_zoom, status=ContentStatus.published,
                ))
            add_relation(db, root_id, topic_id, "broader_than", actor_id)
        db.commit()
        print(f"Memory cluster ready: {created} new notes, {len(MEMORY_NOTES)} total demonstration notes")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Explicitly extend the demonstration map")
    args = parser.parse_args()
    if not args.demo:
        raise SystemExit("Refusing to change map content without --demo")
    extend_demo()


if __name__ == "__main__":
    main()
