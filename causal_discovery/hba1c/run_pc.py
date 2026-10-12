"""
run_pc.py

Runs the PC algorithm on the HbA1c causal discovery dataset.
Records configuration, CI test, significance threshold, separation sets, and outputs:
- Learned CPDAG graph text
- Edge list CSV with endpoint details
- Separation sets JSON
"""

import json
from pathlib import Path
import importlib.metadata
import numpy as np
import pandas as pd
import yaml
from causallearn.search.ConstraintBased.PC import pc

CL_VERSION = importlib.metadata.version("causal-learn")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"
CONFIG_PATH = BASE_DIR / "config.yaml"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)


def run_pc_discovery(dataset_path=None, alpha=None, indep_test=None, max_cond_size=None):
    if dataset_path is None:
        dataset_path = DATA_DIR / f"hba1c_discovery_{config['dataset']['primary_window']}d.csv"
    
    alpha = alpha or config["pc"]["alpha"]
    indep_test = indep_test or config["pc"]["ci_test"]
    max_cond_size = max_cond_size if max_cond_size is not None else config["pc"]["max_cond_size"]
    seed = config["pc"]["random_seed"]
    
    np.random.seed(seed)
    df = pd.read_csv(dataset_path)
    
    # Primary variable set: clinical confounders, binary exposure, binary outcome
    cols = ["anchor_age", "sex_male", "hypertension", "ckd", "prior_mi", "hba1c_state", "subsequent_mi"]
    X = df[cols].values
    
    cg = pc(
        X,
        alpha=alpha,
        indep_test=indep_test,
        node_names=cols,
        depth=max_cond_size,
        show_progress=False
    )
    
    # Extract edges
    edges = []
    G = cg.G
    nodes = [n.get_name() for n in G.get_nodes()]
    
    for e in G.get_graph_edges():
        u = e.get_node1().get_name()
        v = e.get_node2().get_name()
        ep1 = e.get_endpoint1().name
        ep2 = e.get_endpoint2().name
        
        # Determine orientation description
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
            "algorithm": "PC"
        })
        
    edges_df = pd.DataFrame(edges)
    edges_csv = RESULTS_DIR / "pc_edges.csv"
    edges_df.to_csv(edges_csv, index=False)
    
    # Save text graph
    graph_txt = RESULTS_DIR / "pc_graph.txt"
    with open(graph_txt, "w", encoding="utf-8") as f:
        f.write(f"=== PC ALGORITHM DISCOVERY GRAPH ===\n")
        f.write(f"Dataset: {dataset_path.name} (N = {len(df)})\n")
        f.write(f"CI Test: {indep_test}, Alpha: {alpha}, Max Cond Size: {max_cond_size}\n")
        f.write(f"causal-learn version: {CL_VERSION}\n\n")
        f.write("Adjacency Matrix:\n")
        f.write(str(G.graph))
        f.write("\n\nDiscovered Edges:\n")
        for e in edges:
            f.write(f"  {e['orientation']} (endpoints: {e['endpoint_source']}, {e['endpoint_target']})\n")
            
    # Extract separation sets if available
    sepsets_dict = {}
    if hasattr(cg, "sepset") and cg.sepset is not None:
        p = len(cols)
        for i in range(p):
            for j in range(i + 1, p):
                s = cg.sepset[i, j]
                if s is not None and len(s) > 0:
                    u_name = cols[i]
                    v_name = cols[j]
                    # Format conditioning sets
                    cond_list = []
                    for cond in s:
                        cond_list.append([cols[k] for k in cond] if isinstance(cond, (list, tuple, set)) else str(cond))
                    sepsets_dict[f"{u_name} _||_ {v_name}"] = cond_list
            
    with open(RESULTS_DIR / "pc_sepsets.json", "w", encoding="utf-8") as f:
        json.dump(sepsets_dict, f, indent=2)
        
    print(f"PC execution complete. Discovered {len(edges)} edges. Results saved to {edges_csv}")
    return cg, edges_df


if __name__ == "__main__":
    run_pc_discovery()
