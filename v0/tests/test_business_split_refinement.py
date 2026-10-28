"""Checks for complete, source-led company grouping."""

import unittest

import business_split_refinement as refinement


def decision(groups, pairs, citations=None):
    active = [item for group in groups for item in group]
    return {"ticker": "T", "IQ_COMPANY_ID": "IQ1", "current": active,
            "groups": groups, "line_status": {x: "current" for x in active},
            "pair_status": pairs, "group_evidence": citations,
            "businesses": [{"business_id": x, "business": x} for x in active],
            "exited": [], "evidence_gaps": []}


class RefinementTests(unittest.TestCase):
    def test_missing_comparisons_do_not_create_a_third_business(self):
        case = decision([["B1"], ["B2"], ["B3"]],
                        {"B1|B2": "distinct", "B1|B3": "unresolved", "B2|B3": "unresolved"})
        result = refinement.refine_decision(case)
        self.assertEqual(result["groups"], [["B1", "B3"], ["B2"]])
        self.assertEqual(result["decision"], "multiple_businesses")

    def test_related_products_stay_in_one_business(self):
        case = decision([["B1", "B2"]], {"B1|B2": "related"})
        result = refinement.refine_decision(case)
        self.assertEqual(result["groups"], [["B1", "B2"]])

    def test_source_cited_business_hierarchy_resolves_missing_pairs(self):
        case = decision([["B1"], ["B2"], ["B3"]],
                        {"B1|B2": "unresolved", "B1|B3": "distinct", "B2|B3": "unresolved"},
                        [["P1.1"], ["P1.2"], ["P1.3"]])
        result = refinement.refine_decision(case)
        self.assertEqual(result["groups"], [["B1"], ["B2"], ["B3"]])
        self.assertEqual(result["group_basis"], "source_cited_grouping")

    def test_distinct_pair_blocks_transitive_merge(self):
        case = decision([["B1", "B2"], ["B3"]],
                        {"B1|B2": "related", "B1|B3": "related", "B2|B3": "distinct"})
        result = refinement.refine_decision(case)
        self.assertEqual(result["decision"], "multiple_businesses")
        self.assertEqual(result["groups"], [["B1", "B2"], ["B3"]])
        self.assertEqual(result["conflicting_pair_evidence"], ["B1|B3"])

    def test_completed_sale_removes_line_from_current_scope(self):
        case = decision([["B1", "B2"]], {"B1|B2": "related"})
        correction = {"line_status": {"B2": {"status": "exited", "as_of": "2022-07-27",
                                            "url": "https://example.com/sale"}}}
        updated = refinement.apply_source_corrections(case, correction)
        result = refinement.refine_decision(updated)
        self.assertEqual(result["groups"], [["B1"]])
        self.assertEqual(result["exited"], ["B2"])
        self.assertEqual(case["current"], ["B1", "B2"])

    def test_dated_group_override_must_cover_every_current_line(self):
        case = decision([["B1", "B2", "B3"]], {"B1|B2": "related"})
        correction = {"groups": [["B1"], ["B2", "B3"]],
                      "group_source_url": "https://example.com/report"}
        updated = refinement.apply_source_corrections(case, correction)
        self.assertEqual(refinement.refine_decision(updated)["groups"], correction["groups"])
        updated["source_group_override"] = [["B1"], ["B2"]]
        with self.assertRaises(ValueError):
            refinement.refine_decision(updated)


if __name__ == "__main__":
    unittest.main()
