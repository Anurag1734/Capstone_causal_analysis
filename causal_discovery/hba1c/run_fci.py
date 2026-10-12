"""
run_fci.py

Runs the Fast Causal Inference (FCI) algorithm on the HbA1c causal discovery dataset.
Specifically evaluates structures compatible with latent/unmeasured confounding (PAG).
Records configuration, CI test, alpha, edge marks (circle, tail, arrow), and outputs:
- Learned PAG graph text
- Edge list CSV with edge marks and latent confounding flags
"""

import json
from pathlib import Path
import importlib.metadata
import numpy as np
import pandas as pd
import yaml
from causallearn.search.ConstraintBased.FCI import fci

CL_VERSION = importlib.metadata.version("causal-learn")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"
CONFIG_PATH = BASE_DIR / "config.yaml"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)


def run_fci_discovery(dataset_path=None, alpha=None, indep_test=None, max_cond_size=None):
    if dataset_path is None:
        dataset_path = DATA_DIR / f"hba1c_discovery_{config['dataset']['primary_window']}d.csv"
        
    alpha = alpha or config["fci"]["alpha"]
    indep_test = indep_test or config["fci"]["ci_test"]
    max_cond_size = max_cond_size if max_cond_size is not None else config["fci"]["max_cond_size"]
    seed = config["fci"]["random_seed"]
    
    np.random.seed(seed)
    df = pd.read_csv(dataset_path)
    
    cols = ["anchor_age", "sex_male", "hypertension", "ckd", "prior_mi", "hba1c_state", "subsequent_mi"]
    X = df[cols].values
    
    G, edges_fci = fci(
        X,
        alpha=alpha,
        indep_test=indep_test,
        node_names=cols,
        depth=max_cond_size,
        show_progress=False
    )
    
    edges = []
    for e in edges_fci:
        u = e.get_node1().get_name()
        v = e.get_node2().get_name()
        ep1 = e.get_endpoint1().name
        ep2 = e.get_endpoint2().name
        
        # In FCI PAG:
        # ARROW, ARROW (<->) means latent confounding / unmeasured confounder
        # CIRCLE, ARROW (o->) means partially oriented
        # CIRCLE, CIRCLE (o-o) means unoriented PAG edge
        # TAIL, ARROW (-->) means directed ancestral relation
        is_latent_confounding = (ep1 == "ARROW" and ep2 == "ARROW")
        
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
            direction = "bidirected_latent_confounded"
        elif ep1 == "CIRCLE" and ep2 == "ARROW":
            orientation = f"{u} o-> {v}"
            direction = "partially_oriented_circle_arrow"
        elif ep1 == "ARROW" and ep2 == "CIRCLE":
            orientation = f"{v} o-> {u}"
            direction = "partially_oriented_circle_arrow"
        elif ep1 == "CIRCLE" and ep2 == "CIRCLE":
            orientation = f"{u} o-o {v}"
            direction = "non_oriented_pag"
        else:
            orientation = f"{u} {ep1}-{ep2} {v}"
            direction = "pag_mark"
            
        edges.append({
            "source": u,
            "target": v,
            "endpoint_source": ep1,
            "endpoint_target": ep2,
            "orientation": orientation,
            "direction": direction,
            "latent_confounding": is_latent_confounding,
            "algorithm": "FCI"
        })
        
    edges_df = pd.DataFrame(edges)
    edges_csv = RESULTS_DIR / "fci_edges.csv"
    edges_df.to_csv(edges_csv, index=False)
    
    # Save text graph
    graph_txt = RESULTS_DIR / "fci_graph.txt"
    with open(graph_txt, "w", encoding="utf-8") as f:
        f.write(f"=== FCI ALGORITHM DISCOVERY PAG ===\n")
        f.write(f"Dataset: {dataset_path.name} (N = {len(df)})\n")
        f.write(f"CI Test: {indep_test}, Alpha: {alpha}, Max Cond Size: {max_cond_size}\n")
        f.write(f"causal-learn version: {CL_VERSION}\n\n")
        f.write("Adjacency Matrix:\n")
        f.write(str(G.graph))
        f.write("\n\nDiscovered PAG Edges:\n")
        for e in edges:
            latent_flag = " [LATENT CONFOUNDING INDICATED]" if e["latent_confounding"] else ""
            f.write(f"  {e['orientation']} (endpoints: {e['endpoint_source']}, {e['endpoint_target']}){latent_flag}\n")
            
    print(f"FCI execution complete. Discovered {len(edges)} PAG edges. Results saved to {edges_csv}")
    return G, edges_df


if __name__ == "__main__":
    run_fci_discovery()
