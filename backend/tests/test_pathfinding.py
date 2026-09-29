from __future__ import annotations

from simllm.sim.pathfinding import find_path


def test_already_at_goal_returns_empty_path():
    assert find_path((3, 3), (3, 3), 10, 10, set()) == []


def test_straight_line_path_with_no_obstacles():
    path = find_path((0, 0), (3, 0), 10, 10, set())

    assert path == [(1, 0), (2, 0), (3, 0)]


def test_path_length_matches_manhattan_distance_when_unobstructed():
    path = find_path((0, 0), (4, 3), 20, 20, set())

    assert path is not None
    assert len(path) == 4 + 3
    assert path[-1] == (4, 3)


def test_path_routes_around_a_blocked_tile():
    # Wall across y=1 except a gap at x=5.
    blocked = {(x, 1) for x in range(10) if x != 5}

    path = find_path((0, 0), (0, 2), 10, 10, blocked)

    assert path is not None
    assert path[-1] == (0, 2)
    assert all(step not in blocked for step in path)


def test_goal_on_a_blocked_tile_is_still_reachable():
    # The destination itself is a "blocked" tile type (e.g. a house) --
    # you must always be able to walk onto your own destination.
    blocked = {(2, 0)}

    path = find_path((0, 0), (2, 0), 10, 10, blocked)

    assert path == [(1, 0), (2, 0)]


def test_completely_enclosed_goal_is_unreachable():
    # Surround (5, 5) on all four sides.
    blocked = {(4, 5), (6, 5), (5, 4), (5, 6)}

    path = find_path((0, 0), (5, 5), 10, 10, blocked)

    assert path is None


def test_path_never_leaves_grid_bounds():
    path = find_path((0, 0), (2, 2), 3, 3, set())

    assert path is not None
    assert all(0 <= x < 3 and 0 <= y < 3 for x, y in path)
