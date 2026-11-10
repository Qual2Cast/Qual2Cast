"""Cache and validate Barbara's published economic-group profile shards."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
OUT = V1 / "integration/barbara_shards"
BASE = "https://barbara069.github.io/private-company-comparables-research/data/"
VERSION = "unified-public-research-20261030"


def load_catalog() -> dict:
    with gzip.open(V1 / "barbara_catalog_probe.json.gz", "rt", encoding="utf-8") as stream:
        return json.load(stream)


def fetch(name: str, expected: set[str]) -> dict:
    path = OUT / f"{name}.json.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        url = f"{BASE}{name}.json.gz?v={VERSION}"
        with urlopen(url, timeout=45) as response:
            payload = response.read()
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(payload)
        temporary.replace(path)
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        data = json.load(stream)
    if set(data) != expected:
        raise ValueError(f"Shard membership changed: {name}")
    return {"shard": name, "groups": len(data), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if args.workers < 1 or args.workers > 2:
        raise ValueError("Use one or two download workers")
    catalog = load_catalog()
    members: dict[str, set[str]] = {}
    for key, shard in catalog["groups"].items():
        members.setdefault(shard, set()).add(key)
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(fetch, name, keys): name for name, keys in members.items()}
        for future in as_completed(futures):
            records.append(future.result())
            print(f"{len(records)}/{len(members)} {futures[future]}", flush=True)
    record = {"version": VERSION, "catalog_groups": len(catalog["companies"]),
              "profile_groups": sum(item["groups"] for item in records),
              "shards": sorted(records, key=lambda item: item["shard"])}
    (OUT / "manifest.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"Validated {record['profile_groups']} profiles in {len(records)} shards")


if __name__ == "__main__":
    main()
