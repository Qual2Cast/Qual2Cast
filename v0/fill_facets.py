"""
Fill the facets (facets.py) for every company in the comp universe
(universe.py) with an LLM, then write the facet tables.

Three backends, one call per company, same prompt and answer schema:
- claude-cli: Claude Code CLI with its normal login, structured JSON output.
- claude (default): Claude Haiku 5.5 through the Anthropic API, paid per
  token from the team's Console account. Needs ANTHROPIC_API_KEY, set in
  the shell or in a .env file at the repo root (never committed). The
  schema goes in output_config.format.
- codex: Codex CLI (`codex exec`) under the student's own ChatGPT sign-in,
  in a read-only sandbox in an empty temp folder, so it doesn't load this
  repo's AGENTS.md. The schema goes in --output-schema.
--model picks the model within a backend; it is recorded in each call's
run.json and in the profile, and a profile made with another model is
redone. It never gets SIC codes, tickers or financial fields.

Three passes:
1. Every company from what the model knows: its name and website only.
2. Only companies left with an unknown facet get a second call with the
   page text already saved by the website scrape (no new scraping), and
   only the unknown facets are taken from it (facets.fill_gaps). Nothing
   the model filled from its own knowledge is replaced by page text, so a
   poor scraped description can't override it. The profile records what
   the second call filled under "gap_fill"; --no-gap-fill skips the pass.
3. Only companies split into several businesses get a third call: each
   business checked against the saved pages, because the model's knowledge
   of a company's structure can be years out of date. A business the pages
   don't show is removed, if another one is shown; nothing else changes.
   Recorded under "split_check" (with the removed businesses' facets);
   a company the pages can't confirm is flagged split_not_checked for the
   manual review. --no-split-check skips the pass.

Every call keeps its prompt, raw answer and logs under
<out>/codex_runs/<IQ_ID>/<time>/ (the folder name is kept from the first
backend). Profiles are made once per prompt, input and model; a rerun
skips finished companies, and a replaced profile or table moves to a
history folder instead of being overwritten. If the account's usage limit
or API credit runs out, or the API key is refused, the run stops; run it
again after fixing that.

  python v0/fill_facets.py --tickers AAON PCTY     # a few companies
  python v0/fill_facets.py                         # the whole universe
  python v0/fill_facets.py --backend codex --model gpt-6-luna --out ...
  python v0/fill_facets.py --tables-only           # rebuild the CSVs
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent))
import facets as fc  # noqa: E402  (also puts website_scrape/ and src/ on the path)
from project_data import OUTPUTS_LOCAL, REPO_ROOT  # noqa: E402
from universe import build_universe  # noqa: E402
from cli_models import call_cli, executable  # noqa: E402

SCRAPE_PAGE_TEXT = OUTPUTS_LOCAL / "website_scrape" / "page_text"
DEFAULT_OUT = OUTPUTS_LOCAL / "comps" / "facets"
CODEX_TIMEOUT_SECONDS = 600
DEFAULT_MODEL = {"claude": "claude-haiku-5-5", "codex": "", "claude-cli": ""}   # codex "": Codex's own default
CLAUDE_MAX_TOKENS = 16000    # answers are ~1k tokens plus thinking; well under this


def output_paths(out_dir: Path) -> SimpleNamespace:
    return SimpleNamespace(
        codex_runs=out_dir / "codex_runs",          # prompt, raw answer, logs per call
        answer_schema=out_dir / "answer_schema.json",              # name and website only
        answer_schema_pages=out_dir / "answer_schema_with_pages.json",
        profiles=out_dir / "profiles",              # one checked profile per company
        profiles_history=out_dir / "profiles_history",
        prompts_dry_run=out_dir / "prompts_dry_run",
        tables=out_dir / "tables",                  # facets.csv, facet_quotes.csv
        tables_history=out_dir / "tables_history",
    )


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


# ---------------------------------------------------------------- model call

def find_codex() -> str:
    exe = os.environ.get("CODEX_BIN") or shutil.which("codex")
    if not exe:
        raise SystemExit("Codex CLI not found. Install it once per laptop:\n"
                         "  npm install -g @openai/codex\n"
                         "  codex login      (sign in with your ChatGPT account)")
    return exe


def codex_usage(events: str) -> dict:
    """Token usage from Codex's JSONL events (last one wins), if any."""
    usage = {}
    for line in (events or "").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and isinstance(event.get("usage"), dict):
            usage = event["usage"]
    return usage


def call_codex(prompt: str, run_dir: Path, schema_path: Path, workdir: str,
               model: str | None, effort: str | None) -> dict:
    """Compatibility entry point; the shared transport owns its temporary workdir."""
    return call_cli(prompt, run_dir, json.loads(schema_path.read_text(encoding="utf-8")),
                    "codex", model, effort, CODEX_TIMEOUT_SECONDS)


def call_model(prompt: str, run_dir: Path, schema: dict, model: str | None,
               effort: str | None, backend: str = "claude", instructions_len: int = 0) -> dict:
    """Same prompt/schema for both CLI proxies; retain the original API option."""
    if backend == "claude":
        return call_claude(prompt, run_dir, schema, model, effort, instructions_len)
    return call_cli(prompt, run_dir, schema, backend, model, effort, CODEX_TIMEOUT_SECONDS)


def claude_api_key() -> str:
    """ANTHROPIC_API_KEY from the environment, else from a .env file at the
    repo root (KEY=value lines; .env is never committed)."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    env_file = REPO_ROOT / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "ANTHROPIC_API_KEY":
                key = value.strip().strip('"').strip("'")
    if not key:
        raise SystemExit("No Anthropic API key. Make one at console.anthropic.com (API keys), then either\n"
                         "  $env:ANTHROPIC_API_KEY = \"sk-ant-...\"      (PowerShell, this window only)\n"
                         "or put the line ANTHROPIC_API_KEY=sk-ant-... in a .env file at the repo root.")
    return key


_claude = None
_claude_lock = threading.Lock()


def claude_client():
    global _claude
    with _claude_lock:
        if _claude is None:
            import anthropic
            _claude = anthropic.Anthropic(api_key=claude_api_key(), max_retries=4)
    return _claude


def call_claude(prompt: str, run_dir: Path, schema: dict, model: str, effort: str | None,
                instructions_len: int = 0) -> dict:
    """One Messages API call; the answer is written to run_dir/response.json and
    the whole API response to run_dir/api_response.json.

    The prompt's first instructions_len characters (the instructions, the same
    for every company) go in the system prompt, marked for caching; the rest
    (the company) is the user message. The cache covers the system prompt and
    the answer schema (~5,800 tokens), so after the first call each company
    pays full price for ~40 input tokens and a tenth for the rest; the cache
    lasts 5 minutes from its last use."""
    import anthropic
    output_config = {"format": {"type": "json_schema", "schema": schema}}
    if effort:
        output_config["effort"] = effort
    system = [{"type": "text", "text": prompt[:instructions_len],
               "cache_control": {"type": "ephemeral"}}] if instructions_len else anthropic.omit
    started = time.time()
    try:
        msg = claude_client().messages.create(
            model=model, max_tokens=CLAUDE_MAX_TOKENS, output_config=output_config, system=system,
            messages=[{"role": "user", "content": prompt[instructions_len:].lstrip()}])
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
        return {"llm_status": "api_error", "error": f"{exc.status_code}: {exc.message}"[:300],
                "stop_run": True}
    except anthropic.APIStatusError as exc:
        # out of credit is a 400 with this message; the run can't go on
        return {"llm_status": "api_error", "error": f"{exc.status_code}: {exc.message}"[:300],
                "stop_run": "credit balance" in exc.message.lower()}
    except anthropic.APIConnectionError as exc:
        return {"llm_status": "api_error", "error": f"connection: {exc}"[:300]}
    (run_dir / "api_response.json").write_text(msg.to_json(), encoding="utf-8")
    u = msg.usage
    cached, written = u.cache_read_input_tokens or 0, u.cache_creation_input_tokens or 0
    # input_tokens counts every input token, cached or not, as Codex reports it;
    # cache writes cost 1.25x the input rate, reads 0.1x
    usage = {"input_tokens": u.input_tokens + cached + written, "cached_input_tokens": cached,
             "cache_write_input_tokens": written, "output_tokens": u.output_tokens}
    meta = {"api_model": msg.model, "request_id": msg._request_id, "stop_reason": msg.stop_reason,
            "seconds": round(time.time() - started, 1), "usage": usage}
    if msg.stop_reason == "refusal":
        category = msg.stop_details.category if msg.stop_details else None
        return {"llm_status": "refusal", "error": f"refusal: {category}", **meta}
    if msg.stop_reason == "max_tokens":
        return {"llm_status": "truncated", **meta}
    text = next((b.text for b in msg.content if b.type == "text"), "")
    if not text.strip():
        return {"llm_status": "no_output", **meta}
    (run_dir / "response.json").write_text(text, encoding="utf-8")
    return {"llm_status": "ok", "text": text, **meta}


def fill_one(record: dict, out_dir: Path, args, workdir: str, with_pages: bool = False) -> dict:
    """One company: prompt, model call, checks. Every file is kept."""
    paths = output_paths(out_dir)
    run_dir = paths.codex_runs / record["IQ_COMPANY_ID"] / stamp()
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt, lines = fc.build_prompt(record, with_pages)
    (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    input_figures = fc.figures_in_input(prompt, bool(lines))
    result = call_model(prompt, run_dir, fc.answer_schema(bool(lines)), args.model, args.effort,
                        args.backend, instructions_len=len(fc.instructions(bool(lines))))
    text = result.pop("text", None)
    if result["llm_status"] == "ok":
        page_urls = {p["page_id"]: p["url"] for p in record["pages"]}
        try:
            result["answer"] = fc.check_answer(json.loads(text), lines, page_urls)
        except json.JSONDecodeError:
            result["llm_status"] = "invalid_json"
        except ValidationError as exc:
            result["llm_status"] = "invalid_answer"
            result["shape_errors"] = [{"loc": ".".join(map(str, e["loc"])), "msg": e["msg"]}
                                      for e in exc.errors()][:50]
    result["input_figures"] = input_figures
    run_info = {"backend": args.backend, "model": args.model or "", "effort": args.effort or "",
                "with_pages": with_pages, "prompt_version": fc.PROMPT_VERSION, "finished_at": now_iso(),
                **{k: v for k, v in result.items() if k != "answer"}}
    (run_dir / "run.json").write_text(json.dumps(run_info, indent=1), encoding="utf-8")
    result["llm_run_dir"] = run_dir.relative_to(out_dir).as_posix()
    return result


def check_split(record: dict, profile: dict, out_dir: Path, args, workdir: str) -> dict:
    """Third pass, one company split into several businesses: each business
    checked against the saved website pages (facets.split_check_prompt).
    Every file is kept, as in fill_one."""
    run_dir = output_paths(out_dir).codex_runs / record["IQ_COMPANY_ID"] / stamp()
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt, _ = fc.split_check_prompt(record, profile["businesses"])
    (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    schema = fc.split_check_schema([b["business_id"] for b in profile["businesses"]])
    result = call_model(prompt, run_dir, schema, args.model, args.effort, args.backend)
    text = result.pop("text", None)
    if result["llm_status"] == "ok":
        try:
            result["raw"] = json.loads(text)
        except json.JSONDecodeError:
            result["llm_status"] = "invalid_json"
    run_info = {"backend": args.backend, "model": args.model or "", "effort": args.effort or "",
                "pass": "split_check", "with_pages": True, "prompt_version": fc.PROMPT_VERSION,
                "finished_at": now_iso(), **{k: v for k, v in result.items() if k != "raw"}}
    (run_dir / "run.json").write_text(json.dumps(run_info, indent=1), encoding="utf-8")
    result["llm_run_dir"] = run_dir.relative_to(out_dir).as_posix()
    return result


def with_split_checked(profile: dict, record: dict, result: dict | None) -> dict:
    """The profile after the third pass: businesses its current website pages
    don't show removed (facets.apply_split_check), recorded under
    "split_check" with the removed businesses' facets. result is None when
    the company has no saved page text to check against."""
    profile = copy.deepcopy(profile)
    check = {"llm_status": result["llm_status"] if result else "no_pages",
             "llm_run_dir": result.get("llm_run_dir", "") if result else "",
             # the pages: a rescrape changes it, and then the check runs again
             "input_sha256": fc.input_fingerprint(record, True), "created_at": now_iso()}
    if result and result.get("raw"):
        _, lines = fc.split_check_prompt(record, profile["businesses"])
        page_urls = {p["page_id"]: p["url"] for p in record["pages"]}
        profile["businesses"], outcome = fc.apply_split_check(profile["businesses"], result["raw"],
                                                              lines, page_urls)
        check.update(outcome)
    else:
        check["outcome"] = "not_checked"
    if check["outcome"] == "not_checked":                   # both for the manual review
        profile["issues"].append("split_not_checked")
    if check.get("disputed"):
        profile["issues"].append("split_disputed")
    profile["split_check"] = check
    return profile


def company_record(iq_id: str, name: str, website: str, with_pages: bool) -> dict:
    """What the model gets for one company: name and website, plus the saved
    page text if with_pages and the site was scraped."""
    record = {"IQ_COMPANY_ID": iq_id, "company_name": name, "website": website,
              "status": "not used", "pages": []}
    page_path = SCRAPE_PAGE_TEXT / f"{iq_id}.json"
    if with_pages and page_path.exists():
        scraped = json.loads(page_path.read_text(encoding="utf-8"))
        record.update(status=scraped["status"], pages=scraped["pages"])
    return record


def profile_record(record: dict, result: dict, model: str) -> dict:
    """The first pass's profile: the model's answer from the name and website."""
    answer = result.get("answer") or fc.unknown_facets(f"no answer ({result['llm_status']})")
    figures = result.get("input_figures", [])
    if figures:   # the prompt itself carried a figure (fc.figures_in_input)
        answer = {**answer, "issues": [*answer["issues"], "figures_in_input"]}
    return {
        "IQ_COMPANY_ID": record["IQ_COMPANY_ID"],
        "company_name": record["company_name"],
        "website": record["website"],
        "with_pages": False,
        "model": model,
        "prompt_version": fc.PROMPT_VERSION,
        "input_sha256": fc.input_fingerprint(record, False),
        "llm_status": result["llm_status"],
        "llm_run_dir": result.get("llm_run_dir", ""),
        "input_figures": figures,
        "created_at": now_iso(),
        **answer,
    }


def with_gaps_filled(profile: dict, record: dict, result: dict) -> dict:
    """The profile after the second pass: its unknown facets filled from the
    answer made with the saved pages (fc.fill_gaps), if that call gave one.
    Facets the model filled from what it knows are kept as they are. What
    the second call did is recorded under "gap_fill"."""
    profile = copy.deepcopy(profile)
    answer, filled = result.get("answer"), []
    if answer:
        filled, matched = fc.fill_gaps(profile["businesses"], answer["businesses"])
        if not matched:
            profile["issues"].append("gap_fill_business_mismatch")
    if result.get("input_figures"):
        profile["issues"].append("figures_in_input")
    profile["gap_fill"] = {
        "llm_status": result["llm_status"], "llm_run_dir": result.get("llm_run_dir", ""),
        # the second-pass prompt, pages included: a rescrape changes it, and
        # then the second pass runs again
        "input_sha256": fc.input_fingerprint(record, True),
        "scrape_status": record["status"],
        "pages": [{"page_id": p["page_id"], "url": p["url"], "category": p["category"]}
                  for p in record["pages"]],
        "input_figures": result.get("input_figures", []), "filled": filled,
        "notes": answer["notes"] if answer else "", "created_at": now_iso()}
    return profile


def has_unknown(profile: dict) -> bool:
    return any(f["status"] == "unknown" for b in profile.get("businesses", [])
               for f in b["facets"].values())


def is_current(profile: dict, record: dict, model: str, backend: str | None = None,
               effort: str | None = None) -> bool:
    return (profile.get("llm_status") == "ok"
            and profile.get("prompt_version") == fc.PROMPT_VERSION
            and profile.get("model", "") == model
            and (backend is None or profile.get("backend", "claude") == backend)
            and (backend is None or profile.get("effort", "") == (effort or ""))
            and profile.get("input_sha256") == fc.input_fingerprint(record, False))


# ---------------------------------------------------------------- tables

def review_reasons(profile: dict, business: dict) -> list[str]:
    """Why a business profile goes to the manual review, from what the fill
    recorded (no model): described_from_pages_only (the model didn't know
    the company, so every facet comes from its saved pages), facet_unknown,
    facet_flagged (any facet flag), and every other issue the profile has
    (pages_mention_divestiture, split_disputed, citation_not_read, ...).
    Empty: nothing to review."""
    reasons = ["described_from_pages_only"] if "company_not_known" in profile["issues"] else []
    if any(f["status"] == "unknown" for f in business["facets"].values()):
        reasons.append("facet_unknown")
    if any(f["flags"] for f in business["facets"].values()):
        reasons.append("facet_flagged")
    reasons += [i for i in profile["issues"] if i != "company_not_known"]
    return list(dict.fromkeys(reasons))


def write_tables(out_dir: Path) -> None:
    """facets.csv (one row per business, B1 the company's largest; most
    companies have one: for each facet its status, value, category (category
    facets), source and flags; needs_review and review_reasons, see
    review_reasons) and facet_quotes.csv (one row per cited page
    line, with its label and URL), from profiles made with the current
    PROMPT_VERSION; companies
    with only an older profile show as not_run. Earlier tables move to
    tables_history/<time>/."""
    paths = output_paths(out_dir)
    companies, _ = build_universe()
    universe = companies[companies["in_universe"]][["IQ_COMPANY_ID", "target_company_name"]]
    rows, quotes = [], []
    for path in sorted(paths.profiles.glob("*.json")):
        prof = json.loads(path.read_text(encoding="utf-8"))
        if prof["prompt_version"] != fc.PROMPT_VERSION:
            continue
        for b in prof["businesses"]:
            row = {"IQ_COMPANY_ID": prof["IQ_COMPANY_ID"], "business_id": b["business_id"],
                   "business": b["business"], "business_count": len(prof["businesses"]),
                   "llm_status": prof["llm_status"], "prompt_version": prof["prompt_version"],
                   "with_pages": prof["with_pages"]}
            for name, f in b["facets"].items():
                row[f"{name}_status"] = f["status"]
                row[name] = f["value"]
                if fc.FACET_BY_NAME[name].kind != "text":
                    row[f"{name}_category"] = f["category"]
                row[f"{name}_source"] = "; ".join(f["source"])
                row[f"{name}_flags"] = "; ".join(f["flags"])
                quotes += [{"IQ_COMPANY_ID": prof["IQ_COMPANY_ID"], "business_id": b["business_id"],
                            "facet": name, **q} for q in f["quotes"]]
            row["knows_company"] = prof.get("knows_company")
            # the third pass: confirmed, removed (some businesses), not_checked
            row["split_check"] = prof.get("split_check", {}).get("outcome", "")
            row["businesses_removed"] = "; ".join(
                r["business"] for r in prof.get("split_check", {}).get("removed", []))
            row["businesses_disputed"] = "; ".join(prof.get("split_check", {}).get("disputed", []))
            row["divestiture_lines"] = " | ".join(prof.get("divestiture_lines", []))
            row["issues"] = "; ".join(prof["issues"])
            reasons = review_reasons(prof, b)
            row["needs_review"] = bool(reasons)
            row["review_reasons"] = "; ".join(reasons)
            row["notes"] = prof["notes"]
            # facets the second pass filled from the saved pages
            row["filled_from_pages"] = "; ".join(
                f.split(" ", 1)[1] for f in prof.get("gap_fill", {}).get("filled", [])
                if f.startswith(b["business_id"] + " "))
            rows.append(row)
    facet_rows = pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["IQ_COMPANY_ID", "business_id", "business_count", "llm_status", "prompt_version"])
    table = universe.merge(facet_rows, on="IQ_COMPANY_ID", how="left")
    table["llm_status"] = table["llm_status"].fillna("not_run")
    table["business_count"] = pd.to_numeric(table["business_count"]).astype("Int64")

    paths.tables.mkdir(parents=True, exist_ok=True)
    old = list(paths.tables.glob("*.csv"))
    if old:
        dest = paths.tables_history / stamp()
        dest.mkdir(parents=True, exist_ok=True)
        for p in old:
            p.replace(dest / p.name)
    table.to_csv(paths.tables / "facets.csv", index=False)
    pd.DataFrame(quotes, columns=["IQ_COMPANY_ID", "business_id", "facet", "block", "page",
                                  "url", "quote", "quote_found"]).to_csv(
        paths.tables / "facet_quotes.csv", index=False)
    done = table.loc[table["llm_status"].eq("ok"), "IQ_COMPANY_ID"].nunique()
    print(f"Tables: {done}/{table['IQ_COMPANY_ID'].nunique()} universe companies have facets, "
          f"{table['llm_status'].eq('ok').sum()} business profiles -> {paths.tables}")


def load_profiles(out_dir: Path) -> pd.DataFrame:
    """Every profile in out_dir (profiles/ and profiles_history/), the latest
    per company and prompt version, any version: one row per business, with
    the call's model, effort, seconds and token usage from its run.json, a
    count of facets not unknown, and each facet's status, value, category
    and source. Versions before the business split (a-e) are one business,
    B1; version a's facets are the earlier website-only ones."""
    paths = output_paths(out_dir)
    latest = {}
    for path in [*paths.profiles.glob("*.json"), *paths.profiles_history.glob("*.json")]:
        prof = json.loads(path.read_text(encoding="utf-8"))
        key = (prof["IQ_COMPANY_ID"], prof["prompt_version"])
        if key not in latest or prof["created_at"] > latest[key]["created_at"]:
            latest[key] = prof
    rows = []
    for prof in latest.values():
        run_json = out_dir / prof.get("llm_run_dir", "") / "run.json"
        run = json.loads(run_json.read_text(encoding="utf-8")) if prof.get("llm_run_dir") \
            and run_json.exists() else {}
        businesses = prof.get("businesses") or [
            {"business_id": "B1", "business": "", "facets": prof.get("facets", {})}]
        for b in businesses:
            row = {"IQ_COMPANY_ID": prof["IQ_COMPANY_ID"], "prompt_version": prof["prompt_version"],
                   "llm_status": prof["llm_status"], "with_pages": prof.get("with_pages", True),
                   "model": run.get("model") or prof.get("model") or "default",
                   "effort": run.get("effort") or "default",
                   "seconds": run.get("seconds"), **run.get("usage", {}),
                   "business_id": b["business_id"], "business": b["business"],
                   "business_count": len(businesses), "notes": prof.get("notes", ""),
                   "knows_company": prof.get("knows_company"),
                   "facets_total": len(b["facets"]),
                   "facets_filled": sum(f["status"] != "unknown" for f in b["facets"].values())}
            for name, f in b["facets"].items():
                row[f"{name}_status"] = f["status"]
                row[name] = f["value"]
                row[f"{name}_category"] = f.get("category", "")
                row[f"{name}_source"] = "; ".join(f.get("source", []))
            rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- main

def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--tickers", nargs="*", help="only these tickers")
    p.add_argument("--limit", type=int, help="stop after N companies")
    p.add_argument("--refresh", action="store_true", help="redo current profiles too")
    p.add_argument("--backend", choices=["claude", "codex", "claude-cli"], default="claude",
                   help="codex / claude-cli: CLI proxies; claude: original Anthropic API")
    p.add_argument("--model", help="model (default: claude-haiku-5-5 for claude, "
                                   "Codex's configured model for codex)")
    p.add_argument("--effort", choices=["low", "medium", "high"],
                   help="reasoning effort (default: the model's own; medium on Haiku 5.5)")
    p.add_argument("--workers", type=int, default=2, help="companies in parallel")
    p.add_argument("--no-gap-fill", action="store_true",
                   help="skip the second pass (saved pages, for facets the model left unknown)")
    p.add_argument("--no-split-check", action="store_true",
                   help="skip the third pass (business splits checked against the saved pages)")
    p.add_argument("--dry-run", action="store_true",
                   help="write the first pass's prompts, don't call the model")
    p.add_argument("--tables-only", action="store_true", help="only rebuild the CSVs")
    args = p.parse_args(argv)
    args.model = args.model or DEFAULT_MODEL[args.backend]

    out_dir = Path(args.out).resolve()
    paths = output_paths(out_dir)
    if args.tables_only:
        write_tables(out_dir)
        return

    companies, _ = build_universe()
    companies = companies[companies["in_universe"]]
    if args.tickers:
        wanted = {t.upper() for t in args.tickers}
        companies = companies[companies["target_ciq_ticker"].str.upper().isin(wanted)]
    if args.limit:
        companies = companies.head(args.limit)

    paths.profiles.mkdir(parents=True, exist_ok=True)

    def current_profile(c) -> dict | None:
        path = paths.profiles / f"{c.IQ_COMPANY_ID}.json"
        if not path.exists():
            return None
        profile = json.loads(path.read_text(encoding="utf-8"))
        record = company_record(c.IQ_COMPANY_ID, c.target_company_name, c.target_ciq_website, False)
        return profile if is_current(profile, record, args.model, args.backend, args.effort) else None

    # First pass: every company from the model's own knowledge (name and website).
    todo = [(company_record(c.IQ_COMPANY_ID, c.target_company_name, c.target_ciq_website, False),
             paths.profiles / f"{c.IQ_COMPANY_ID}.json")
            for c in companies.itertuples() if args.refresh or current_profile(c) is None]

    out_dir.mkdir(parents=True, exist_ok=True)
    for pages, schema_path in [(False, paths.answer_schema), (True, paths.answer_schema_pages)]:
        schema_path.write_text(json.dumps(fc.answer_schema(pages), indent=1), encoding="utf-8")
    if args.dry_run:
        paths.prompts_dry_run.mkdir(parents=True, exist_ok=True)
        for record, _ in todo:
            prompt = fc.build_prompt(record, False)[0]
            (paths.prompts_dry_run / f"{record['IQ_COMPANY_ID']}.txt").write_text(
                prompt, encoding="utf-8")
        print(f"Wrote {len(todo)} prompts to {paths.prompts_dry_run}")
        return

    if args.backend == "claude":
        claude_api_key()   # fail early with setup instructions
    else:
        executable(args.backend)
    workdir = tempfile.mkdtemp(prefix="codex_facets_")
    stopped = threading.Event()   # usage limit, no credit, or key refused

    def save(out_path: Path, profile: dict) -> None:
        if out_path.exists():
            paths.profiles_history.mkdir(exist_ok=True)
            out_path.replace(paths.profiles_history / f"{out_path.stem}_{stamp()}.json")
        out_path.write_text(json.dumps(profile, indent=1, ensure_ascii=False), encoding="utf-8")

    def first_pass(record, out_path):
        result = fill_one(record, out_dir, args, workdir, with_pages=False)
        if not result.get("stop_run"):
            save(out_path, {**profile_record(record, result, args.model),
                            "backend": args.backend, "effort": args.effort or ""})
        return result

    def second_pass(record, out_path):
        result = fill_one(record, out_dir, args, workdir, with_pages=True)
        if not result.get("stop_run"):
            profile = json.loads(out_path.read_text(encoding="utf-8"))
            save(out_path, with_gaps_filled(profile, record, result))
        return result

    def third_pass(record, out_path):
        profile = json.loads(out_path.read_text(encoding="utf-8"))
        before = [b["business"] for b in profile["businesses"]]
        result = check_split(record, profile, out_dir, args, workdir)
        if not result.get("stop_run"):
            checked = with_split_checked(profile, record, result)
            save(out_path, checked)
            removed = [r["business"] for r in checked["split_check"].get("removed", [])]
            result["summary"] = (f"{checked['split_check']['outcome']}: {len(before)} -> "
                                 f"{len(checked['businesses'])} businesses"
                                 + (f" (removed: {'; '.join(removed)})" if removed else ""))
        return result

    def run_all(jobs, work, title):
        print(f"{title}: {len(jobs)} companies with {args.backend} "
              f"{args.model or '(default model)'} ({args.workers} at a time)...")

        def job(record, out_path):
            if stopped.is_set():
                return record, {"llm_status": "not_run"}
            result = work(record, out_path)
            if result.pop("stop_run", False):
                stopped.set()
                return record, {**result, "llm_status": "not_run"}
            return record, result

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(job, r, o) for r, o in jobs]
            for n, fut in enumerate(as_completed(futures), start=1):
                record, result = fut.result()
                if result["llm_status"] == "not_run":
                    if result.get("error"):
                        print(f"  not run: {result['error']}", flush=True)
                    continue
                detail = f"  {result['error']}" if result.get("error") else ""
                if "summary" in result:           # the third pass says what it did
                    what = result["summary"]
                else:
                    ans = result.get("answer")
                    facets = [f for b in ans["businesses"] for f in b["facets"].values()] if ans else []
                    filled = sum(f["status"] != "unknown" for f in facets)
                    split = f", {len(ans['businesses'])} businesses" if ans and len(ans["businesses"]) > 1 else ""
                    what = f"{filled}/{len(facets)} facets{split}"
                print(f"[{n}/{len(jobs)}] {record['company_name'][:40]:<40} "
                      f"{result['llm_status']:<14} {what}{detail}", flush=True)

    if todo:
        run_all(todo, first_pass, "First pass, from what the model knows")

    # Second pass: only companies left with an unknown facet, with their saved
    # pages; only those facets are taken from it (with_gaps_filled).
    gaps = []
    for c in companies.itertuples() if not (args.no_gap_fill or stopped.is_set()) else []:
        profile = current_profile(c)
        if not (profile and has_unknown(profile)):
            continue
        record = company_record(c.IQ_COMPANY_ID, c.target_company_name, c.target_ciq_website, True)
        tried = profile.get("gap_fill", {})
        # not yet tried, tried without an answer (an API error), or the saved
        # pages have changed since (a rescrape)
        if tried.get("llm_status") == "ok" and tried.get("input_sha256") == fc.input_fingerprint(record, True):
            continue
        if fc.build_prompt(record, True)[1]:      # some page text to try
            gaps.append((record, paths.profiles / f"{c.IQ_COMPANY_ID}.json"))
    if gaps:
        run_all(gaps, second_pass, "Second pass, saved pages for the unknown facets")

    # Third pass: companies split into several businesses, each business
    # checked against the saved pages; one they don't show is removed
    # (with_split_checked). Not yet checked, checked without an answer, or
    # the pages have changed since.
    splits = []
    for c in companies.itertuples() if not (args.no_split_check or stopped.is_set()) else []:
        profile = current_profile(c)
        if not (profile and len(profile.get("businesses", [])) > 1):
            continue
        record = company_record(c.IQ_COMPANY_ID, c.target_company_name, c.target_ciq_website, True)
        done = profile.get("split_check", {})
        if done.get("llm_status") in ("ok", "no_pages") and \
                done.get("input_sha256") == fc.input_fingerprint(record, True):
            continue
        out_path = paths.profiles / f"{c.IQ_COMPANY_ID}.json"
        if fc.build_prompt(record, True)[1]:
            splits.append((record, out_path))
        else:                                     # nothing to check against: flag it
            save(out_path, with_split_checked(profile, record, None))
    if splits:
        run_all(splits, third_pass, "Third pass, business splits checked against the saved pages")
    # Divestiture lines (no model): a company whose saved pages mention a sale,
    # divestiture or spin-off is flagged for the manual review; its facets
    # may describe something it no longer owns. Saved only when it changes.
    for c in companies.itertuples():
        profile = current_profile(c)
        if not profile:
            continue
        record = company_record(c.IQ_COMPANY_ID, c.target_company_name, c.target_ciq_website, True)
        found = fc.divestiture_lines(fc.build_prompt(record, True)[1])
        if found != profile.get("divestiture_lines", []):
            profile["divestiture_lines"] = found
            profile["issues"] = [i for i in profile["issues"] if i != "pages_mention_divestiture"] + \
                (["pages_mention_divestiture"] if found else [])
            save(paths.profiles / f"{c.IQ_COMPANY_ID}.json", profile)
    if not todo and not gaps and not splits:
        print("Nothing to do: every selected company has a current profile, no unknown facet "
              "is left that the saved pages could fill, and every split is checked.")
    shutil.rmtree(workdir, ignore_errors=True)
    if stopped.is_set():
        print("\nStopped: the usage limit or API credit ran out, or the API key was refused "
              "(error above). Fix that and run the same command again; finished companies "
              "are skipped.")
    write_tables(out_dir)


if __name__ == "__main__":
    main()
