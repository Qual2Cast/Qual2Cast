"""Concise, source-linked reports in the order used by TeamPipeline."""

from html import escape
import json
from pathlib import Path
import pandas as pd


def company_html(report):
    if report.get("status") == "identity_required":
        return "<p>Company identity is unresolved; no analysis was performed.</p>"
    stages = report["stages"]
    identity = report["identity"]
    name = identity.get("target_company_name", identity.get("IQ_COMPANY_ID", "Company"))

    def table(rows):
        return (
            "<div style='overflow-x:auto'>"
            + pd.DataFrame(rows).to_html(index=False, escape=True, border=0)
            + "</div>"
            if rows
            else "<p>No observations available.</p>"
        )

    def facts(values):
        return table(
            [
                {"item": k, "value": v}
                for k, v in values.items()
                if not isinstance(v, (list, dict))
            ]
        )

    parts = [
        "<!doctype html><html lang='en'><meta charset='utf-8'><title>Company Analysis</title>",
        "<style>body{max-width:1100px;margin:40px auto;padding:0 22px;font:16px/1.55 system-ui;color:#172533}h1,h2{line-height:1.2}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:9px;border-bottom:1px solid #dbe2e8;text-align:left;vertical-align:top}th{background:#edf3f7}a{color:#176580}code{background:#edf3f7;padding:2px 5px}section{margin:32px 0}.notice{border-left:4px solid #ad7519;padding:12px 16px;background:#fff8e9}</style>",
        "<h1>" + escape(str(name)) + "</h1>",
        "<p>Private-target simulation · Development evidence · 19 October 2026</p>",
        "<p class='notice'>This report uses ordinary website evidence and explicitly supplied financial inputs. "
        "Automated business approval is not independent human validation. Snapshot financial dates and definitions "
        "remain unverified; any computed value is a development proxy.</p>",
    ]
    parts += [
        "<section><h2>1. Company and input evidence</h2>",
        facts(identity),
        table(
            [
                {"factor": k, "value": v}
                for k, v in report["target_inputs"]["values"].items()
            ]
        ),
    ]
    parts.append(
        table(
            [{"input": k, **v} for k, v in report["target_inputs"]["sources"].items()]
        )
    )
    profile = stages["profile"]["result"]
    if profile.get("activities"):
        parts.append("<p><strong>Observed business activities</strong></p>")
        parts.append(
            table(
                [
                    {k: v for k, v in a.items() if k != "sentence_ids"}
                    for a in profile["activities"]
                ]
            )
        )
        parts.append("<p>" + escape(profile.get("scope_uncertainties", "")) + "</p>")
    for d in stages["evidence"]["result"]:
        url = d["source_url"]
        parts.append(
            "<p>"
            + escape(d["source_id"])
            + ": <a href='"
            + escape(url, quote=True)
            + "'>"
            + escape(url)
            + "</a> — "
            + ("retained" if d["eligible"] else "excluded")
            + "</p>"
        )
    parts.append("</section><section><h2>2. Candidate matching</h2>")
    parts.append(
        "<p>Method: <code>" + escape(stages["matching"]["method"]) + "</code>.</p>"
    )
    search = stages.get("candidate_search", {}).get("result", {})
    if search:
        parts.append(facts(search))
        parts.append(
            "<p>The requested count is ten approved peers. A review budget is resumable; "
            "unreviewed candidates have not been rejected. Scores order candidates and "
            "are not probabilities of comparability.</p>"
        )
        ranking = search["ranked_candidates"]
        columns = (
            "retrieval_rank",
            "peer",
            "retrieval_score",
            "ranking_stage",
            "review_status",
            "business_eligible",
        )
        display_rows = [{k: r.get(k) for k in columns} for r in ranking]
        parts.append(table(display_rows[:30]))
        if len(display_rows) > 30:
            parts.append("<details><summary>Remaining ranked candidates</summary>")
            parts.append(table(display_rows[30:]))
            parts.append("</details>")
    else:
        parts.append(table(stages["matching"]["result"]))
    parts.append(
        "</section><section><h2>3. Business comparability</h2><p>Function, operating role, customer use and the full observed business scope must all pass before financial ranking.</p>"
    )
    peer_names = {
        r["peer_id"]: r.get("peer", r["peer_id"]) for r in stages["matching"]["result"]
    }
    for row in stages["business_review"]["result"]:
        review = row.get("review") or {}
        if not row.get("eligible"):
            parts.append(
                "<details><summary>"
                + escape(peer_names.get(row["peer_id"], row["peer_id"]))
                + " — "
                + escape(row["status"])
                + "</summary>"
            )
        parts.append(
            "<h3>"
            + escape(peer_names.get(row["peer_id"], row["peer_id"]))
            + " — "
            + escape(row["status"])
            + "</h3>"
        )
        parts.append(
            "<p>"
            + escape(
                review.get("rationale", "No completed source review is available.")
            )
            + "</p>"
        )
        if review.get("scope_differences"):
            parts.append(
                "<p><strong>Scope differences:</strong> "
                + escape(review["scope_differences"])
                + "</p>"
            )
        decisions = review.get("criterion_decisions", review.get("checks", {}))
        parts.append(
            table([{"criterion": k, "decision": v} for k, v in decisions.items()])
        )
        for side in ("target", "peer"):
            for evidence in review.get(side + "_evidence", []):
                parts.append(
                    "<p><strong>"
                    + side.title()
                    + " evidence:</strong> “"
                    + escape(evidence["quote"])
                    + "” ("
                    + escape(evidence["source_id"])
                    + "). <a href='"
                    + escape(evidence.get("source_url") or "", quote=True)
                    + "'>Source</a></p>"
                )
        if not row.get("eligible"):
            parts.append("</details>")
    parts.append("</section><section><h2>4. Financial factors and growth evidence</h2>")
    factors = stages["factors"]
    parts.append(
        "<p>Factor method: <code>"
        + escape(factors["method"])
        + "</code>; status: "
        + escape(factors["result"]["status"])
        + ".</p>"
    )
    growth = stages["growth"]["result"]
    parts.append(
        "<p>Growth extraction: "
        + escape(growth["status"])
        + ". Events are evidence for review; no growth forecast or multiple premium is inferred.</p>"
    )
    parts.append(
        table(
            [
                {
                    k: e.get(k)
                    for k in ("event_type", "source_url", "event_date", "source_text")
                }
                for e in growth["events"]
            ]
        )
    )
    parts.append("</section><section><h2>5. EBITDA and valuation</h2>")
    parts.append("<p>Selected peers:</p>")
    parts.append(
        table(
            [
                {
                    k: p.get(k)
                    for k in (
                        "peer",
                        "selection_rank",
                        "factor_distance",
                        "public_peer_multiple",
                    )
                }
                for p in report["peers"]
            ]
        )
    )
    parts.append(facts(stages["measurement"]["result"]))
    parts.append(facts(stages["valuation"]["result"]))
    parts.append("</section><section><h2>6. Results and evaluation</h2>")
    parts.append(facts(report["audit"]))
    if report.get("development_evaluation"):
        parts.append(facts(report["development_evaluation"]))
    parts.append(
        "<p>Interpret the count of approved peers alongside abstentions. Missing or incompatible peers are not replaced by financially similar companies. Independent peer labels, aligned valuation dates and complete private-company inputs remain required for investment use.</p></section></html>"
    )
    return "\n".join(parts)


def export_reports(result_dir):
    result_dir = Path(result_dir)
    paths = []
    for path in sorted(result_dir.glob("*_Company_Report.json")):
        target = path.with_suffix(".html")
        target.write_text(
            company_html(json.loads(path.read_text(encoding="utf-8"))), encoding="utf-8"
        )
        paths.append(target)
    return paths
