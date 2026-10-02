import uuid
import pytest
from pydantic import ValidationError

from app.schemas import ContentBlock, PlacementInput


def test_external_links_require_https():
    with pytest.raises(ValidationError):
        ContentBlock(
            id=uuid.uuid4(), type="external_link",
            data={"url": "javascript:alert(1)", "label": "unsafe"},
        )


def test_zoom_interval_is_half_open():
    item = PlacementInput(
        map_id=uuid.uuid4(), x=1200, y=1800,
        min_zoom=-2, max_zoom=0,
    )
    assert item.min_zoom <= -1 < item.max_zoom


def test_rejects_non_finite_coordinates():
    with pytest.raises(ValidationError):
        PlacementInput(map_id=uuid.uuid4(), x=float("inf"), y=1)
