"""Independent small-instance oracles and externally observable solver contracts."""

from itertools import combinations
import math
import random
import unittest

from vertex_cover import Graph, is_vertex_cover, solve_exact


def brute_force_optimum(n, edges):
    # Deliberately use subsets and direct edge checks, not solver internals.
    for size in range(n + 1):
        for candidate in combinations(range(n), size):
            chosen = set(candidate)
            if all(u in chosen or v in chosen for u, v in edges):
                return size
    raise AssertionError("all vertices must be a feasible cover")


class ExactTests(unittest.TestCase):
    def check_optimum(self, graph):
        original_edges = graph.edges
        result = solve_exact(graph)
        expected = brute_force_optimum(graph.num_vertices, graph.edges)
        self.assertTrue(is_vertex_cover(graph, result.cover))
        self.assertTrue(result.optimal)
        self.assertEqual(result.status, "optimal")
        self.assertEqual(result.cover_size, expected)
        self.assertEqual(result.lower_bound, expected)
        self.assertEqual(graph.edges, original_edges)
        stats = result.stats
        self.assertEqual(stats.nodes_visited, stats.nodes_expanded + stats.pruned_by_size
                         + stats.pruned_by_bound + stats.leaves)
        self.assertGreaterEqual(stats.elapsed_seconds, 0)

    def test_all_simple_graphs_through_five_vertices(self):
        cases = 0
        for n in range(6):
            possible = tuple(combinations(range(n), 2))
            for mask in range(1 << len(possible)):
                edges = [e for i, e in enumerate(possible) if mask & (1 << i)]
                with self.subTest(n=n, mask=mask):
                    self.check_optimum(Graph(n, edges))
                cases += 1
        self.assertEqual(cases, 1100)

    def test_seeded_random_graphs_against_brute_force(self):
        rng = random.Random(20261102)
        for n in range(12):
            for repetition in range(25):
                probability = rng.random()
                edges = [e for e in combinations(range(n), 2) if rng.random() < probability]
                with self.subTest(n=n, repetition=repetition):
                    self.check_optimum(Graph(n, edges))

    def test_structured_graphs(self):
        for n in range(2, 13):
            families = [
                (Graph(n, ((0, i) for i in range(1, n))), 1),
                (Graph(n, ((i, i + 1) for i in range(n - 1))), n // 2),
                (Graph(n, combinations(range(n), 2)), n - 1),
            ]
            if n >= 3:
                families.append((Graph(n, ((i, (i + 1) % n) for i in range(n))), (n + 1) // 2))
            for graph, expected in families:
                with self.subTest(n=n, edges=graph.edges):
                    self.assertEqual(solve_exact(graph).cover_size, expected)
                    self.check_optimum(graph)

    def test_disconnected_graph_and_isolated_vertices(self):
        graph = Graph(10, [(0, 1), (1, 2), (0, 2), (3, 4), (3, 5), (3, 6)])
        result = solve_exact(graph)
        self.assertEqual(result.cover_size, 3)
        self.assertFalse(result.cover & {7, 8, 9})
        self.check_optimum(graph)

    def test_zero_time_limit_returns_feasible_unproven_answer(self):
        graph = Graph(5, [(0, i) for i in range(1, 5)])
        result = solve_exact(graph, time_limit=0)
        self.assertEqual(result.status, "timeout")
        self.assertFalse(result.optimal)
        self.assertTrue(is_vertex_cover(graph, result.cover))
        self.assertLessEqual(result.lower_bound, 1)
        self.assertGreaterEqual(result.cover_size, 1)

    def test_node_limit_results_remain_valid_with_safe_bounds(self):
        graph = Graph(9, [(i, (i + 1) % 9) for i in range(9)])
        optimum = brute_force_optimum(graph.num_vertices, graph.edges)
        saw_interrupted = saw_optimal = False
        for budget in [0, 1, 2, 3, 5, 10, 20, 1000]:
            result = solve_exact(graph, node_limit=budget)
            self.assertTrue(is_vertex_cover(graph, result.cover))
            self.assertLessEqual(result.stats.nodes_visited, budget)
            self.assertLessEqual(result.lower_bound, optimum)
            self.assertGreaterEqual(result.cover_size, optimum)
            if result.optimal:
                saw_optimal = True
                self.assertEqual(result.cover_size, optimum)
            else:
                saw_interrupted = True
                self.assertEqual(result.status, "node_limit")
        self.assertTrue(saw_interrupted and saw_optimal)

    def test_empty_graph_is_proved_even_with_zero_limits(self):
        result = solve_exact(Graph(30), time_limit=0, node_limit=0)
        self.assertTrue(result.optimal)
        self.assertEqual(result.cover, frozenset())

    def test_results_are_deterministic_for_same_graph(self):
        graph = Graph(7, [(i, (i + 1) % 7) for i in range(7)])
        a, b = solve_exact(graph), solve_exact(graph)
        self.assertEqual(a.cover, b.cover)
        self.assertEqual(a.stats.nodes_visited, b.stats.nodes_visited)

    def test_invalid_limits(self):
        graph = Graph(2, [(0, 1)])
        for bad in [-1, math.inf, math.nan, True, "1"]:
            with self.subTest(time_limit=bad), self.assertRaises(ValueError):
                solve_exact(graph, time_limit=bad)
        for bad in [-1, 1.5, True, "1"]:
            with self.subTest(node_limit=bad), self.assertRaises(ValueError):
                solve_exact(graph, node_limit=bad)


class GraphTests(unittest.TestCase):
    def test_normalizes_direction_and_duplicates(self):
        self.assertEqual(Graph(4, [(2, 0), (0, 2), (1, 0)]).edges, ((0, 1), (0, 2)))

    def test_invalid_graphs(self):
        for n, edges in [(-1, []), (True, []), (2.5, []), (2, [(0, 0)]),
                         (2, [(-1, 1)]), (2, [(0, 2)]), (2, [(False, 1)]),
                         (2, [(0.0, 1)]), (2, [(0,)]), (2, [(0, 1, 2)]), (2, [None])]:
            with self.subTest(n=n, edges=edges), self.assertRaises(ValueError):
                Graph(n, edges)

    def test_cover_validator_rejects_bad_identifiers_and_missing_edges(self):
        graph = Graph(3, [(0, 1), (1, 2)])
        self.assertTrue(is_vertex_cover(graph, [1]))
        self.assertFalse(is_vertex_cover(graph, [0]))
        for bad in [[1, 4], [1, True], [True, 1], [-1, 1], [1.0]]:
            with self.subTest(cover=bad):
                self.assertFalse(is_vertex_cover(graph, bad))


if __name__ == "__main__":
    unittest.main()
