"""Freeze uniform technical retry IDs from first-pass outputs, without rankings."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from modular_validation.local_llm import read_cached_profile, _canonical
from modular_validation.profile_repair import technical_retry_reason


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cache", type=Path)
    parser.add_argument("--scope-freeze", type=Path, required=True)
    parser.add_argument("--reuse-cache", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config_path = args.cache / "extraction_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("max_new_tokens") != 2048:
        raise ValueError("Technical repair selection requires the 2048-token first pass")
    config_hash = hashlib.sha256(_canonical(config).encode()).hexdigest()
    scope = json.loads(args.scope_freeze.read_text(encoding="utf-8"))
    ids = scope["company_ids"]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Frozen company IDs must be distinct and nonempty")
    rows, source_hashes = {}, {}
    for cid in ids:
        cached = read_cached_profile(cid, config_hash, [args.cache, *args.reuse_cache])
        if cached is None:
            raise RuntimeError(f"First pass incomplete for {cid}; no repair scope written")
        record, source = cached
        rows[cid] = record
        source_hashes[cid] = hashlib.sha256(source.read_bytes()).hexdigest()
    reasons = {cid: reason for cid, row in rows.items()
               if (reason := technical_retry_reason(row)) is not None}
    result = {"version": "uniform-technical-repair-v1", "created_at_utc": datetime.now(timezone.utc).isoformat(),
              "company_ids": list(reasons), "technical_reasons": reasons,
              "parent_scope_path": str(args.scope_freeze.resolve()),
              "parent_scope_sha256": hashlib.sha256(args.scope_freeze.read_bytes()).hexdigest(),
              "first_pass_config_hash": config_hash,
              "first_pass_config_path": str(config_path.resolve()),
              "first_pass_checkpoint_sha256": source_hashes,
              "input_truncated_not_repaired": [cid for cid, r in rows.items()
                                                if r.get("generation", {}).get("input_truncated", False)],
              "first_pass_company_count": len(ids), "repair_company_count": len(reasons),
              "selection_rule": "Every first-pass record with output_token_limit or invalid JSON/top-level schema, excluding input-truncated records. Valid JSON with missing or unsupported facts is not retried.",
              "required_change": {"max_new_tokens": 4096},
              "same_prompt_model_full_sources_and_other_semantics": True,
              "maximum_retries_per_company": 1, "no_relevance_or_outcome_inputs": True}
    if args.output.exists():
        previous = json.loads(args.output.read_text(encoding="utf-8"))
        compare = lambda obj: {k: v for k, v in obj.items() if k != "created_at_utc"}
        if compare(previous) != compare(result):
            raise FileExistsError("Existing repair scope differs; preserve it and record an explicit new decision")
        result = previous
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"repair_count": len(reasons), "path": str(args.output.resolve()),
                      "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
                      "input_truncated_count": len(result["input_truncated_not_repaired"])}), flush=True)


if __name__ == "__main__":
    main()
