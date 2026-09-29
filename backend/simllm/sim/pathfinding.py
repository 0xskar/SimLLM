from __future__ import annotations

import heapq

Point = tuple[int, int]


def find_path(
    start: Point,
    goal: Point,
    width: int,
    height: int,
    blocked: set[Point],
) -> list[Point] | None:
    """4-directional A* on the world grid.

    Returns the sequence of steps to take (excluding `start`, including
    `goal`), `[]` if already at the goal, or `None` if unreachable. The
    goal is always walkable even if it's in `blocked` (e.g. a building
    tile) -- you must always be able to arrive at your own destination.
    """
    if start == goal:
        return []

    blocked = blocked - {goal}

    def heuristic(a: Point, b: Point) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    open_heap: list[tuple[int, int, Point]] = [(heuristic(start, goal), 0, start)]
    came_from: dict[Point, Point] = {}
    g_score = {start: 0}
    visited: set[Point] = set()

    while open_heap:
        _, g, current = heapq.heappop(open_heap)
        if current in visited:
            continue
        visited.add(current)

        if current == goal:
            path = []
            node = current
            while node != start:
                path.append(node)
                node = came_from[node]
            path.reverse()
            return path

        x, y = current
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            neighbor = (x + dx, y + dy)
            nx, ny = neighbor
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if neighbor in blocked or neighbor in visited:
                continue
            tentative_g = g + 1
            if tentative_g < g_score.get(neighbor, float("inf")):
                g_score[neighbor] = tentative_g
                came_from[neighbor] = current
                heapq.heappush(open_heap, (tentative_g + heuristic(neighbor, goal), tentative_g, neighbor))

    return None
