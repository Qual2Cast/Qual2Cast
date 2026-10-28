"""Guard against omitted or duplicated targets in batched peer selection."""

import unittest

from holdout_batched_routes import answers_by_target, chunks, direct_schema, judge_schema


class BatchTests(unittest.TestCase):
    def test_every_target_must_be_answered_once(self):
        good = {"targets": [{"target_id": "A", "comps": []},
                            {"target_id": "B", "comps": []}]}
        self.assertEqual(set(answers_by_target(good, ["A", "B"])), {"A", "B"})
        with self.assertRaises(ValueError):
            answers_by_target({"targets": [good["targets"][0]] * 2}, ["A", "B"])

    def test_schema_and_batches_preserve_requested_ids(self):
        targets = ["A", "B", "C"]
        self.assertEqual(list(chunks(targets, 2)), [["A", "B"], ["C"]])
        for make_schema in (direct_schema, judge_schema):
            target_item = make_schema(targets)["properties"]["targets"]["items"]
            self.assertEqual(target_item["properties"]["target_id"]["enum"], targets)


if __name__ == "__main__":
    unittest.main()
