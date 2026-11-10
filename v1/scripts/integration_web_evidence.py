"""Find official-site snippets for firms with no usable saved website lines."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse

import pandas as pd

import agent_loop
import b3_facet_add_drop as b3
import facets as fc
import fill_facets as ff


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
OUT = V1 / "integration/web_evidence"
sys.path.insert(0, str(ROOT / "v1/scripts/verification"))
import evidence as evm  # noqa: E402


def host(value: str) -> str:
    return (urlparse(value if "://" in value else "https://" + value).hostname or "").lower().removeprefix("www.")


def usable(url: str, website: str) -> bool:
    found = host(url)
    expected = host(website)
    return bool(found and expected and (found == expected or found.endswith("." + expected))
                and not re.search(r"/(?:ir|financials?|earnings|sec-filings?)(?:/|$)",
                                  urlparse(url).path, re.I))


def saved_search(query: str, directory: Path) -> list[dict]:
    prompt = directory / "search_prompt.txt"
    events = directory / "search_events.jsonl"
    if not prompt.exists() or not events.exists():
        return []
    if prompt.read_text(encoding="utf-8").strip() != (
            f"Use web search once for: {query}. Do not run commands or open local files."):
        return []
    results = []
    for line in events.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        item = event.get("item", {})
        if (event.get("type") == "item.completed" and item.get("type") == "web_search"
                and item.get("action", {}).get("query") == query):
            results.extend({"url": value.get("url", ""),
                            "title": value.get("title", ""),
                            "snippet": value.get("snippet", "")}
                           for value in item.get("results", [])
                           if value.get("type") == "text_result")
    return results


def record_for(iq: str, name: str, website: str) -> dict:
    saved = ff.company_record(iq, name, website, True)
    if fc.build_prompt(saved, True)[1]:
        return saved
    fallback = OUT / "pages" / f"{iq}.json"
    if fallback.exists():
        data = json.loads(fallback.read_text(encoding="utf-8"))
        if data["IQ_COMPANY_ID"] != iq or data["company_name"] != name or data["website"] != website:
            raise ValueError(f"Saved web evidence belongs to a different company input: {iq}")
        saved["pages"] = data["pages"]
        saved["status"] = data["source_mode"]
    return saved


def main() -> None:
    universe, ids, _, _ = b3.read_inputs()
    rows = universe.set_index("IQ_COMPANY_ID")
    search = agent_loop.codex_searcher("gpt-6.1-sol")
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    for iq in ids:
        row = rows.loc[iq]
        name, website = row.target_company_name, row.target_ciq_website
        saved = ff.company_record(iq, name, website, True)
        if fc.build_prompt(saved, True)[1]:
            continue
        output = OUT / "pages" / f"{iq}.json"
        if output.exists():
            data = json.loads(output.read_text(encoding="utf-8"))
            if data["company_name"] != name or data["website"] != website:
                raise ValueError(f"Saved web evidence input changed: {iq}")
            if not data["pages"]:
                results = saved_search(data["query"], OUT / "searches" / iq)
                candidates = [r for r in results if usable(r.get("url", ""), website)
                              and (r.get("snippet") or r.get("title"))]
                if candidates:
                    data["pages"] = [{"page_id": f"P{i}", "url": r["url"],
                                      "title": r.get("title", ""), "meta": "",
                                      "blocks": [r.get("snippet", "")],
                                      "category": "official_site_search_snippet"}
                                     for i, r in enumerate(candidates[:5], 1)]
                    data["search_snippets"] = len(data["pages"])
                    data["source_mode"] = "official_site_search_snippet"
                    output.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
        else:
            live_pages = []
            crawl_error = ""
            try:
                live = evm.gather(iq, name, website, crawl=True, search=False,
                                  out_root=OUT / "crawl")
                for sid, src in live.sources.items():
                    if not sid.startswith("W") or not usable(src["url"], website):
                        continue
                    blocks = [line for label, line in live.lines.items()
                              if label.startswith(sid + ".")]
                    if blocks:
                        live_pages.append({"page_id": f"P{len(live_pages) + 1}",
                                           "url": src["url"], "title": src.get("title", ""),
                                           "meta": "", "blocks": blocks,
                                           "category": "official_site_live_crawl"})
            except Exception as exc:
                crawl_error = str(exc)[:300]
            query = f"{name} official products services customers site:{host(website)}"
            results = search(query, OUT / "searches" / iq)
            candidates = [r for r in results if usable(r.get("url", ""), website)
                          and (r.get("snippet") or r.get("title"))]
            pages = live_pages + [{"page_id": f"P{i + len(live_pages)}", "url": r["url"], "title": r.get("title", ""),
                      "meta": "", "blocks": [r.get("snippet", "")],
                      "category": "official_site_search_snippet"}
                     for i, r in enumerate(candidates[:5], 1)]
            mode = ("official_site_live_crawl_and_search_snippet" if live_pages and candidates
                    else "official_site_live_crawl" if live_pages
                    else "official_site_search_snippet" if candidates else "no_official_site_evidence")
            data = {"IQ_COMPANY_ID": iq, "company_name": name, "website": website,
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "query": query, "source_mode": mode,
                    "live_pages": len(live_pages), "search_snippets": len(pages) - len(live_pages),
                    "crawl_error": crawl_error,
                    "pages": pages}
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        record = record_for(iq, name, website)
        n_lines = len(fc.build_prompt(record, True)[1])
        records.append({"IQ_COMPANY_ID": iq, "ticker": row.target_ciq_ticker,
                        "official_results": len(data["pages"]),
                        "live_pages": data.get("live_pages", 0),
                        "search_snippets": data.get("search_snippets", 0),
                        "crawl_error": data.get("crawl_error", ""),
                        "usable_lines": n_lines})
        print(f"{row.target_ciq_ticker}: {len(data['pages'])} official results, {n_lines} lines", flush=True)
    pd.DataFrame(records).to_csv(OUT / "coverage.csv", index=False)
    print(f"Searched {len(records)} firms without saved lines")


if __name__ == "__main__":
    main()
