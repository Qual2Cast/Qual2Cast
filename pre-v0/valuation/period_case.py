"""Programmatically reconcile two LTM routes on isolated public disclosures."""

from pathlib import Path
import hashlib
import re
from valuation.ebitda import from_net_income, ltm_ebitda

FIELDS = {
    "net_income": r"Net (?:income|loss|\(loss\))",
    "interest": r"Interest expense",
    "tax": r"Income tax",
    "depreciation": r"Depreciation expense",
    "amortization": r"Amortization expense",
}


def values(line):
    line = re.sub(r"^L\d+: ", "", line).replace("|", " ")
    tokens = re.findall(r"\(\s*\d+\.\d+\s*\)|(?<![\w.])\d+\.\d+|—", line)
    return [
        0.0 if x == "—" else -float(x.strip("() ")) if x.startswith("(") else float(x)
        for x in tokens
    ]


def parse_web_reconciliation(text):
    lines = text.splitlines()
    anchor = max(i for i, line in enumerate(lines) if "Depreciation expense" in line)
    section = lines[anchor - 4 : anchor + 3]
    rows = {}
    for key, pattern in FIELDS.items():
        line = next(
            line for line in section if re.match(pattern, re.sub(r"^L\d+: ", "", line))
        )
        rows[key] = values(line)
    sizes = {len(v) for v in rows.values()}
    if len(sizes) != 1 or sizes.pop() not in (2, 4):
        raise ValueError("Unexpected reconciliation layout")
    return rows


def public_ltm_case(source_dir, fy_table):
    source_dir, fy_table = Path(source_dir), Path(fy_table)
    text = fy_table.read_text(encoding="utf-8")
    fy_rows = {
        key: values(
            next(line for line in text.splitlines() if re.match(pattern, line.strip()))
        )
        for key, pattern in FIELDS.items()
    }
    fy_url = "https://s22.q4cdn.com/142468460/files/doc_financials/2025/q4/BrightView-8K-Q4FY25-Vf.pdf"

    def period(start, end, available, value, url):
        return dict(
            start=start,
            end=end,
            available_on=available,
            value=value,
            source_url=url,
            basis="net_income_bridge",
            currency="USD",
            units="millions",
            entity="BrightView Holdings, Inc.",
        )

    def bridge(rows, col):
        return from_net_income({key: row[col] for key, row in rows.items()})["value"]

    fy = period("2024-10-01", "2025-09-30", "2025-11-19", bridge(fy_rows, 0), fy_url)
    quarters = [
        period("2025-07-01", "2025-09-30", "2025-11-19", bridge(fy_rows, 2), fy_url)
    ]
    metadata = [
        ("q1", "2025-10-01", "2025-12-31", "2026-02-03"),
        ("q2", "2026-01-01", "2026-03-31", "2026-05-05"),
        ("q3", "2026-04-01", "2026-06-30", "2026-08-04"),
    ]
    evidence = []
    for key, start, end, available in metadata:
        file = source_dir / (key + "_web_capture.txt")
        raw = file.read_text(encoding="utf-8")
        url = re.search(r"\((https://investor\.brightview\.com/[^\s)]+)\)", raw).group(
            1
        )
        rows = parse_web_reconciliation(raw)
        quarters.append(period(start, end, available, bridge(rows, 0), url))
        evidence.append(
            {
                "source_url": url,
                "file": file.name,
                "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                "parsed_components": rows,
            }
        )
        if key == "q3":
            current = period(
                "2025-10-01", "2026-06-30", available, bridge(rows, 2), url
            )
            prior = period("2024-10-01", "2025-06-30", available, bridge(rows, 3), url)
    four = ltm_ebitda(quarters, "four_quarters", "2026-08-04")
    ytd = ltm_ebitda([fy, current, prior], "fy_plus_ytd", "2026-08-04")
    difference = abs(four["value"] - ytd["value"])
    return {
        "four_quarters": four,
        "fy_plus_ytd": ytd,
        "quarters": quarters,
        "fy_ytd_inputs": [fy, current, prior],
        "source_evidence": evidence,
        "evaluation": {
            "absolute_difference_usd_million": difference,
            "within_reported_rounding": difference <= 0.21,
            "interpretation": "Arithmetic agreement within disclosed rounding; not proof of maintainable earnings or fair value.",
        },
        "scope": "Isolated public measurement example. These IR values never enter private-target matching.",
    }
