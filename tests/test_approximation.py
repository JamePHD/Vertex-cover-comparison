"""Independent feasibility, approximation-bound, and compatibility checks."""

from dataclasses import FrozenInstanceError
from itertools import combinations
import random
import unittest

from tests.helpers import brute_force_optimum
from vertex_cover import ApproximationResult, Graph, is_vertex_cover, solve_approximation, solve_exact


class ApproximationTests(unittest.TestCase):
    def check_result(self, graph, optimum=None):
        original = (graph.num_vertices, graph.edges)
        result = solve_approximation(graph)
        self.assertIsInstance(result, ApproximationResult)
        self.assertIsInstance(result.cover, frozenset)
        self.assertIsInstance(result.matching, tuple)
        self.assertTrue(is_vertex_cover(graph, result.cover))
        endpoints = set()
        input_edges = set(graph.edges)
        for edge in result.matching:
            self.assertIn(edge, input_edges)
            u, v = edge
            self.assertNotIn(u, endpoints)
            self.assertNotIn(v, endpoints)
            endpoints.update(edge)
        self.assertEqual(result.cover, endpoints)
        self.assertEqual(result.cover_size, 2 * result.matching_size)
        self.assertEqual(result.lower_bound, result.matching_size)
        self.assertTrue(all(u in endpoints or v in endpoints for u, v in graph.edges))
        self.assertEqual(result.matching, tuple(sorted(result.matching)))
        self.assertEqual(original, (graph.num_vertices, graph.edges))
        self.assertEqual(result, solve_approximation(graph))
        if optimum is None:
            optimum = brute_force_optimum(graph.num_vertices, graph.edges)
        self.assertLessEqual(result.lower_bound, optimum)
        self.assertLessEqual(optimum, result.cover_size)
        self.assertLessEqual(result.cover_size, 2 * optimum)
        return result

    def test_all_simple_graphs_through_five_vertices(self):
        cases = 0
        for n in range(6):
            possible = tuple(combinations(range(n), 2))
            for mask in range(1 << len(possible)):
                edges = [e for i, e in enumerate(possible) if mask & (1 << i)]
                with self.subTest(n=n, mask=mask):
                    self.check_result(Graph(n, edges))
                cases += 1
        self.assertEqual(cases, 1100)

    def test_seeded_random_graphs_against_brute_force(self):
        rng = random.Random(20261102)
        for n in range(12):
            for repetition in range(25):
                probability = rng.random()
                edges = [e for e in combinations(range(n), 2) if rng.random() < probability]
                with self.subTest(n=n, repetition=repetition):
                    self.check_result(Graph(n, edges))

    def test_empty_and_isolated_vertices(self):
        for n in (0, 1, 30):
            with self.subTest(n=n):
                self.assertEqual(self.check_result(Graph(n)), ApproximationResult(frozenset(), ()))

    def test_structured_families(self):
        for n in range(2, 14):
            families = [
                (Graph(n, ((0, i) for i in range(1, n))), 2, 1),
                (Graph(n, ((i, i + 1) for i in range(0, n - 1, 2))), 2 * (n // 2), n // 2),
                (Graph(n, combinations(range(n), 2)), 2 * (n // 2), n - 1),
                (Graph(n, ((i, i + 1) for i in range(n - 1))), 2 * (n // 2), n // 2),
            ]
            if n >= 3:
                families.append((Graph(n, ((i, (i + 1) % n) for i in range(n))),
                                 2 * (n // 2), (n + 1) // 2))
            for graph, size, optimum in families:
                with self.subTest(n=n, edges=graph.edges):
                    self.assertEqual(self.check_result(graph, optimum).cover_size, size)

    def test_disconnected_components_and_isolates(self):
        graph = Graph(10, [(0, 1), (1, 2), (0, 2), (3, 4), (3, 5), (3, 6)])
        result = self.check_result(graph)
        self.assertEqual(result.matching, ((0, 1), (3, 4)))
        self.assertFalse(result.cover & {7, 8, 9})

    def test_canonical_order_and_relabelled_path(self):
        path = Graph(4, [(0, 1), (1, 2), (2, 3)])
        result = self.check_result(path)
        self.assertEqual(result.matching, ((0, 1), (2, 3)))
        reordered = Graph(4, [(3, 2), (2, 1), (1, 0), (0, 1)])
        self.assertEqual(result, self.check_result(reordered))
        relabelled = Graph(4, [(0, 1), (0, 2), (1, 3)])
        self.assertEqual(self.check_result(relabelled).matching, ((0, 1),))

    def test_results_are_immutable_and_calls_do_not_share_state(self):
        result = solve_approximation(Graph(2, [(0, 1)]))
        with self.assertRaises(FrozenInstanceError):
            result.cover = frozenset()
        with self.assertRaises(FrozenInstanceError):
            result.matching = ()
        self.check_result(Graph(2))
        self.assertEqual(result, solve_approximation(Graph(2, [(0, 1)])))

    def test_non_graph_arguments(self):
        for bad in (None, [], {}, 3, "graph", [(0, 1)]):
            with self.subTest(value=bad), self.assertRaisesRegex(TypeError, "graph must be a Graph"):
                solve_approximation(bad)

    def test_same_graph_works_with_both_solvers(self):
        graph = Graph(4, [(0, 1), (1, 2), (2, 3)])
        approximation = self.check_result(graph)
        exact = solve_exact(graph)
        self.assertTrue(exact.optimal)
        self.assertEqual(exact.cover_size, 2)
        self.assertEqual(approximation.cover_size, 2 * exact.cover_size)
        interrupted = solve_exact(graph, node_limit=0)
        self.assertFalse(interrupted.optimal)
        self.assertTrue(is_vertex_cover(graph, interrupted.cover))
        self.assertEqual(approximation, solve_approximation(graph))

    def test_large_sparse_graph_without_recursion(self):
        n = 100_000
        graph = Graph(n, ((i, i + 1) for i in range(0, n, 2)))
        result = self.check_result(graph, n // 2)
        self.assertEqual(result.cover_size, n)


if __name__ == "__main__":
    unittest.main()
