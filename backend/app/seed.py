import argparse
import uuid

from sqlalchemy import select

from .database import new_session
from .models import (
    ContentStatus, IdentityType, KnowledgeMap, Layer, Placement, Region, Relationship,
    Role, TerrainFeature, Topic, TopicRevision, Trail, TrailEdge, TrailStep, User,
)
from .services import slugify

NAMESPACE = uuid.UUID("5b4f957e-dcad-4d69-9a97-5093f659a544")

TOPICS = [
    ("Artificial Intelligence", "The study and engineering of systems that perform tasks associated with intelligent behaviour.", 0, 650, 3180, -4),
    ("Machine Learning", "Methods that improve behaviour by learning patterns from data or experience.", 0, 880, 2960, -3),
    ("Neural Networks", "Layered function approximators whose parameters are adjusted from examples.", 0, 1100, 2770, -2),
    ("Human-centred AI", "Designing AI around human agency, needs, institutions and lived consequences.", 0, 520, 2720, -2),
    ("AI Evaluation", "Systematic measurement of model capabilities, limitations and downstream effects.", 0, 820, 2480, -1),
    ("Memory in AI", "Mechanisms that retain, retrieve and update information across interactions.", 0, 1180, 2360, -1),
    ("Retrieval-Augmented Generation", "Generation grounded by retrieving relevant material from an external collection.", 0, 1370, 2180, 0),
    ("AI Safety Cases", "Structured arguments and evidence for claims about an AI system's acceptable operation.", 0, 610, 2240, 0),
    ("Interpretability", "Techniques for understanding how model components and representations contribute to behaviour.", 0, 920, 2050, 0),
    ("Agentic Systems", "Software systems in which models choose and sequence actions toward a goal.", 0, 1230, 1900, 0),
    ("Public Technology", "Technology developed and governed to support public value and collective capability.", 1, 2050, 3260, -4),
    ("Digital Public Infrastructure", "Shared digital systems that enable broadly useful public and private services.", 1, 2300, 3020, -3),
    ("Civic Participation", "Processes through which people influence public decisions and shared institutions.", 1, 1810, 2920, -2),
    ("Public Interest Technology", "Applying technical expertise in ways accountable to public needs and rights.", 1, 2050, 2690, -2),
    ("Open Standards", "Publicly available agreements that allow independently built systems to interoperate.", 1, 2520, 2740, -1),
    ("Digital Identity", "Systems for representing and verifying claims about people or organisations.", 1, 2340, 2440, -1),
    ("Service Design", "Designing end-to-end services around the experiences and constraints of their users.", 1, 1760, 2460, -1),
    ("Algorithmic Accountability", "Practices that make consequential automated systems explainable, contestable and governable.", 1, 2030, 2150, 0),
    ("Interoperability", "The ability of distinct systems to exchange information and act on shared meaning.", 1, 2590, 2180, 0),
    ("Digital Commons", "Shared digital resources stewarded through rules that protect collective access and value.", 1, 2290, 1910, 0),
    ("Science and Engineering", "Disciplines for explaining the world and designing reliable interventions within it.", 2, 3380, 3210, -4),
    ("Information Theory", "A mathematical framework for quantifying information, uncertainty and communication.", 2, 3110, 2920, -3),
    ("Thermodynamics", "The study of energy, work, heat and the macroscopic direction of physical processes.", 2, 3610, 2900, -3),
    ("Entropy", "A quantity that characterises uncertainty or the multiplicity of possible microscopic states.", 2, 3340, 2640, -2),
    ("Feedback Control", "Using measured outcomes to adjust a system toward desired behaviour.", 2, 3780, 2520, -2),
    ("Complex Systems", "Systems whose collective behaviour emerges from many interacting parts.", 2, 3070, 2360, -1),
    ("Bayesian Inference", "Updating uncertainty about hypotheses as evidence becomes available.", 2, 3410, 2220, -1),
    ("Resilience Engineering", "Designing systems to adapt, recover and continue under disruption.", 2, 3730, 2100, 0),
    ("Network Science", "The study of entities and the relationships that connect them as networks.", 2, 3120, 1940, 0),
    ("Scientific Models", "Purpose-built representations used to explain, predict or explore aspects of the world.", 2, 3490, 1810, 0),
]


def block(block_type: str, data: dict) -> dict:
    return {"id": str(uuid.uuid4()), "type": block_type, "data": data}


def seed_demo() -> None:
    with new_session() as db:
        existing = db.scalar(select(KnowledgeMap).where(KnowledgeMap.title == "Alkemata Knowledge World"))
        if existing:
            print(f"Demo data already present: map {existing.id}")
            return
        demo_user = User(
            id=uuid.uuid5(NAMESPACE, "demo-user"), display_name="Alkemata demonstration",
            role=Role.editor, identity_type=IdentityType.agent,
        )
        knowledge_map = KnowledgeMap(
            id=uuid.uuid5(NAMESPACE, "world"), title="Alkemata Knowledge World",
            description="An illustrated landscape for exploring connected ideas.",
            default_camera={"x": 3072, "y": 2048, "z": -3}, coordinate_version=2,
            world_bounds={"min_x": 0, "min_y": 0, "max_x": 6144, "max_y": 4096},
            tile_config={
                "url_template": "/map-tiles/{z}/{x}/{y}.webp", "tile_size": 256,
                "min_zoom": -4, "max_native_zoom": 0, "max_zoom": 4,
            },
        )
        db.add_all([demo_user, knowledge_map])
        db.flush()
        regions_data = [
            ("AI Highlands", 256, 1536, 1536, 3584, {"fill": "#dbeafe", "accent": "#2563eb"}),
            ("Public Technology Valley", 1536, 1536, 2816, 3584, {"fill": "#dcfce7", "accent": "#15803d"}),
            ("Science Range", 2816, 1536, 4096, 3584, {"fill": "#fef3c7", "accent": "#b45309"}),
        ]
        regions = []
        for index, (title, min_x, min_y, max_x, max_y, style) in enumerate(regions_data):
            region = Region(
                id=uuid.uuid5(NAMESPACE, f"region-{index}"), map_id=knowledge_map.id,
                title=title, min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y,
                style=style, status=ContentStatus.published,
            )
            regions.append(region)
            db.add(region)
            db.flush()
            terrain = Layer(
                id=uuid.uuid5(NAMESPACE, f"layer-terrain-{index}"), region_id=region.id,
                kind="terrain", z_index=10, min_zoom=-4, max_zoom=5,
            )
            roads = Layer(
                id=uuid.uuid5(NAMESPACE, f"layer-roads-{index}"), region_id=region.id,
                kind="roads", z_index=20, min_zoom=-3, max_zoom=5,
            )
            db.add_all([terrain, roads])
            db.flush()
            db.add(TerrainFeature(
                layer_id=terrain.id, feature_type="polygon",
                geometry={"points": [[min_x + 40, min_y + 80], [max_x - 80, min_y + 30], [max_x - 30, max_y - 120], [min_x + 100, max_y - 40]]},
                style={"fill": style["fill"], "stroke": style["accent"]},
            ))
            db.add(TerrainFeature(
                layer_id=roads.id, feature_type="polyline",
                geometry={"points": [[min_x + 140, max_y - 180], [min_x + 480, max_y - 620], [max_x - 180, min_y + 180]]},
                style={"stroke": "#854d0e", "weight": 8},
            ))
        topics: list[Topic] = []
        placements: list[Placement] = []
        for title, summary, region_index, x, y, min_zoom in TOPICS:
            topic_id = uuid.uuid5(NAMESPACE, f"topic-{slugify(title)}")
            revision_id = uuid.uuid5(NAMESPACE, f"revision-{slugify(title)}")
            topic = Topic(
                id=topic_id, slug=slugify(title), status=ContentStatus.published,
                published_revision_id=revision_id, created_by=demo_user.id,
            )
            revision = TopicRevision(
                id=revision_id, topic_id=topic_id, revision_number=1, title=title,
                summary=summary,
                content={
                    "schema_version": 1,
                    "blocks": [
                        block("callout", {"kind": "note", "text": "Demonstration content: concise orientation, not a complete treatment."}),
                        block("heading", {"level": 2, "text": "Why it matters"}),
                        block("paragraph", {"text": f"{title} provides a useful landmark in the wider knowledge landscape. Follow its relationships to compare neighbouring ideas and cross disciplinary boundaries."}),
                    ],
                },
                language="en", change_note="Original demonstration seed",
                created_by=demo_user.id, review_state="published", reviewed_by=demo_user.id,
            )
            placement = Placement(
                id=uuid.uuid5(NAMESPACE, f"placement-{slugify(title)}"), topic_id=topic_id,
                map_id=knowledge_map.id, region_id=regions[region_index].id,
                x=x, y=y, icon="observatory" if min_zoom <= -3 else "building",
                min_zoom=min_zoom, max_zoom=5, label_priority=5 - int(min_zoom),
                status=ContentStatus.published,
            )
            db.add_all([topic, revision])
            db.flush()
            db.add(placement)
            topics.append(topic)
            placements.append(placement)
        db.flush()
        for left, right, kind, explanation in [
            (0, 1, "broader_than", "Machine learning is one approach within AI."),
            (1, 2, "broader_than", "Neural networks are a major family of learning methods."),
            (5, 6, "broader_than", "Retrieval is one design for external memory."),
            (3, 13, "related_to", "Both centre technical practice on human and public outcomes."),
            (10, 11, "broader_than", "Digital public infrastructure is one expression of public technology."),
            (14, 18, "prerequisite_for", "Open standards often enable interoperability."),
            (21, 23, "related_to", "Entropy measures uncertainty in information theory."),
            (22, 23, "related_to", "Thermodynamic entropy counts accessible microscopic configurations."),
            (24, 27, "related_to", "Feedback and resilience both concern behaviour under changing conditions."),
            (25, 28, "related_to", "Network structure often shapes complex-system behaviour."),
            (26, 4, "related_to", "Bayesian reasoning is widely used in evaluation under uncertainty."),
        ]:
            source, target = topics[left], topics[right]
            if kind == "related_to" and source.id.int > target.id.int:
                source, target = target, source
            db.add(Relationship(
                source_topic_id=source.id, target_topic_id=target.id, kind=kind,
                explanation=explanation, status=ContentStatus.published, created_by=demo_user.id,
            ))
        trail = Trail(
            id=uuid.uuid5(NAMESPACE, "trail-ai-human-public"), title="From AI to public value",
            summary="A branching demonstration route from technical foundations to accountable practice.",
            map_id=knowledge_map.id, visibility="public", status=ContentStatus.published,
            created_by=demo_user.id,
        )
        db.add(trail)
        db.flush()
        trail_indices = [0, 1, 3, 4, 17, 13]
        steps = []
        for order, topic_index in enumerate(trail_indices):
            step = TrailStep(
                id=uuid.uuid5(NAMESPACE, f"trail-step-{order}"), trail_id=trail.id,
                topic_id=topics[topic_index].id,
                preferred_placement_id=placements[topic_index].id,
                note="Follow the main path." if order < 4 else "Choose a governance or design branch.",
            )
            db.add(step)
            steps.append(step)
        trail.start_step_id = steps[0].id
        db.flush()
        for order in range(4):
            db.add(TrailEdge(trail_id=trail.id, from_step_id=steps[order].id, to_step_id=steps[order + 1].id, is_default=True))
        db.add(TrailEdge(trail_id=trail.id, from_step_id=steps[3].id, to_step_id=steps[5].id, label="Public-interest design", is_default=False))
        db.commit()
        print(f"Seeded map {knowledge_map.id} with {len(TOPICS)} demonstration topics.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Explicitly seed demonstration data")
    args = parser.parse_args()
    if not args.demo:
        raise SystemExit("Refusing to seed without explicit --demo")
    seed_demo()


if __name__ == "__main__":
    main()
