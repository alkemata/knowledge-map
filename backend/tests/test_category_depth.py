import uuid

import pytest

from app.models import Region
from app.services import category_depth, depth_min_zoom, destination_region


def test_category_depth_and_zoom_layers():
    root, child, grandchild = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    parents = {child: root, grandchild: child}
    assert category_depth(root, parents) == 0
    assert category_depth(child, parents) == 1
    assert category_depth(grandchild, parents) == 2
    assert [depth_min_zoom(level) for level in range(4)] == [-4, -2, 0, 2]


def test_category_cycle_rejected():
    first, second = uuid.uuid4(), uuid.uuid4()
    with pytest.raises(ValueError, match="cycle"):
        category_depth(first, {first: second, second: first})


def test_drag_can_leave_a_legacy_region():
    map_id, old_id, next_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    old = Region(id=old_id, map_id=map_id, title="Old", min_x=0, min_y=0, max_x=100, max_y=100)
    next_region = Region(id=next_id, map_id=map_id, title="Next", min_x=100, min_y=0, max_x=200, max_y=100)
    regions = [old, next_region]
    assert destination_region(regions, old_id, 50, 50) == old_id
    assert destination_region(regions, old_id, 150, 50) == next_id
    assert destination_region(regions, old_id, 250, 50) is None
