"""Build a separate canonical profile map; original model generations are kept."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from modular_validation.data import load_corpus
from modular_validation.profile_validation import validate_record, VERSION
from modular_validation.local_llm import resolve_profile_scope, read_cached_profile
from modular_validation.profile_repair import (technical_retry_reason, validate_repair_config,
                                                select_technical_repairs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cache", type=Path)
    parser.add_argument("--scope-freeze", type=Path)
    parser.add_argument("--reuse-cache", type=Path, action="append", default=[])
    parser.add_argument("--repair-cache", type=Path,
                        help="Separate 4096-token technical repair cache, after every trigger was attempted")
    parser.add_argument("--output", type=Path,
                        help="Canonical map destination directory; defaults to cache")
    args = parser.parse_args()
    design = json.loads((ROOT / "outputs-local/modular-validation/design_freeze.json").read_text())
    corpus = load_corpus(design["team_root"])
    scope = json.loads(args.scope_freeze.read_text(encoding="utf-8")) if args.scope_freeze else None
    ids = resolve_profile_scope(corpus, scope["company_ids"] if scope is not None else None)
    config = json.loads((args.cache / "extraction_config.json").read_text(encoding="utf-8"))
    if config.get("corpus") != corpus.provenance:
        raise ValueError("Current source corpus differs from the recorded extraction provenance")
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True, ensure_ascii=False,
                                           separators=(",", ":")).encode()).hexdigest()
    sources_by_id = {cid: read_cached_profile(cid, config_hash, [args.cache, *args.reuse_cache])
                     for cid in ids}
    missing = [cid for cid in ids if sources_by_id[cid] is None]
    if missing:
        raise RuntimeError(f"Frozen scope incomplete: {len(missing)} missing; no canonical map written")
    first_records = {cid: sources_by_id[cid][0] for cid in ids}
    first_hashes = {cid: hashlib.sha256(sources_by_id[cid][1].read_bytes()).hexdigest() for cid in ids}
    first_paths = {cid: str(sources_by_id[cid][1].resolve()) for cid in ids}
    repair_config_hash, repairs = None, None
    if args.repair_cache is not None:
        repair_config = json.loads((args.repair_cache / "extraction_config.json").read_text(encoding="utf-8"))
        validate_repair_config(config, repair_config)
        repair_config_hash = hashlib.sha256(json.dumps(repair_config, sort_keys=True, ensure_ascii=False,
                                                      separators=(",", ":")).encode()).hexdigest()
        retry_ids = [cid for cid in ids if technical_retry_reason(first_records[cid]) is not None]
        repair_sources = {cid: read_cached_profile(cid, repair_config_hash, [args.repair_cache]) for cid in retry_ids}
        incomplete = [cid for cid in retry_ids if repair_sources[cid] is None]
        if incomplete:
            raise RuntimeError(f"Uniform repair incomplete for {len(incomplete)} companies; no canonical map written")
        repairs = {cid: repair_sources[cid][0] for cid in retry_ids}
        sources_by_id.update(repair_sources)
    selected, lineage = select_technical_repairs(first_records, repairs)
    output = args.output or args.cache
    output.mkdir(parents=True, exist_ok=True)
    destination = output / "all_profiles_validated.json"
    if destination.exists():
        raise FileExistsError(f"Preserve existing canonical map: {destination}")
    profiles, input_hashes, input_paths = {}, {}, {}
    for cid in ids:
        _, source = sources_by_id[cid]
        record = selected[cid]
        input_hashes[cid] = hashlib.sha256(source.read_bytes()).hexdigest()
        input_paths[cid] = str(source.resolve())
        sources = {r.source_id: r.text_masked for r in
                   corpus.documents[corpus.documents.company_id == cid].itertuples()
                   if r.text_masked and not r.block_page}
        profiles[cid] = validate_record(record, sources)
        profiles[cid]["technical_repair_lineage"] = {**lineage[cid],
                         "first_pass_source_path": first_paths[cid],
                         "first_pass_sha256": first_hashes[cid],
                         "selected_source_path": input_paths[cid],
                         "selected_source_sha256": input_hashes[cid]}
    destination.write_text(json.dumps(profiles, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "validation_version": VERSION,
               "map_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
               "input_file_sha256": input_hashes, "companies": len(profiles),
               "input_paths": input_paths, "semantic_config_hash": config_hash,
               "repair_config_hash": repair_config_hash,
               "first_pass_input_paths": first_paths, "first_pass_input_file_sha256": first_hashes,
               "repair_lineage": lineage,
               "scope_freeze": str(args.scope_freeze.resolve()) if args.scope_freeze else None,
               "scope_sha256": hashlib.sha256(args.scope_freeze.read_bytes()).hexdigest() if args.scope_freeze else None,
               "statuses": dict(Counter(r["status"] for r in profiles.values())),
               "accepted_activities": sum(len(r["known_activities"]) for r in profiles.values()),
               "original_accepted_activities": sum(r["original_extraction_activity_count"] for r in profiles.values()),
               "schema_field_issues": sum(len(r["schema_field_issues"]) for r in profiles.values()),
               "independent_human_labels": 0, "raw_files_modified": False,
               "change": "Before profile ranking: preserve distinct facet contexts, consolidate exact duplicates, omit malformed or explicitly unknown facets; literal quote checks only, not semantic validation."}
    (output / "validation_manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    large_fields = {"input_file_sha256", "input_paths", "first_pass_input_paths",
                    "first_pass_input_file_sha256", "repair_lineage"}
    print(json.dumps({k: v for k, v in summary.items() if k not in large_fields}, indent=2))
    print(json.dumps({"canonical_profile_map": str(destination.resolve())}))


if __name__ == "__main__":
    main()
