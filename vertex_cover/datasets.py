"""Seeded graph generation, canonical hashes, and a self-contained input manifest."""

from datetime import datetime, timezone
from hashlib import sha256
from itertools import combinations
import json
from math import isfinite
from pathlib import Path
import random

from .graph import Graph

FAMILIES = {"path", "cycle", "star", "clique", "disjoint_edges", "complete_bipartite"}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(data):
    return sha256(data).hexdigest()


def graph_payload(graph):
    return {"num_vertices": graph.num_vertices, "edges": [list(e) for e in graph.edges]}


def graph_digest(graph):
    return digest(canonical_bytes(graph_payload(graph)))


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def new_directory(path):
    path = Path(path)
    # Never mix fresh measurements with pre-existing files or clobber results.
    path.mkdir(parents=True, exist_ok=False)
    return path


def make_graph(family, n, *, probability=None, seed=0):
    if type(n) is not int or n < 0:
        raise ValueError("graph size must be a non-negative integer")
    if family == "gnp":
        if (type(probability) not in (float, int) or not isfinite(probability)
                or not 0 <= probability <= 1 or type(seed) is not int):
            raise ValueError("gnp requires probability in [0, 1] and an integer seed")
        rng = random.Random(seed)
        return Graph(n, (e for e in combinations(range(n), 2) if rng.random() < probability))
    if family == "path":
        edges = ((i, i + 1) for i in range(n - 1))
    elif family == "cycle":
        if n < 3:
            raise ValueError("simple cycle requires at least three vertices")
        edges = ((i, (i + 1) % n) for i in range(n))
    elif family == "star":
        edges = ((0, i) for i in range(1, n))
    elif family == "clique":
        edges = combinations(range(n), 2)
    elif family == "disjoint_edges":
        edges = ((i, i + 1) for i in range(0, n - 1, 2))
    elif family == "complete_bipartite":
        edges = ((i, j) for i in range(n // 2) for j in range(n // 2, n))
    else:
        raise ValueError(f"unknown graph family: {family}")
    return Graph(n, edges)


def known_optimum(family, n):
    if family in {"path", "disjoint_edges", "complete_bipartite"}:
        return n // 2
    if family == "cycle":
        return (n + 1) // 2
    if family == "star":
        return int(n >= 2)
    if family == "clique":
        return max(0, n - 1)
    return None


def relabel(graph, permutation):
    if (len(permutation) != graph.num_vertices or any(type(v) is not int for v in permutation)
            or set(permutation) != set(range(graph.num_vertices))):
        raise ValueError("permutation must be a bijection of the graph vertices")
    return Graph(graph.num_vertices, ((permutation[u], permutation[v]) for u, v in graph.edges))


def validate_config(config):
    if not isinstance(config, dict):
        raise ValueError("configuration must be a JSON object")
    expected = {"name", "purpose", "predictions_file", "random_sizes", "probabilities", "seeds",
                "structured_sizes", "families", "relabel_sizes", "relabel_families",
                "permutation_seeds", "repetitions", "warmups", "exact_time_limit",
                "exact_node_limit", "batch_threshold_ns", "batch_size"}
    if set(config) != expected:
        raise ValueError(f"configuration keys differ: {sorted(set(config) ^ expected)}")
    for key in ["name", "purpose", "predictions_file"]:
        if not isinstance(config[key], str) or not config[key].strip():
            raise ValueError(f"{key} must be a nonempty string")
    for key in ["random_sizes", "seeds", "structured_sizes", "relabel_sizes", "permutation_seeds"]:
        values = config[key]
        if (not isinstance(values, list) or any(type(v) is not int or v < 0 for v in values)
                or len(values) != len(set(values))):
            raise ValueError(f"{key} must contain distinct non-negative integers")
    probabilities = config["probabilities"]
    if (not isinstance(probabilities, list)
            or any(type(v) not in (int, float) or not isfinite(v) or not 0 <= v <= 1
                   for v in probabilities) or len(probabilities) != len(set(probabilities))):
        raise ValueError("probabilities must be distinct finite values in [0, 1]")
    for key in ["families", "relabel_families"]:
        if (not isinstance(config[key], list) or any(not isinstance(v, str) or v not in FAMILIES for v in config[key])
                or len(config[key]) != len(set(config[key]))):
            raise ValueError(f"{key} must contain distinct structured family names")
    if not set(config["relabel_families"]) <= set(config["families"]):
        raise ValueError("relabel families must also occur in families")
    if not set(config["relabel_sizes"]) <= set(config["structured_sizes"]):
        raise ValueError("relabel sizes must also occur in structured_sizes")
    for key, minimum in [("repetitions", 1), ("warmups", 0), ("batch_threshold_ns", 0), ("batch_size", 1)]:
        if type(config[key]) is not int or config[key] < minimum:
            raise ValueError(f"{key} must be an integer >= {minimum}")
    if config["batch_size"] > 200:
        raise ValueError("batch_size must be <= 200 to bound retained result objects")
    seconds = config["exact_time_limit"]
    if type(seconds) not in (int, float) or not isfinite(seconds) or seconds < 0:
        raise ValueError("exact_time_limit must be a finite non-negative number")
    nodes = config["exact_node_limit"]
    if nodes is not None and (type(nodes) is not int or nodes < 0):
        raise ValueError("exact_node_limit must be null or a non-negative integer")
    if "cycle" in config["families"] and any(n < 3 for n in config["structured_sizes"]):
        raise ValueError("cycle sizes must be >= 3")
    return config


def generate_dataset(config_path, output):
    config_path = Path(config_path).resolve()
    config = validate_config(json.loads(config_path.read_text(encoding="utf-8-sig")))
    prediction_bytes = (config_path.parent / config["predictions_file"]).read_bytes()
    if not prediction_bytes.strip():
        raise ValueError("predictions file must not be empty")
    entries = []
    output = new_directory(output)
    (output / "graphs").mkdir()
    (output / "predictions.md").write_bytes(prediction_bytes)
    write_json(output / "config.json", config)

    def add(graph, identifier, family, *, probability=None, seed=None, base_id=None,
            permutation_seed=None, permutation=None):
        relative = f"graphs/{identifier}.json"
        write_json(output / relative, graph_payload(graph))
        n, m = graph.num_vertices, len(graph.edges)
        entries.append({"id": identifier, "file": relative, "sha256": graph_digest(graph),
                        "family": family, "n": n, "m": m,
                        "density": 2 * m / (n * (n - 1)) if n > 1 else 0.0,
                        "probability": probability, "seed": seed,
                        "base_id": base_id or identifier, "permutation_seed": permutation_seed,
                        "permutation": permutation, "analytic_optimum": known_optimum(family, n)})

    for n in config["random_sizes"]:
        for p in config["probabilities"]:
            for seed in config["seeds"]:
                add(make_graph("gnp", n, probability=p, seed=seed),
                    f"gnp_n{n}_p{p}_s{seed}", "gnp", probability=p, seed=seed)
    for family in config["families"]:
        for n in config["structured_sizes"]:
            graph = make_graph(family, n)
            identifier = f"{family}_n{n}"
            add(graph, identifier, family)
            if family in config["relabel_families"] and n in config["relabel_sizes"]:
                for seed in config["permutation_seeds"]:
                    permutation = list(range(n))
                    random.Random(seed).shuffle(permutation)
                    add(relabel(graph, permutation), f"{identifier}_perm{seed}", family,
                        base_id=identifier, permutation_seed=seed, permutation=permutation)
    if not entries:
        raise ValueError("configuration produces no graphs")
    manifest = {"schema_version": 1, "created_utc": utc_now(), "config": config,
                "config_sha256": digest(canonical_bytes(config)),
                "predictions_sha256": digest(prediction_bytes), "instances": entries}
    write_json(output / "manifest.json", manifest)
    return manifest


def load_dataset(path):
    path = Path(path).resolve()
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported dataset schema")
    validate_config(manifest["config"])
    if digest(canonical_bytes(manifest["config"])) != manifest["config_sha256"]:
        raise ValueError("dataset configuration hash mismatch")
    if digest((path / "predictions.md").read_bytes()) != manifest["predictions_sha256"]:
        raise ValueError("prediction snapshot hash mismatch")
    instances, identifiers = [], set()
    for entry in manifest["instances"]:
        if entry["id"] in identifiers:
            raise ValueError("duplicate instance id")
        identifiers.add(entry["id"])
        file = (path / entry["file"]).resolve()
        if not file.is_relative_to(path):
            raise ValueError("graph path escapes the dataset directory")
        payload = json.loads(file.read_text(encoding="utf-8"))
        graph = Graph(payload["num_vertices"], payload["edges"])
        if (graph_digest(graph) != entry["sha256"] or graph.num_vertices != entry["n"]
                or len(graph.edges) != entry["m"]):
            raise ValueError(f"graph integrity check failed: {entry['id']}")
        instances.append((entry, graph))
    if not instances:
        raise ValueError("dataset contains no graphs")
    return manifest, instances
