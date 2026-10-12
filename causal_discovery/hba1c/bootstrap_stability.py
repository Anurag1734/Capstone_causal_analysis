"""
bootstrap_stability.py

Performs bootstrap resampling stability analysis (500 replicates) for PC, GES, and FCI.
Calculates:
- Adjacency selection frequency under resampling for all pairs
- Primary orientation selection frequency under resampling
- Method-specific stability summary
Outputs:
- results/bootstrap_edge_frequency.csv
- results/bootstrap_summary.json
"""

import json
from pathlib import Path
import itertools
import numpy as np
import pandas as pd
import yaml
from causallearn.search.ConstraintBased.PC import pc
from causallearn.search.ScoreBased.GES import ges
from causallearn.search.ConstraintBased.FCI import fci

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"
CONFIG_PATH = BASE_DIR / "config.yaml"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)


def run_bootstrap_analysis(n_replicates=500, random_seed=42):
    dataset_path = DATA_DIR / f"hba1c_discovery_{config['dataset']['primary_window']}d.csv"
    df = pd.read_csv(dataset_path)
    
    cols = ["anchor_age", "sex_male", "hypertension", "ckd", "prior_mi", "hba1c_state", "subsequent_mi"]
    p = len(cols)
    pairs = [tuple(sorted(pair)) for pair in itertools.combinations(cols, 2)]
    
    np.random.seed(random_seed)
    n_samples = len(df)
    
    # Trackers for adjacencies: pair -> count
    pc_adj_counts = {pair: 0 for pair in pairs}
    ges_adj_counts = {pair: 0 for pair in pairs}
    fci_adj_counts = {pair: 0 for pair in pairs}
    
    # Trackers for orientations: pair -> dict of orientation strings -> count
    pc_orient_counts = {pair: {} for pair in pairs}
    ges_orient_counts = {pair: {} for pair in pairs}
    fci_orient_counts = {pair: {} for pair in pairs}
    
    alpha = config["pc"]["alpha"]
    indep_test = config["pc"]["ci_test"]
    score_func = config["ges"]["score_func"]
    max_cond = config["pc"]["max_cond_size"]
    
    print(f"Starting bootstrap stability analysis: {n_replicates} replicates on N = {n_samples}...")
    
    for b in range(n_replicates):
        if (b + 1) % 50 == 0 or b == 0:
            print(f"  Bootstrap replicate {b + 1}/{n_replicates}...")
            
        # Resample with replacement
        sample_idx = np.random.choice(n_samples, size=n_samples, replace=True)
        sample_X = df[cols].iloc[sample_idx].values
        
        # 1. PC Run
        cg_pc = pc(sample_X, alpha=alpha, indep_test=indep_test, node_names=cols, depth=max_cond, show_progress=False)
        pc_edges = cg_pc.G.get_graph_edges()
        for e in pc_edges:
            u, v = e.get_node1().get_name(), e.get_node2().get_name()
            ep1, ep2 = e.get_endpoint1().name, e.get_endpoint2().name
            pair = tuple(sorted([u, v]))
            pc_adj_counts[pair] += 1
            
            # Format canonical orientation relative to sorted pair
            if pair[0] == u:
                orient_str = f"{u} -> {v}" if (ep1=="TAIL" and ep2=="ARROW") else (f"{v} -> {u}" if (ep1=="ARROW" and ep2=="TAIL") else f"{u} - {v}")
            else:
                orient_str = f"{v} -> {u}" if (ep1=="TAIL" and ep2=="ARROW") else (f"{u} -> {v}" if (ep1=="ARROW" and ep2=="TAIL") else f"{u} - {v}")
            pc_orient_counts[pair][orient_str] = pc_orient_counts[pair].get(orient_str, 0) + 1

        # 2. GES Run
        res_ges = ges(sample_X, score_func=score_func, node_names=cols)
        ges_edges = res_ges["G"].get_graph_edges()
        for e in ges_edges:
            u, v = e.get_node1().get_name(), e.get_node2().get_name()
            ep1, ep2 = e.get_endpoint1().name, e.get_endpoint2().name
            pair = tuple(sorted([u, v]))
            ges_adj_counts[pair] += 1
            
            if pair[0] == u:
                orient_str = f"{u} -> {v}" if (ep1=="TAIL" and ep2=="ARROW") else (f"{v} -> {u}" if (ep1=="ARROW" and ep2=="TAIL") else f"{u} - {v}")
            else:
                orient_str = f"{v} -> {u}" if (ep1=="TAIL" and ep2=="ARROW") else (f"{u} -> {v}" if (ep1=="ARROW" and ep2=="TAIL") else f"{u} - {v}")
            ges_orient_counts[pair][orient_str] = ges_orient_counts[pair].get(orient_str, 0) + 1

        # 3. FCI Run
        G_fci, fci_edges = fci(sample_X, alpha=alpha, indep_test=indep_test, node_names=cols, depth=max_cond, show_progress=False)
        for e in fci_edges:
            u, v = e.get_node1().get_name(), e.get_node2().get_name()
            ep1, ep2 = e.get_endpoint1().name, e.get_endpoint2().name
            pair = tuple(sorted([u, v]))
            fci_adj_counts[pair] += 1
            
            if ep1 == "ARROW" and ep2 == "ARROW":
                orient_str = f"{pair[0]} <-> {pair[1]}"
            elif (pair[0] == u and ep1 == "TAIL" and ep2 == "ARROW") or (pair[1] == u and ep1 == "ARROW" and ep2 == "TAIL"):
                orient_str = f"{pair[0]} -> {pair[1]}"
            elif (pair[1] == u and ep1 == "TAIL" and ep2 == "ARROW") or (pair[0] == u and ep1 == "ARROW" and ep2 == "TAIL"):
                orient_str = f"{pair[1]} -> {pair[0]}"
            elif ep1 == "CIRCLE" and ep2 == "ARROW":
                orient_str = f"{u} o-> {v}"
            elif ep1 == "ARROW" and ep2 == "CIRCLE":
                orient_str = f"{v} o-> {u}"
            else:
                orient_str = f"{pair[0]} o-o {pair[1]}"
            fci_orient_counts[pair][orient_str] = fci_orient_counts[pair].get(orient_str, 0) + 1

    # Compile results table
    rows = []
    for pair in pairs:
        u, v = pair
        pc_freq = pc_adj_counts[pair] / n_replicates * 100
        ges_freq = ges_adj_counts[pair] / n_replicates * 100
        fci_freq = fci_adj_counts[pair] / n_replicates * 100
        
        # Most frequent orientation
        pc_best_orient = max(pc_orient_counts[pair].items(), key=lambda x: x[1])[0] if pc_orient_counts[pair] else "None"
        pc_orient_freq = (max(pc_orient_counts[pair].values()) / n_replicates * 100) if pc_orient_counts[pair] else 0.0
        
        ges_best_orient = max(ges_orient_counts[pair].items(), key=lambda x: x[1])[0] if ges_orient_counts[pair] else "None"
        ges_orient_freq = (max(ges_orient_counts[pair].values()) / n_replicates * 100) if ges_orient_counts[pair] else 0.0
        
        fci_best_orient = max(fci_orient_counts[pair].items(), key=lambda x: x[1])[0] if fci_orient_counts[pair] else "None"
        fci_orient_freq = (max(fci_orient_counts[pair].values()) / n_replicates * 100) if fci_orient_counts[pair] else 0.0
        
        rows.append({
            "var1": u,
            "var2": v,
            "PC_adjacency_freq_pct": round(pc_freq, 2),
            "PC_primary_orientation": pc_best_orient,
            "PC_orientation_freq_pct": round(pc_orient_freq, 2),
            "GES_adjacency_freq_pct": round(ges_freq, 2),
            "GES_primary_orientation": ges_best_orient,
            "GES_orientation_freq_pct": round(ges_orient_freq, 2),
            "FCI_adjacency_freq_pct": round(fci_freq, 2),
            "FCI_primary_orientation": fci_best_orient,
            "FCI_orientation_freq_pct": round(fci_orient_freq, 2),
            "mean_adjacency_freq_pct": round((pc_freq + ges_freq + fci_freq) / 3, 2)
        })
        
    res_df = pd.DataFrame(rows).sort_values("mean_adjacency_freq_pct", ascending=False)
    csv_path = RESULTS_DIR / "bootstrap_edge_frequency.csv"
    res_df.to_csv(csv_path, index=False)
    print(f"Bootstrap stability analysis finished. Results saved to {csv_path}")
    
    return res_df


if __name__ == "__main__":
    run_bootstrap_analysis(n_replicates=500, random_seed=42)
