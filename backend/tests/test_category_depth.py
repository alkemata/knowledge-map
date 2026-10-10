import uuid

import pytest

from app.services import category_depth, depth_min_zoom


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
