"""
Checks on the Claude API before a facet fill, with fictional companies and one well-known real one
(about half a cent per run). Each check calls the API the way fill_facets.py
does and records what came back:

1. digit_rule_one_field: a one-field schema whose text may not contain a
   digit, "$" or "%", with a prompt that asks for figures. Does the API take
   the rule, and what does the model write instead?
2. digit_rule_full_schema: the full answer schema with the same rule on one
   text facet. Accepted, or refused before the model writes anything?
3. first_call / second_call: the current answer schema and prompt for two
   fictional companies in a row, with the instructions and schema as the
   cached system prompt (fill_facets.call_claude). Is the schema accepted,
   does the model mark an unknown company unknown instead of inventing it,
   and does the second call read the cache?
4. one_message_call: the first company again with the whole prompt as one
   user message (no system prompt, no cache), to see whether putting the
   instructions in the system prompt changes how much the model guesses.
5. known_company_call: one real, well-known company from the list
   (Paylocity, name and website only), to see that the rule against
   guessing doesn't also stop the model describing companies it knows.

Writes outputs-local/comps/api_checks/<time>/checks.json and each call's raw
response; facet_fill_runs.ipynb shows the latest.

  python v0/check_claude_api.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import facets as fc  # noqa: E402
import fill_facets as ff  # noqa: E402
from project_data import OUTPUTS_LOCAL  # noqa: E402
from universe import build_universe  # noqa: E402

MODEL = ff.DEFAULT_MODEL["claude"]
KNOWN_TICKER = "PCTY"     # a well-known company in the list (Paylocity)
# US dollars per 1M tokens for prompts up to 100K tokens: input, cache write, cache read, output
PRICE = {"input": 0.10, "cache_write": 0.125, "cache_read": 0.01, "output": 0.50}
DIGIT_RULE = r"^[^0-9$%]*$"
# Made up, with plausible names and web addresses and nothing that says so, as
# a private company the model doesn't know would look (2026-10-24: an earlier
# label "(fictional test company)" gave the answer away).
FICTIONAL = [{"IQ_COMPANY_ID": f"TEST{i}", "company_name": name, "website": site,
              "status": "not used", "pages": []}
             for i, (name, site) in enumerate([
                 ("Harlow & Pryce Rooftop Systems, Inc.", "www.harlowpryce-rooftop.com"),
                 ("Birch Valley Dairy Cooperative of Ohio", "www.birchvalleydairy-oh.com")], 1)]


def cost(usage: dict) -> float:
    """US dollars for one call, from the usage fill_facets records."""
    cached, written = usage.get("cached_input_tokens", 0), usage.get("cache_write_input_tokens", 0)
    return (PRICE["input"] * (usage["input_tokens"] - cached - written) + PRICE["cache_write"] * written
            + PRICE["cache_read"] * cached + PRICE["output"] * usage["output_tokens"]) / 1e6


def raw_call(schema: dict, prompt: str, run_dir: Path) -> dict:
    """One plain call with a given schema; a refusal before generation costs nothing."""
    import anthropic
    started = time.time()
    try:
        msg = ff.claude_client().messages.create(
            model=MODEL, max_tokens=ff.CLAUDE_MAX_TOKENS,
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": prompt}])
    except anthropic.BadRequestError as exc:
        return {"accepted": False, "error": exc.message[:300], "cost_usd": 0.0}
    (run_dir / "api_response.json").write_text(msg.to_json(), encoding="utf-8")
    usage = {"input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens}
    text = next((b.text for b in msg.content if b.type == "text"), "")
    return {"accepted": True, "stop_reason": msg.stop_reason, "answer": text, "usage": usage,
            "seconds": round(time.time() - started, 1), "cost_usd": cost(usage)}


def main() -> None:
    companies, _ = build_universe()     # company information only
    universe = companies[companies["in_universe"]]
    run = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = OUTPUTS_LOCAL / "comps" / "api_checks" / run
    checks = {}

    def run_dir(name: str) -> Path:
        d = out / name
        d.mkdir(parents=True, exist_ok=True)
        return d

    one_field = {"type": "object", "additionalProperties": False, "required": ["company_size"],
                 "properties": {"company_size": {"type": "string", "pattern": DIGIT_RULE}}}
    checks["digit_rule_one_field"] = raw_call(
        one_field, "A company has 120 plants, 5,000 employees and $2 billion in revenue. "
        "Describe its size in company_size, quoting those exact figures.", run_dir("digit_rule_one_field"))
    if checks["digit_rule_one_field"].get("answer"):
        size = json.loads(checks["digit_rule_one_field"]["answer"])["company_size"]
        checks["digit_rule_one_field"]["has_digit"] = any(ch.isdigit() for ch in size)

    full = fc.answer_schema(False)
    full["$defs"]["Facet_offering_description"]["properties"]["value"]["pattern"] = DIGIT_RULE
    prompt, _ = fc.build_prompt(FICTIONAL[0], False)
    checks["digit_rule_full_schema"] = raw_call(full, prompt, run_dir("digit_rule_full_schema"))

    split = len(fc.instructions(False))
    known = universe[universe["target_ciq_ticker"] == KNOWN_TICKER].iloc[0]
    known = ff.company_record(known["IQ_COMPANY_ID"], known["target_company_name"],
                              known["target_ciq_website"], False)
    for name, record, instructions_len in [("first_call", FICTIONAL[0], split),
                                           ("second_call", FICTIONAL[1], split),
                                           ("one_message_call", FICTIONAL[0], 0),
                                           ("known_company_call", known, split)]:
        prompt, lines = fc.build_prompt(record, False)
        result = ff.call_claude(prompt, run_dir(name), fc.answer_schema(False), MODEL, None,
                                instructions_len=instructions_len)
        check = {k: result.get(k) for k in ("llm_status", "stop_reason", "seconds", "usage", "error")}
        if result["llm_status"] == "ok":
            answer = fc.check_answer(json.loads(result["text"]), lines, {})
            statuses = [f["status"] for b in answer["businesses"] for f in b["facets"].values()]
            check["knows_company"] = answer["knows_company"]
            check["facets_unknown"] = f"{statuses.count('unknown')} of {len(statuses)}"
            check["answer_chars"] = len(result["text"])
            check["notes"] = answer["notes"]
        check["cost_usd"] = cost(result["usage"]) if result.get("usage") else 0.0
        checks[name] = check

    (out / "checks.json").write_text(json.dumps(
        {"run": run, "model": MODEL, "prompt_version": fc.PROMPT_VERSION, "price_per_mtok": PRICE,
         "checks": checks, "total_cost_usd": sum(c["cost_usd"] for c in checks.values())},
        indent=1, ensure_ascii=False), encoding="utf-8")
    for name, c in checks.items():
        print(f"{name:24} ${c['cost_usd']:.5f}  " + json.dumps(
            {k: v for k, v in c.items() if k not in ("answer", "cost_usd")}, ensure_ascii=False)[:160])
    print(f"-> {out}")


if __name__ == "__main__":
    main()
