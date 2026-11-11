from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.patches import Patch
from matplotlib.lines import Line2D


MODEL_PATH = Path(__file__).with_name("statin_dag.json")
ROLE_COLORS = {
    "confounder": "#d9eaf7",
    "proxy": "#e6e6e6",
    "selection": "#ffe0a6",
    "treatment": "#9bd5a5",
    "mediator": "#d9c2f0",
    "outcome": "#f4a6a6",
    "competing_event": "#f7c58b",
}


def load_model(path: Path = MODEL_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        model = json.load(file)
    validate_model(model)
    return model


def build_graph(model: dict[str, Any] | None = None) -> nx.DiGraph:
    model = model or load_model()
    graph = nx.DiGraph()
    for node in model["nodes"]:
        if node.get("active", True):
            graph.add_node(node["id"], **node)
    for edge in model["edges"]:
        graph.add_edge(edge["from"], edge["to"], **edge)
    return graph


def validate_model(model: dict[str, Any]) -> None:
    node_ids = [node["id"] for node in model["nodes"]]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("Node IDs must be unique.")

    node_id_set = set(node_ids)
    active_node_ids = {
        node["id"] for node in model["nodes"] if node.get("active", True)
    }
    allowed_roles = {
        "confounder",
        "proxy",
        "selection",
        "treatment",
        "mediator",
        "outcome",
        "competing_event",
    }
    for node in model["nodes"]:
        if node["role"] not in allowed_roles:
            raise ValueError(f"Unsupported role for node {node['id']}: {node['role']}")
    active_edges = [(edge["from"], edge["to"]) for edge in model["edges"]]
    if len(active_edges) != len(set(active_edges)):
        raise ValueError("Active directed edges must be unique.")
    for edge in model["edges"]:
        if edge["from"] not in active_node_ids or edge["to"] not in active_node_ids:
            raise ValueError(f"Active edge must connect active nodes: {edge}")
        if edge["status"] not in {"proposed", "assumption"}:
            raise ValueError(f"Unsupported active edge status: {edge['status']}")
    for edge in model["unresolved_edges"]:
        if edge["from"] not in node_id_set or edge["to"] not in node_id_set:
            raise ValueError(f"Unresolved edge endpoints must have node definitions: {edge}")
        if edge["status"] != "unresolved":
            raise ValueError(f"Unsupported unresolved edge status: {edge['status']}")
    for node_id in model["selection_conditioning_nodes"]:
        if node_id not in node_id_set:
            raise ValueError(f"Unknown selection conditioning node: {node_id}")
    for node_id in model["candidate_adjustment_nodes"]:
        if node_id not in active_node_ids:
            raise ValueError(f"Adjustment candidate must be an active node: {node_id}")
        if not next(
            node["adjustment_candidate"]
            for node in model["nodes"]
            if node["id"] == node_id
        ):
            raise ValueError(f"Node is not eligible for adjustment: {node_id}")
    if not nx.is_directed_acyclic_graph(build_graph_unchecked(model)):
        raise ValueError("Active model edges must form a directed acyclic graph.")


def build_graph_unchecked(model: dict[str, Any]) -> nx.DiGraph:
    graph = nx.DiGraph()
    graph.add_nodes_from(node["id"] for node in model["nodes"])
    graph.add_edges_from((edge["from"], edge["to"]) for edge in model["edges"])
    return graph


def parents(graph: nx.DiGraph, node: str) -> set[str]:
    return set(graph.predecessors(node))


def descendants(graph: nx.DiGraph, node: str) -> set[str]:
    return nx.descendants(graph, node)


def backdoor_blocked(
    graph: nx.DiGraph,
    treatment: str,
    outcome: str,
    adjustment: set[str],
    conditioned: set[str] | None = None,
) -> bool:
    if treatment not in graph or outcome not in graph:
        raise ValueError("Treatment and outcome must be nodes in the graph.")
    if adjustment & ({treatment, outcome} | descendants(graph, treatment)):
        raise ValueError("A backdoor adjustment set cannot contain treatment, outcome, or treatment descendants.")
    ineligible = {
        node_id
        for node_id in adjustment
        if not graph.nodes[node_id].get("adjustment_candidate", False)
    }
    if ineligible:
        raise ValueError(
            f"Nodes are not approved baseline adjustment candidates: {sorted(ineligible)}"
        )

    backdoor_graph = graph.copy()
    backdoor_graph.remove_edges_from(list(backdoor_graph.out_edges(treatment)))
    conditioning_set = set(adjustment) | set(conditioned or ())
    return nx.is_d_separator(backdoor_graph, {treatment}, {outcome}, conditioning_set)


def minimal_candidate_adjustment_sets(
    model: dict[str, Any] | None = None,
) -> list[tuple[str, ...]]:
    model = model or load_model()
    graph = build_graph(model)
    treatment = model["treatment_node"]
    outcome = model["outcome_node"]
    conditioned = set(model["selection_conditioning_nodes"])
    candidates = list(model["candidate_adjustment_nodes"])

    if not backdoor_blocked(
        graph,
        treatment,
        outcome,
        set(candidates),
        conditioned,
    ):
        return []

    minimal_sets: list[tuple[str, ...]] = []
    for size in range(len(candidates) + 1):
        for subset in itertools.combinations(candidates, size):
            subset_set = set(subset)
            if any(set(existing).issubset(subset_set) for existing in minimal_sets):
                continue
            if backdoor_blocked(graph, treatment, outcome, subset_set, conditioned):
                minimal_sets.append(subset)
    return minimal_sets


def open_backdoor_paths(
    graph: nx.DiGraph,
    treatment: str,
    outcome: str,
    adjustment: set[str],
    conditioned: set[str],
    max_paths: int = 100,
    max_states: int = 100000,
) -> dict[str, Any]:
    if max_paths < 1:
        raise ValueError("max_paths must be positive.")
    if max_states < 1:
        raise ValueError("max_states must be positive.")
    backdoor_graph = graph.copy()
    backdoor_graph.remove_edges_from(list(backdoor_graph.out_edges(treatment)))
    conditioning_set = set(adjustment) | set(conditioned)
    if nx.is_d_separator(
        backdoor_graph,
        {treatment},
        {outcome},
        conditioning_set,
    ):
        return {"paths": [], "truncated": False, "enumerated_paths": 0}

    undirected = backdoor_graph.to_undirected()
    active_paths: list[dict[str, Any]] = []
    explored_states = 0
    truncated = False
    conditioned_ancestors = set(conditioning_set)
    for node_id in conditioning_set:
        conditioned_ancestors.update(nx.ancestors(backdoor_graph, node_id))

    def search(path: list[str]) -> None:
        nonlocal explored_states, truncated
        if truncated:
            return
        if len(active_paths) >= max_paths or explored_states >= max_states:
            truncated = True
            return
        explored_states += 1
        current = path[-1]
        if current == outcome:
            formatted_path = [path[0]]
            for source, target in zip(path, path[1:]):
                direction = "->" if backdoor_graph.has_edge(source, target) else "<-"
                formatted_path.extend((direction, target))
            active_paths.append(
                {
                    "nodes": path.copy(),
                    "path": " ".join(formatted_path),
                    "roles": {
                        node_id: graph.nodes[node_id].get("role", "unknown")
                        for node_id in path
                    },
                }
            )
            return

        for next_node in undirected.neighbors(current):
            if next_node in path:
                continue
            if len(path) > 1:
                previous_node = path[-2]
                is_collider = (
                    backdoor_graph.has_edge(previous_node, current)
                    and backdoor_graph.has_edge(next_node, current)
                )
                if is_collider and current not in conditioned_ancestors:
                    continue
                if not is_collider and current in conditioning_set:
                    continue
            path.append(next_node)
            search(path)
            path.pop()
            if truncated:
                return

    search([treatment])
    return {
        "paths": active_paths,
        "truncated": truncated,
        "explored_states": explored_states,
    }


def assess_backdoor_paths(model: dict[str, Any] | None = None) -> dict[str, Any]:
    model = model or load_model()
    graph = build_graph(model)
    observed_set = set(model["candidate_adjustment_nodes"])
    measured_set = set(model["measured_candidate_adjustment_nodes"])
    conditioned = set(model["selection_conditioning_nodes"])
    blocked = backdoor_blocked(
        graph,
        model["treatment_node"],
        model["outcome_node"],
        observed_set,
        conditioned,
    )
    open_paths = open_backdoor_paths(
        graph,
        model["treatment_node"],
        model["outcome_node"],
        observed_set,
        conditioned,
    )
    measured_paths = open_backdoor_paths(
        graph,
        model["treatment_node"],
        model["outcome_node"],
        measured_set,
        conditioned,
    )
    return {
        "conditioning_on_target_population": sorted(conditioned),
        "measured_candidate_adjustment_set_tested": sorted(measured_set),
        "expanded_candidate_adjustment_set_tested": sorted(observed_set),
        "measured_candidate_set_blocks_backdoor_paths": backdoor_blocked(
            graph,
            model["treatment_node"],
            model["outcome_node"],
            measured_set,
            conditioned,
        ),
        "expanded_candidate_set_blocks_backdoor_paths": blocked,
        "candidate_set_blocks_backdoor_paths": blocked,
        "open_backdoor_path_count_measured_set": len(measured_paths["paths"]),
        "open_backdoor_paths_measured_set": measured_paths["paths"],
        "open_backdoor_paths_measured_set_truncated": measured_paths["truncated"],
        "open_backdoor_path_count_expanded_set": len(open_paths["paths"]),
        "open_backdoor_paths_expanded_set": open_paths["paths"],
        "open_backdoor_paths_expanded_set_truncated": open_paths["truncated"],
        "minimal_sets_among_candidate_variables": [
            list(items) for items in minimal_candidate_adjustment_sets(model)
        ],
        "interpretation": (
            "Graph separation is a structural check only, not evidence that the edges, measurements, "
            "exchangeability, or causal effect are valid."
        ),
    }


def render_dag(
    output_path: Path,
    model: dict[str, Any] | None = None,
) -> Path:
    model = model or load_model()
    graph = build_graph(model)
    node_data = {node["id"]: node for node in model["nodes"]}
    layers: dict[int, list[str]] = {}
    for node_id, attributes in graph.nodes(data=True):
        layer = int(attributes.get("layer", 0))
        layers.setdefault(layer, []).append(node_id)

    layer_order = {
        layer: sorted(node_ids, key=lambda node_id: node_data[node_id]["label"])
        for layer, node_ids in layers.items()
    }
    for _ in range(6):
        vertical_order = {
            node_id: (len(node_ids) - 1) / 2 - index
            for node_ids in layer_order.values()
            for index, node_id in enumerate(node_ids)
        }
        for layer in sorted(layer_order):
            previous_positions = {
                node_id: vertical_order[node_id]
                for prior_layer in layer_order
                if prior_layer < layer
                for node_id in layer_order[prior_layer]
            }
            if previous_positions:
                layer_order[layer].sort(
                    key=lambda node_id: (
                        sum(
                            previous_positions[parent]
                            for parent in graph.predecessors(node_id)
                            if parent in previous_positions
                        )
                        / max(
                            1,
                            sum(
                                parent in previous_positions
                                for parent in graph.predecessors(node_id)
                            ),
                        ),
                        node_data[node_id]["label"],
                    )
                )
            vertical_order = {
                node_id: (len(node_ids) - 1) / 2 - index
                for node_ids in layer_order.values()
                for index, node_id in enumerate(node_ids)
            }
        for layer in sorted(layer_order, reverse=True):
            later_positions = {
                node_id: vertical_order[node_id]
                for later_layer in layer_order
                if later_layer > layer
                for node_id in layer_order[later_layer]
            }
            if later_positions:
                layer_order[layer].sort(
                    key=lambda node_id: (
                        sum(
                            later_positions[child]
                            for child in graph.successors(node_id)
                            if child in later_positions
                        )
                        / max(
                            1,
                            sum(
                                child in later_positions
                                for child in graph.successors(node_id)
                            ),
                        ),
                        node_data[node_id]["label"],
                    )
                )

    positions: dict[str, tuple[float, float]] = {}
    for layer, ordered in layer_order.items():
        for index, node_id in enumerate(ordered):
            positions[node_id] = (
                float(layer) * 1.2,
                ((len(ordered) - 1) / 2 - index) * 1.4,
            )

    max_nodes_in_layer = max(map(len, layers.values()))
    figure, axis = plt.subplots(
        figsize=(max(22, len(layers) * 3.4), max(12, max_nodes_in_layer * 1.65))
    )
    colors = [
        ROLE_COLORS[node_data[node_id]["role"]]
        for node_id in graph.nodes
    ]
    labels = {node_id: node_data[node_id]["label"] for node_id in graph.nodes}
    nx.draw_networkx_nodes(
        graph,
        positions,
        node_color=colors,
        node_size=2700,
        edgecolors="#34495e",
        linewidths=0.8,
        ax=axis,
    )
    nx.draw_networkx_labels(graph, positions, labels=labels, font_size=8, ax=axis)

    proposed = [
        (source, target)
        for source, target, edge in graph.edges(data=True)
        if edge["status"] == "proposed"
    ]
    assumptions = [
        (source, target)
        for source, target, edge in graph.edges(data=True)
        if edge["status"] == "assumption"
    ]
    nx.draw_networkx_edges(
        graph,
        positions,
        edgelist=proposed,
        edge_color="#526779",
        width=0.8,
        alpha=0.45,
        arrows=True,
        arrowsize=11,
        connectionstyle="arc3,rad=0.04",
        ax=axis,
    )
    nx.draw_networkx_edges(
        graph,
        positions,
        edgelist=assumptions,
        edge_color="#c27c0e",
        style="dashed",
        width=0.9,
        alpha=0.7,
        arrows=True,
        arrowsize=11,
        connectionstyle="arc3,rad=0.06",
        ax=axis,
    )
    axis.set_title(
        "Provisional statin DAG | solid: proposed; dashed: assumption requiring validation",
        fontsize=12,
    )
    role_handles = [
        Patch(
            facecolor=color,
            edgecolor="#34495e",
            label=role.replace("_", " ").title(),
        )
        for role, color in ROLE_COLORS.items()
    ]
    role_handles.extend(
        [
            Line2D([0], [0], color="#526779", label="Proposed edge"),
            Line2D([0], [0], color="#c27c0e", linestyle="--", label="Assumption"),
        ]
    )
    axis.legend(
        handles=role_handles,
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        frameon=False,
        fontsize=8,
    )
    axis.axis("off")
    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, format=output_path.suffix.lstrip(".") or "svg", bbox_inches="tight")
    plt.close(figure)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and visualize the provisional statin DAG.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("statin_dag.svg"),
        help="Path for the rendered DAG (default: causal_models/statin_dag.svg).",
    )
    args = parser.parse_args()

    model = load_model()
    graph = build_graph(model)
    assessment = assess_backdoor_paths(model)
    result = {
        "is_dag": nx.is_directed_acyclic_graph(graph),
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "conditioning_on_target_population": assessment[
            "conditioning_on_target_population"
        ],
        "measured_candidate_set_blocks_backdoor_paths": assessment[
            "measured_candidate_set_blocks_backdoor_paths"
        ],
        "measured_open_path_count_returned": assessment[
            "open_backdoor_path_count_measured_set"
        ],
        "measured_path_listing_truncated": assessment[
            "open_backdoor_paths_measured_set_truncated"
        ],
        "expanded_candidate_set_blocks_backdoor_paths": assessment[
            "expanded_candidate_set_blocks_backdoor_paths"
        ],
        "expanded_open_paths": assessment["open_backdoor_paths_expanded_set"],
        "parents_of_treatment": sorted(parents(graph, model["treatment_node"])),
        "descendants_of_treatment": sorted(descendants(graph, model["treatment_node"])),
        "visualization": str(render_dag(args.output, model)),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
