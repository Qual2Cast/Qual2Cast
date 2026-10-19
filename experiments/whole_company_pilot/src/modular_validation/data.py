"""Read the pinned team snapshot without materializing any financial columns."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

IDENTIFIER_COLUMNS = ["IQ_COMPANY_ID", "target_company_name", "target_ciq_ticker",
                      "target_ciq_exchange", "target_ciq_website", "target_sic4_code",
                      "target_primary_sic_industry"]
FORBIDDEN_MATCHING_COLUMNS = {"target_revenue", "target_ebitda", "target_margin",
                              "target_debt_to_revenue", "target_ev_to_ebitda"}


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def team_modules(team_root: Path):
    """Import sanctioned control helpers without writing bytecode into the archive."""
    team_root = team_root.resolve(strict=True)
    sys.dont_write_bytecode = True
    for subdir in ["src", "website_scrape", "scraps/codex_profiles"]:
        location = str(team_root / subdir)
        if location not in sys.path:
            sys.path.insert(0, location)
    loader = _module(team_root / "src/project_data.py", "project_data")
    baseline = _module(team_root / "scraps/comps_first_pass/comps_similarity.py",
                       "modular_team_baseline")
    return loader, baseline


@dataclass
class Corpus:
    companies: pd.DataFrame
    universe: pd.DataFrame
    excluded: pd.DataFrame
    documents: pd.DataFrame
    provenance: dict
    team_baseline: object


def load_corpus(team_root: str | Path) -> Corpus:
    """Use the official loader/checksum, frozen masking and baseline eligibility.

    No targets are selected, no ranking is performed, and no outcome or financial
    predictor column is loaded. Baseline text is one control representation;
    documents retain raw/clean variants for subsequent declared transformations.
    """
    root = Path(team_root).resolve(strict=True)
    loader, baseline = team_modules(root)
    manifest = loader.load_manifest()
    snapshot = loader.snapshot_path(verify=True)
    companies = pd.read_csv(snapshot, dtype=str, keep_default_na=False,
                             usecols=IDENTIFIER_COLUMNS)
    companies = loader.normalize_sic_codes(companies)
    assert not (FORBIDDEN_MATCHING_COLUMNS & set(companies.columns))
    if companies["IQ_COMPANY_ID"].duplicated().any():
        raise ValueError("Snapshot contains duplicate company IDs")
    expected = manifest["snapshots"][manifest["required_snapshot"]].get("rows")
    if expected is not None and len(companies) != expected:
        raise ValueError(f"Expected {expected} companies, found {len(companies)}")

    scrape_root = root / "outputs-local/website_scrape"
    texts = baseline.page_texts(scrape_root)
    universe, excluded = baseline.build_universe(texts, companies, "pages")
    known_ids = set(companies.IQ_COMPANY_ID)
    rows, text_files = [], []
    for path in sorted((scrape_root / "page_text").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        cid = str(record["IQ_COMPANY_ID"])
        if cid not in known_ids:
            raise ValueError(f"Unexpected scraped company ID: {cid}")
        _, masked_pages = baseline.build_prompt(record) if record.get("pages") else (None, {})
        for page in record.get("pages", []):
            pid = str(page["page_id"])
            raw_html = root / page["raw_html_file"] if page.get("raw_html_file") else None
            rows.append({
                "company_id": cid, "source_id": f"{cid}:{pid}", "page_id": pid,
                "source_url": page["url"], "source_category": page.get("category", "unknown"),
                "fetched_at": page.get("fetched_at"), "archive_snapshot": page.get("snapshot"),
                "source_type": "company_website", "fetch_method": page.get("method"),
                "company_status": record["status"], "block_page": page.get("block_page", False),
                "text_masked": masked_pages.get(pid, ""),
                "text_clean": "\n".join([page.get("title", ""), page.get("meta", ""), *page.get("blocks", [])]),
                "text_raw": "\n".join([page.get("raw_title", ""), page.get("raw_meta", ""), *page.get("raw_blocks", [])]),
                "removed": page.get("removed", []),
                "raw_html_path": str(raw_html) if raw_html else None,
                "raw_html_available": bool(raw_html and raw_html.is_file()),
                "raw_html_sha256_recorded": page.get("raw_html_sha256"),
                "input_json_sha256": digest_file(path),
                "word_cap_dropped_blocks": page.get("blocks_cut_at_word_cap", 0),
            })
        text_files.append((path.name, digest_file(path)))
    documents = pd.DataFrame(rows)
    if not documents.empty and documents.source_id.duplicated().any():
        raise ValueError("Duplicate document source IDs")
    provenance = {
        "team_root": str(root), "team_commit": root.name,
        "required_snapshot": manifest["required_snapshot"],
        "snapshot_path": str(snapshot), "snapshot_sha256": digest_file(snapshot),
        "manifest_sha256": digest_file(root / "data_manifest.json"),
        "page_text_digest": hashlib.sha256(json.dumps(text_files, sort_keys=True).encode()).hexdigest(),
        "company_count": len(companies), "baseline_eligible_count": len(universe),
        "baseline_excluded_count": len(excluded), "documents": len(documents),
        "raw_html_available_count": int(documents.raw_html_available.sum()) if len(documents) else 0,
        "financial_columns_loaded": [], "targets_selected": False,
        "source_project_state_present": (root / "PROJECT_STATE.md").exists(),
        "baseline_eligibility_rule": "team status ok/thin_content and >=100 words after frozen cleanup",
        "financial_policy": "website-only control here; explicitly separate permitted financial augmentation later",
    }
    return Corpus(companies, universe, excluded, documents, provenance, baseline)


def write_input_audit(corpus: Corpus, output: str | Path) -> None:
    """Write an explicit new audit directory; refuse to overwrite prior artifacts."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "input_manifest.json").write_text(json.dumps(corpus.provenance, indent=2), encoding="utf-8")
    corpus.companies.to_csv(output / "company_identifiers.csv", index=False)
    corpus.excluded.to_csv(output / "excluded_control_companies.csv", index=False)
    coverage = corpus.documents.drop(columns=["text_clean", "text_raw", "text_masked", "removed"])
    coverage.to_csv(output / "source_coverage.csv", index=False)
    corpus.documents.to_json(output / "document_evidence.jsonl", orient="records", lines=True, force_ascii=False)
