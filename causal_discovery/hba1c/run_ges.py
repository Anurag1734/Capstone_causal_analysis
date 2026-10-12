"""
run_ges.py

Runs Greedy Equivalence Search (GES) on the HbA1c causal discovery dataset.
Records configuration, score function (BIC), penalty parameters, and outputs:
- Learned CPDAG graph text
- Edge list CSV with orientations
"""

import json
from pathlib import Path
import importlib.metadata
import numpy as np
import pandas as pd
import yaml
from causallearn.search.ScoreBased.GES import ges

CL_VERSION = importlib.metadata.version("causal-learn")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"
CONFIG_PATH = BASE_DIR / "config.yaml"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)


def run_ges_discovery(dataset_path=None, score_func=None, maxP=None):
    if dataset_path is None:
        dataset_path = DATA_DIR / f"hba1c_discovery_{config['dataset']['primary_window']}d.csv"
        
    score_func = score_func or config["ges"]["score_func"]
    seed = config["ges"]["random_seed"]
    
    np.random.seed(seed)
    df = pd.read_csv(dataset_path)
    
    cols = ["anchor_age", "sex_male", "hypertension", "ckd", "prior_mi", "hba1c_state", "subsequent_mi"]
    X = df[cols].values
    
    res = ges(
        X,
        score_func=score_func,
        maxP=maxP,
        node_names=cols
    )
    
    G = res["G"]
    edges = []
    
    for e in G.get_graph_edges():
        u = e.get_node1().get_name()
        v = e.get_node2().get_name()
        ep1 = e.get_endpoint1().name
        ep2 = e.get_endpoint2().name
        
        if ep1 == "TAIL" and ep2 == "ARROW":
            orientation = f"{u} -> {v}"
            direction = "directed"
        elif ep1 == "ARROW" and ep2 == "TAIL":
            orientation = f"{v} -> {u}"
            direction = "directed"
        elif ep1 == "TAIL" and ep2 == "TAIL":
            orientation = f"{u} - {v}"
            direction = "undirected"
        elif ep1 == "ARROW" and ep2 == "ARROW":
            orientation = f"{u} <-> {v}"
            direction = "bidirected"
        else:
            orientation = f"{u} {ep1}-{ep2} {v}"
            direction = "partially_oriented"
            
        edges.append({
            "source": u,
            "target": v,
            "endpoint_source": ep1,
            "endpoint_target": ep2,
            "orientation": orientation,
            "direction": direction,
            "algorithm": "GES"
        })
        
    edges_df = pd.DataFrame(edges)
    edges_csv = RESULTS_DIR / "ges_edges.csv"
    edges_df.to_csv(edges_csv, index=False)
    
    # Save text graph
    graph_txt = RESULTS_DIR / "ges_graph.txt"
    with open(graph_txt, "w", encoding="utf-8") as f:
        f.write(f"=== GES ALGORITHM DISCOVERY GRAPH ===\n")
        f.write(f"Dataset: {dataset_path.name} (N = {len(df)})\n")
        f.write(f"Score Function: {score_func}\n")
        f.write(f"BIC Score: {res.get('score', 'N/A')}\n")
        f.write(f"causal-learn version: {CL_VERSION}\n\n")
        f.write("Adjacency Matrix:\n")
        f.write(str(G.graph))
        f.write("\n\nDiscovered Edges:\n")
        for e in edges:
            f.write(f"  {e['orientation']} (endpoints: {e['endpoint_source']}, {e['endpoint_target']})\n")
            
    print(f"GES execution complete. Discovered {len(edges)} edges. Results saved to {edges_csv}")
    return res, edges_df


if __name__ == "__main__":
    run_ges_discovery()
