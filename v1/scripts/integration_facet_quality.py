"""Audit facet coverage and evidence provenance across team schemas."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import facets as fc
import integration_yifan_facets as yf


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
OUT = V1 / "integration/facet_quality"


def general_run_summary() -> None:
    root = V1 / "facets_codex_gpt61sol"
    profiles = [json.loads(path.read_text(encoding="utf-8"))
                for path in (root / "profiles").glob("*.json")]
    if len(profiles) != 533 or len({p["IQ_COMPANY_ID"] for p in profiles}) != 533:
        raise ValueError("GPT general profiles must cover 533 companies once")
    calls = []
    for profile in profiles:
        if profile["llm_status"] != "ok" or profile["prompt_version"] != fc.PROMPT_VERSION:
            raise ValueError("GPT general profile version or status changed")
        locations = [profile["llm_run_dir"]]
        if profile.get("gap_fill", {}).get("llm_run_dir"):
            locations.append(profile["gap_fill"]["llm_run_dir"])
        for location in locations:
            call = json.loads((root / location / "run.json").read_text(encoding="utf-8"))
            if call["model"] != "gpt-6.1-sol" or call["llm_status"] != "ok":
                raise ValueError(f"GPT model or call status changed: {location}")
            calls.append(call)
    usage = {name: sum(int(call.get("usage", {}).get(name, 0)) for call in calls)
             for name in ("input_tokens", "cached_input_tokens", "output_tokens")}
    (root / "run.json").write_text(json.dumps({
        "model": "gpt-6.1-sol", "backend": "codex", "prompt_version": fc.PROMPT_VERSION,
        "companies": len(profiles), "successful_calls": len(calls),
        "page_gap_calls": len(calls) - len(profiles), "usage": usage,
        "schema": "12 whole-company facets; B1 once per company",
    }, indent=2), encoding="utf-8")


def wide(source: str, path: Path, names: list[str], stated: tuple[str, ...]) -> list[dict]:
    table = pd.read_csv(path, dtype=str).fillna("")
    rows = []
    for name in names:
        status = table.get(name + "_status", pd.Series("", index=table.index))
        present = status.isin(stated)
        citation = table.get(name + "_cites", pd.Series("", index=table.index)).ne("")
        source_col = table.get(name + "_source", pd.Series("", index=table.index))
        evidence = citation | (source_col.ne("") & ~source_col.str.contains("model knowledge|from_memory", case=False))
        rows.append({"source": source, "field": name, "companies": table["IQ_COMPANY_ID"].nunique(),
                     "stated": int(present.sum()), "evidence_marked": int((present & evidence).sum())})
    return rows


def main() -> None:
    general_run_summary()
    general = [f.name for f in fc.FACETS]
    rows = []
    for label, path in (
        ("GPT memory-first", V1 / "facets_codex_gpt61sol/tables/facets.csv"),
        ("GPT cited-only", V1 / "facets_source_gpt61sol/tables/facets.csv"),
        ("Sonnet saved", V1 / "facets_sonnet/tables/facets.csv"),
    ):
        rows += wide(label, path, general, ("filled",))
    sector = pd.read_csv(V1 / "sector_facets_codex_gpt61sol/tables/sector_facets.csv",
                         dtype=str).fillna("")
    sector_names = sorted({c.removesuffix("_status") for c in sector if c.endswith("_status")
                           and c not in ("llm_status",)})
    rows += wide("GPT Fiona sector", V1 / "sector_facets_codex_gpt61sol/tables/sector_facets.csv",
                 sector_names, ("stated",))
    rows += wide("GPT Yifan Orbis", yf.OUT / "facets.csv",
                 [f["name"] for f in yf.definitions()], ("stated",))
    industry = pd.read_csv(V1 / "industry_facets_codex_gpt61sol/tables/industry_facets_long.csv",
                           dtype=str).fillna("")
    for name, part in industry.groupby("facet"):
        present = part["status"].eq("stated")
        evidence = part["source"].eq("evidence") & part["cites"].ne("")
        rows.append({"source": "GPT Barbara SIC2", "field": name,
                     "companies": part["IQ_COMPANY_ID"].nunique(),
                     "stated": int(present.sum()), "evidence_marked": int((present & evidence).sum())})
    output = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUT / "coverage.csv", index=False)
    summary = output.groupby("source")[["stated", "evidence_marked"]].sum().to_dict("index")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(pd.DataFrame(summary).T.to_string())


if __name__ == "__main__":
    main()
