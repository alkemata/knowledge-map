import math
import uuid
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator, model_validator


BlockType = Literal[
    "paragraph", "heading", "list", "equation", "image", "source",
    "external_link", "topic_link", "video", "callout",
]
ALLOWED_VIDEO_PROVIDERS = {"youtube", "vimeo", "peertube"}
ALLOWED_ICONS = {"building", "library", "tower", "workshop", "observatory", "bridge"}
ALLOWED_RELATIONS = {"related_to", "prerequisite_for", "example_of", "contradicts", "broader_than"}


def require_https(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Only absolute HTTPS URLs are accepted")
    return value


class ContentBlock(BaseModel):
    id: uuid.UUID
    type: BlockType
    data: dict[str, Any]

    @model_validator(mode="after")
    def validate_data(self) -> "ContentBlock":
        serialized = str(self.data)
        if len(serialized) > 100_000:
            raise ValueError("Block exceeds 100 kB")
        if self.type in {"paragraph", "heading", "callout"} and not isinstance(self.data.get("text"), str):
            raise ValueError(f"{self.type} requires data.text")
        if self.type == "list" and not isinstance(self.data.get("items"), list):
            raise ValueError("list requires data.items")
        if self.type == "equation" and not isinstance(self.data.get("latex"), str):
            raise ValueError("equation requires data.latex")
        if self.type == "image" and not self.data.get("asset_id"):
            raise ValueError("image requires data.asset_id")
        if self.type == "source" and not self.data.get("source_id"):
            raise ValueError("source requires data.source_id")
        if self.type == "external_link":
            require_https(str(self.data.get("url", "")))
        if self.type == "topic_link":
            uuid.UUID(str(self.data.get("target_topic_id")))
        if self.type == "video":
            if self.data.get("provider") not in ALLOWED_VIDEO_PROVIDERS:
                raise ValueError("Unsupported video provider")
            require_https(str(self.data.get("fallback_url", "")))
        return self


class ContentEnvelope(BaseModel):
    schema_version: Literal[1] = 1
    blocks: list[ContentBlock] = Field(max_length=250)


class PlacementInput(BaseModel):
    map_id: uuid.UUID
    region_id: uuid.UUID | None = None
    x: float
    y: float
    icon: str = "building"
    min_zoom: float = -4
    max_zoom: float = 5
    label_priority: int = 0

    @model_validator(mode="after")
    def validate_coordinates(self) -> "PlacementInput":
        if not all(math.isfinite(v) for v in (self.x, self.y, self.min_zoom, self.max_zoom)):
            raise ValueError("Coordinates and zoom values must be finite")
        if not -8 <= self.min_zoom < self.max_zoom <= 8:
            raise ValueError("Expected -8 <= min_zoom < max_zoom <= 8")
        if self.icon not in ALLOWED_ICONS:
            raise ValueError("Unsupported icon")
        return self


class TopicCreate(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    summary: str = Field(min_length=2, max_length=3000)
    content: ContentEnvelope
    language: str = Field(default="en", pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
    change_note: str = Field(default="Initial version", max_length=500)
    placement: PlacementInput | None = None


class TopicRevisionCreate(BaseModel):
    expected_revision: int = Field(ge=1)
    title: str = Field(min_length=2, max_length=240)
    summary: str = Field(min_length=2, max_length=3000)
    content: ContentEnvelope
    language: str = Field(default="en", pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
    change_note: str = Field(min_length=2, max_length=500)


class PlacementPatch(BaseModel):
    base_version: int = Field(ge=1)
    x: float
    y: float

    @model_validator(mode="after")
    def finite(self) -> "PlacementPatch":
        if not math.isfinite(self.x) or not math.isfinite(self.y):
            raise ValueError("Coordinates must be finite")
        return self


class RelationshipCreate(BaseModel):
    source_topic_id: uuid.UUID
    target_topic_id: uuid.UUID
    kind: str
    explanation: str = Field(default="", max_length=3000)

    @model_validator(mode="after")
    def valid(self) -> "RelationshipCreate":
        if self.source_topic_id == self.target_topic_id:
            raise ValueError("Self relationships are not allowed")
        if self.kind not in ALLOWED_RELATIONS:
            raise ValueError("Unsupported relationship type")
        return self


class TrailStepInput(BaseModel):
    client_id: str = Field(min_length=1, max_length=80)
    topic_id: uuid.UUID
    preferred_placement_id: uuid.UUID | None = None
    note: str = Field(default="", max_length=3000)


class TrailEdgeInput(BaseModel):
    from_client_id: str
    to_client_id: str
    label: str = Field(default="", max_length=120)
    is_default: bool = False


class TrailCreate(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    summary: str = Field(default="", max_length=3000)
    map_id: uuid.UUID | None = None
    steps: list[TrailStepInput] = Field(min_length=1, max_length=100)
    edges: list[TrailEdgeInput] = Field(default_factory=list, max_length=250)
    start_client_id: str

    @model_validator(mode="after")
    def validate_graph(self) -> "TrailCreate":
        ids = [step.client_id for step in self.steps]
        if len(ids) != len(set(ids)) or self.start_client_id not in ids:
            raise ValueError("Step client IDs must be unique and include the start step")
        defaults: dict[str, int] = {}
        for edge in self.edges:
            if edge.from_client_id not in ids or edge.to_client_id not in ids:
                raise ValueError("Every edge must reference steps in this trail")
            defaults[edge.from_client_id] = defaults.get(edge.from_client_id, 0) + int(edge.is_default)
        if any(value > 1 for value in defaults.values()):
            raise ValueError("At most one default outgoing edge is allowed")
        return self


class Bounds(BaseModel):
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @model_validator(mode="after")
    def valid(self) -> "Bounds":
        values = (self.min_x, self.min_y, self.max_x, self.max_y)
        if not all(math.isfinite(v) for v in values) or self.min_x >= self.max_x or self.min_y >= self.max_y:
            raise ValueError("Invalid finite bounds")
        return self


class RegionCreate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    bounds: Bounds
    style: dict[str, Any] = Field(default_factory=dict)


class TerrainFeatureInput(BaseModel):
    feature_type: Literal["symbol", "polyline", "polygon"]
    geometry: dict[str, Any]
    symbol: Literal["building", "tree", "mountain"] | None = None
    style: dict[str, Any] = Field(default_factory=dict)
    base_version: int | None = None

    @model_validator(mode="after")
    def validate_geometry(self) -> "TerrainFeatureInput":
        allowed_colors = {"#164e63", "#166534", "#365314", "#854d0e", "#334155", "#0e7490", "#f1f5f9"}
        for key in ("fill", "stroke"):
            if key in self.style and self.style[key] not in allowed_colors:
                raise ValueError(f"{key} is outside the bounded palette")
        points = self.geometry.get("points", [])
        if len(points) > 500:
            raise ValueError("Geometry is limited to 500 vertices")
        for point in points:
            if not isinstance(point, list) or len(point) != 2 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in point):
                raise ValueError("Each vertex must be a finite [x,y] pair")
        return self


class LoginInput(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=512)

