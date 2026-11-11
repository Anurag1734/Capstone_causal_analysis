from __future__ import annotations

import unittest

import networkx as nx

from causal_models.statin_dag import (
    assess_backdoor_paths,
    backdoor_blocked,
    build_graph,
    descendants,
    load_model,
    minimal_candidate_adjustment_sets,
    open_backdoor_paths,
    parents,
    validate_model,
)


class StatinDagTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.model = load_model()
        cls.graph = build_graph(cls.model)

    def test_active_graph_is_acyclic_and_valid(self) -> None:
        validate_model(self.model)
        self.assertTrue(nx.is_directed_acyclic_graph(self.graph))

    def test_treatment_parent_and_descendant_inspection(self) -> None:
        self.assertIn("prior_mi_episode_count", parents(self.graph, "statin_initiation"))
        self.assertNotIn("prior_mi_history", parents(self.graph, "statin_initiation"))
        self.assertIn("true_recurrent_mi", descendants(self.graph, "statin_initiation"))
        self.assertIn("recorded_statin_order", descendants(self.graph, "statin_initiation"))

    def test_observed_candidate_set_does_not_close_all_backdoors(self) -> None:
        assessment = assess_backdoor_paths(self.model)
        self.assertFalse(assessment["candidate_set_blocks_backdoor_paths"])
        self.assertEqual(assessment["minimal_sets_among_candidate_variables"], [])
        self.assertIn(
            "unmeasured_atherosclerotic_risk",
            {
                node
                for path in assessment["open_backdoor_paths_expanded_set"]
                for node in path["nodes"]
            },
        )
        self.assertTrue(assessment["open_backdoor_paths_measured_set"])
        self.assertTrue(assessment["open_backdoor_paths_expanded_set"])
        for path in assessment["open_backdoor_paths_expanded_set"]:
            self.assertEqual(path["nodes"][0], "statin_initiation")
            self.assertEqual(path["nodes"][-1], "true_recurrent_mi")
            self.assertIn("unmeasured_atherosclerotic_risk", path["nodes"])
        self.assertTrue(
            any(
                "selected_prior_mi_cohort" in path["nodes"]
                for path in assessment["open_backdoor_paths_measured_set"]
            )
        )
        self.assertEqual(minimal_candidate_adjustment_sets(self.model), [])

    def test_treatment_descendants_cannot_be_adjusted_for(self) -> None:
        with self.assertRaises(ValueError):
            backdoor_blocked(
                self.graph,
                "statin_initiation",
                "true_recurrent_mi",
                {"post_assignment_adherence"},
            )

    def test_statins_before_proxy_is_not_adjustment_eligible(self) -> None:
        self.assertNotIn("statin_before_proxy", self.model["candidate_adjustment_nodes"])
        self.assertFalse(self.graph.nodes["statin_before_proxy"]["adjustment_candidate"])
        self.assertEqual(
            parents(self.graph, "statin_before_proxy"),
            {"prior_statin_use", "healthcare_access"},
        )
        with self.assertRaises(ValueError):
            backdoor_blocked(
                self.graph,
                "statin_initiation",
                "true_recurrent_mi",
                {"statin_before_proxy"},
            )

    def test_selected_population_separates_eligibility_and_prior_history(self) -> None:
        labels = {node["id"]: node["label"] for node in self.model["nodes"]}
        self.assertIn("eligibility", labels["prior_mi_history"].lower())
        self.assertIn("episode", labels["prior_mi_episode_count"].lower())
        self.assertIn("most recent", labels["time_since_most_recent_mi"].lower())
        self.assertIn("interventions", labels["prior_cv_interventions"].lower())
        self.assertEqual(
            self.model["selection_conditioning_nodes"],
            ["selected_prior_mi_cohort"],
        )
        self.assertNotIn("prior_mi_history", parents(self.graph, "statin_initiation"))

    def test_unresolved_edges_are_not_added_to_active_graph(self) -> None:
        self.assertNotIn("pre_exposure_ecg_state", self.graph)
        self.assertNotIn("z_ecg", self.graph)
        self.assertIn("pre_exposure_ecg_state", {node["id"] for node in self.model["nodes"]})
        self.assertIn("z_ecg", {node["id"] for node in self.model["nodes"]})
        self.assertEqual(len(self.model["unresolved_edges"]), 7)

    def test_open_path_enumeration_respects_conditioned_colliders(self) -> None:
        graph = nx.DiGraph()
        graph.add_edges_from(
            [
                ("prior_use", "treatment"),
                ("prior_use", "measurement_proxy"),
                ("access", "measurement_proxy"),
                ("access", "outcome"),
            ]
        )
        without_conditioning = open_backdoor_paths(
            graph,
            "treatment",
            "outcome",
            adjustment=set(),
            conditioned=set(),
        )
        conditioning_on_proxy = open_backdoor_paths(
            graph,
            "treatment",
            "outcome",
            adjustment=set(),
            conditioned={"measurement_proxy"},
        )
        self.assertEqual(without_conditioning["paths"], [])
        self.assertEqual(len(conditioning_on_proxy["paths"]), 1)


if __name__ == "__main__":
    unittest.main()
