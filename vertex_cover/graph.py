"""Common input and validation for both students' solvers.

Scope: simple, unweighted, undirected graphs with vertices 0 .. n-1.
Input edge direction and repeated edges do not change the graph.
"""

from dataclasses import dataclass
from typing import Iterable

Edge = tuple[int, int]


@dataclass(frozen=True, init=False)
class Graph:
    num_vertices: int
    edges: tuple[Edge, ...]

    def __init__(self, num_vertices: int, edges: Iterable[Edge] = ()) -> None:
        if type(num_vertices) is not int or num_vertices < 0:
            raise ValueError("num_vertices must be a non-negative integer")
        normalized = set()
        for edge in edges:
            try:
                u, v = edge
            except (TypeError, ValueError) as exc:
                raise ValueError("each edge must contain exactly two vertices") from exc
            if type(u) is not int or type(v) is not int:
                raise ValueError("vertex identifiers must be integers")
            if not (0 <= u < num_vertices and 0 <= v < num_vertices):
                raise ValueError("vertex identifier outside 0 .. num_vertices-1")
            if u == v:
                raise ValueError("self-loops are outside this project's graph scope")
            normalized.add((min(u, v), max(u, v)))
        object.__setattr__(self, "num_vertices", num_vertices)
        object.__setattr__(self, "edges", tuple(sorted(normalized)))


def is_vertex_cover(graph: Graph, vertices: Iterable[int]) -> bool:
    """Check feasibility, including the validity of supplied vertex identifiers."""
    supplied = tuple(vertices)
    if any(type(v) is not int or not 0 <= v < graph.num_vertices for v in supplied):
        return False
    chosen = set(supplied)
    return all(u in chosen or v in chosen for u, v in graph.edges)
