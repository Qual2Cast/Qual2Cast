"""Resume a frozen company scope, or the full eligible universe, without uploads."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from modular_validation.data import load_corpus
from modular_validation.local_llm import extract_all_profiles, resolve_profile_scope


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", type=Path, default=ROOT / "outputs-local/modular-validation/design_freeze.json")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs-local/modular-validation/profile-cache")
    parser.add_argument("--execution-batch-size", type=int, default=16)
    parser.add_argument("--max-new-tokens", type=int, choices=[2048, 4096], default=2048,
                        help="4096 only for a separately frozen uniform technical-repair scope")
    parser.add_argument("--no-length-bucketing", action="store_true")
    parser.add_argument("--scope-freeze", type=Path,
                        help="Frozen JSON containing company_ids; never inferred from cache")
    parser.add_argument("--reuse-cache", type=Path, action="append", default=[],
                        help="Existing semantic-key cache directory, read only; repeatable")
    args = parser.parse_args()
    if args.execution_batch_size < 1:
        parser.error("execution batch size must be positive")
    design = json.loads(args.design.read_text(encoding="utf-8"))
    corpus = load_corpus(design["team_root"])
    scope = json.loads(args.scope_freeze.read_text(encoding="utf-8")) if args.scope_freeze else None
    ids = resolve_profile_scope(corpus, scope["company_ids"] if scope is not None else None)
    scope_metadata = ({"path": str(args.scope_freeze.resolve()),
                       "sha256": hashlib.sha256(args.scope_freeze.read_bytes()).hexdigest()}
                      if args.scope_freeze else None)
    profiles = extract_all_profiles(corpus, args.output, batch_size=8,
                                    max_input_tokens=8192, max_new_tokens=args.max_new_tokens,
                                    execution_batch_size=args.execution_batch_size,
                                    length_bucketing=not args.no_length_bucketing,
                                    company_ids=ids, read_only_cache_dirs=args.reuse_cache,
                                    scope_metadata=scope_metadata)
    assert set(profiles) == set(ids)
    key = profiles[ids[0]]["config_hash"]
    destination = args.output / key[:20] / "all_profiles.json"
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps({cid: profiles[cid] for cid in ids},
                                    ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(destination)
    print(json.dumps({"stage": "all_profiles_complete", "companies": len(profiles),
                      "path": str(destination), "scope_metadata": scope_metadata}), flush=True)


if __name__ == "__main__":
    main()
