"""Small-instance oracle independent of either solver."""

from itertools import combinations


def brute_force_optimum(n, edges):
    # Deliberately use subsets and direct edge checks, not solver internals.
    for size in range(n + 1):
        for candidate in combinations(range(n), size):
            chosen = set(candidate)
            if all(u in chosen or v in chosen for u, v in edges):
                return size
    raise AssertionError("all vertices must be a feasible cover")
