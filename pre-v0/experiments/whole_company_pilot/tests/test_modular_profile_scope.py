import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from modular_validation import local_llm as mod


class FrozenProfileScope(unittest.TestCase):
    def corpus(self):
        return SimpleNamespace(
            universe=pd.DataFrame({"IQ_COMPANY_ID": ["A", "B", "C"]}),
            documents=pd.DataFrame([
                {"company_id": cid, "source_id": cid + ":P1",
                 "text_masked": cid + " provides software for fleet operations",
                 "block_page": False} for cid in ["A", "B", "C"]]),
            provenance={"fixture": "full three-company corpus"})

    def test_scope_rejects_duplicate_and_ineligible_ids(self):
        for ids in [[], ["A", "A"], ["Z"]]:
            with self.assertRaises(ValueError):
                mod.resolve_profile_scope(self.corpus(), ids)

    def test_scoped_generation_reuses_read_only_cache_and_keeps_semantic_hash(self):
        corpus = self.corpus()
        config = {"model_id": mod.MODEL_ID, "model_revision": mod.REVISION,
                  "prompt_version": mod.PROMPT_VERSION, "system_prompt": mod.SYSTEM,
                  "batch_size": 8, "max_input_tokens": 8192, "max_new_tokens": 2048,
                  "do_sample": False, "input_policy": "all available masked website pages in page order",
                  "corpus": corpus.provenance, "human_truth": False}
        key = hashlib.sha256(mod._canonical(config).encode()).hexdigest()
        model = MagicMock()
        model.runtime = {"test": "no GPU or real model"}
        model.generate.return_value = [{
            "text": json.dumps({"activities": [{"activity": "Fleet software",
                     "source_id": "B:P1", "quote": "provides software for fleet operations"}]}),
            "input_truncated": False, "output_hit_limit": False}]
        with tempfile.TemporaryDirectory() as folder:
            old = Path(folder) / "original"
            old.mkdir()
            checkpoint = old / "A.json"
            original = {"company_id": "A", "config_hash": key, "known_activities": []}
            checkpoint.write_text(json.dumps(original))
            before = checkpoint.read_bytes()
            output = Path(folder) / "pilot"
            with patch.object(mod, "LocalGroundedModel", return_value=model), \
                    patch.dict(sys.modules, {"torch": MagicMock()}):
                result = mod.extract_all_profiles(corpus, output, company_ids=["A", "B"],
                           read_only_cache_dirs=[old], execution_batch_size=32)
            self.assertEqual(set(result), {"A", "B"})
            self.assertEqual(result["B"]["config_hash"], key)
            self.assertEqual(checkpoint.read_bytes(), before)
            self.assertFalse((old / "B.json").exists())
            self.assertEqual([p.name for p in (output / key[:20]).glob("[ABC].json")], ["B.json"])
            model.generate.assert_called_once()
            self.assertIn("B:P1", model.generate.call_args.args[0][0][1]["content"])

    def test_incompatible_or_conflicting_checkpoint_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "A.json"
            path.write_text(json.dumps({"company_id": "A", "config_hash": "wrong"}))
            with self.assertRaises(ValueError):
                mod.read_cached_profile("A", "expected", [folder])


if __name__ == "__main__":
    unittest.main()
