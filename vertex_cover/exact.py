"""Exact branch-and-bound minimum vertex cover.

Assigned student owner: Derek Song. Initial implementation is AI-generated
with Codex; ownership is an assignment responsibility, not a claim that the
student independently authored this initial code. Review and disclose its use.

Branching rule: an uncovered edge (u, v) forces every completion to include
u or v. An explicit depth-first stack avoids Python recursion-depth limits.
"""

from dataclasses import dataclass
from math import isfinite
from time import perf_counter
from typing import Literal

from .graph import Edge, Graph


@dataclass(frozen=True)
class SearchStats:
    nodes_visited: int
    nodes_expanded: int
    pruned_by_size: int
    pruned_by_bound: int
    leaves: int
    incumbent_updates: int
    max_stack_size: int
    elapsed_seconds: float


@dataclass(frozen=True)
class ExactResult:
    cover: frozenset[int]
    status: Literal["optimal", "timeout", "node_limit"]
    lower_bound: int
    stats: SearchStats

    @property
    def optimal(self) -> bool:
        return self.status == "optimal"

    @property
    def cover_size(self) -> int:
        return len(self.cover)


def _matching_bound(edges: tuple[Edge, ...]) -> int:
    """Any cover needs >= one distinct vertex per disjoint matching edge.

    This greedy matching is an internal lower bound, not the partner's
    approximation solver. Even a non-maximum matching gives a safe bound.
    """
    used = 0
    count = 0
    for u, v in edges:
        endpoints = (1 << u) | (1 << v)
        if not used & endpoints:
            used |= endpoints
            count += 1
    return count


def _branch_edge(edges: tuple[Edge, ...]) -> Edge:
    """Prefer high-degree endpoints; resolve ties deterministically."""
    degrees: dict[int, int] = {}
    for u, v in edges:
        degrees[u] = degrees.get(u, 0) + 1
        degrees[v] = degrees.get(v, 0) + 1
    u, v = max(edges, key=lambda e: (degrees[e[0]] + degrees[e[1]], -e[0], -e[1]))
    if degrees[v] > degrees[u]:
        return v, u
    return u, v


def solve_exact(
    graph: Graph,
    *,
    time_limit: float | None = None,
    node_limit: int | None = None,
) -> ExactResult:
    """Return a feasible cover and an explicit optimality status.

    Limits include solver setup time but exclude graph construction and I/O.
    The time limit is cooperative: checked between search nodes, so a single
    node's processing can overrun it. node_limit caps visited search nodes.
    On interruption, lower_bound is the initial matching bound; it is valid
    but may be weaker than bounds discovered during search.
    """
    if not isinstance(graph, Graph):
        raise TypeError("graph must be a Graph")
    if time_limit is not None:
        if (type(time_limit) not in (int, float)
                or not isfinite(time_limit) or time_limit < 0):
            raise ValueError("time_limit must be a finite non-negative number or None")
    if node_limit is not None and (type(node_limit) is not int or node_limit < 0):
        raise ValueError("node_limit must be a non-negative integer or None")

    started = perf_counter()
    deadline = None if time_limit is None else started + time_limit
    best_mask = 0
    for u, v in graph.edges:
        best_mask |= (1 << u) | (1 << v)
    best_size = best_mask.bit_count()
    root_bound = _matching_bound(graph.edges)
    # Every state records uncovered edges and vertices already selected.
    stack = [(graph.edges, 0, 0)] if graph.edges else []
    visited = expanded = pruned_size = pruned_bound = leaves = updates = 0
    max_stack = len(stack)
    status = "optimal"

    while stack:
        if deadline is not None and perf_counter() >= deadline:
            status = "timeout"
            break
        if node_limit is not None and visited >= node_limit:
            status = "node_limit"
            break
        remaining, chosen, chosen_size = stack.pop()
        visited += 1
        if chosen_size >= best_size:
            pruned_size += 1
            continue
        if not remaining:
            leaves += 1
            best_mask, best_size = chosen, chosen_size
            updates += 1
            if best_size == root_bound:
                # Feasible upper bound equals a proven global lower bound.
                stack.clear()
            continue
        if chosen_size + _matching_bound(remaining) >= best_size:
            pruned_bound += 1
            continue
        expanded += 1
        u, v = _branch_edge(remaining)
        # LIFO: push v first so the preferred endpoint u is explored first.
        for vertex in (v, u):
            child_edges = tuple(e for e in remaining if vertex not in e)
            stack.append((child_edges, chosen | (1 << vertex), chosen_size + 1))
        max_stack = max(max_stack, len(stack))

    cover = frozenset(v for v in range(graph.num_vertices) if best_mask & (1 << v))
    stats = SearchStats(visited, expanded, pruned_size, pruned_bound, leaves,
                        updates, max_stack, perf_counter() - started)
    return ExactResult(cover, status, best_size if status == "optimal" else root_bound, stats)
