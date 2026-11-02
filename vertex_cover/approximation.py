"""Deterministic maximal-matching 2-approximation for minimum vertex cover."""

from dataclasses import dataclass

from .graph import Edge, Graph


@dataclass(frozen=True)
class ApproximationResult:
    """A feasible cover and the matching that certifies its factor-two bound."""

    cover: frozenset[int]
    matching: tuple[Edge, ...]

    @property
    def cover_size(self) -> int:
        return len(self.cover)

    @property
    def matching_size(self) -> int:
        return len(self.matching)

    @property
    def lower_bound(self) -> int:
        return self.matching_size


def solve_approximation(graph: Graph) -> ApproximationResult:
    """Return both endpoints of a greedy maximal matching.

    Visit Graph.edges in canonical order, selecting an edge only when both
    endpoints are unused. Every skipped edge has a selected endpoint, so the
    returned endpoints cover every edge. Every cover needs a distinct vertex
    for each matching edge; returning two per edge gives size <= 2 * OPT.

    Uses O(n + m) time and O(n) space, including result construction. The
    graph is unchanged, and each call uses fresh state. Optimality is not
    assessed; lower_bound <= OPT <= cover_size holds for every result.
    """
    if not isinstance(graph, Graph):
        raise TypeError("graph must be a Graph")

    matched = [False] * graph.num_vertices
    matching: list[Edge] = []
    for u, v in graph.edges:
        if not matched[u] and not matched[v]:
            matching.append((u, v))
            matched[u] = matched[v] = True

    cover = frozenset(v for v, used in enumerate(matched) if used)
    return ApproximationResult(cover, tuple(matching))
