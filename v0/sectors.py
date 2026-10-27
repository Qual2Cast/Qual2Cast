"""
Sectors for the specialized sub-models (recipe steps 5-6): each company's
Fama-French 49 industry (FF49) from its 4-digit SIC code, and a broader
sector group that decides which sector-specific facets it gets
(sector_facets.py) and which pool its sub-model searches.

FF49 definitions: v0/reference/Siccodes49.txt, Ken French's data library
(mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_49_ind_port.html),
the same file Barbara used for the growth base rates. A SIC code in no range
is FF49 "Other", as in French's own portfolios.

Sector is not a financial field: CapIQ gives a SIC code for private
companies too, so a private target has it. It is a matching input only
through the facets below (sector_similarity); EV/EBITDA is never read here.

Sector groups (SECTOR_GROUPS) merge FF49 industries whose businesses are
described by the same extra facets: a machinery maker and a chemicals maker
are both described by how they produce, a software firm and a staffing firm
are not. Edit the table to regroup; every FF49 industry must be in exactly
one group (checked in the tests).
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

FF49_FILE = Path(__file__).resolve().parent / "reference" / "Siccodes49.txt"
OTHER = "Other"

SECTOR_GROUPS: dict[str, tuple[str, ...]] = {
    "manufacturing": ("Chems", "Rubbr", "Txtls", "BldMt", "Steel", "FabPr", "Mach", "ElcEq", "Autos",
                      "Aero", "Ships", "Guns", "Hardw", "Chips", "LabEq", "Paper", "Boxes"),
    "consumer_products": ("Food", "Soda", "Beer", "Smoke", "Toys", "Hshld", "Clths"),
    "healthcare": ("Hlth", "MedEq", "Drugs"),
    "software": ("Softw",),
    "business_services": ("BusSv", "PerSv"),
    "consumer_venues": ("Rtail", "Meals", "Fun"),
    "distribution_transport": ("Whlsl", "Trans"),
    "construction_real_estate": ("Cnstr", "RlEst"),
    "financials": ("Banks", "Insur", "Fin"),
    "energy_resources": ("Agric", "Gold", "Mines", "Coal", "Oil", "Util"),
    "media_telecom": ("Telcm", "Books"),
    "other": ("Other",),
}
GROUP_OF = {ff: g for g, members in SECTOR_GROUPS.items() for ff in members}
SECTOR_LABELS = {
    "manufacturing": "Manufacturing (industrial, materials, electronics)",
    "consumer_products": "Consumer products (food, beverages, household, apparel)",
    "healthcare": "Healthcare (providers, devices, pharmaceuticals)",
    "software": "Software and internet",
    "business_services": "Business and personal services",
    "consumer_venues": "Retail, restaurants, hotels and entertainment",
    "distribution_transport": "Wholesale distribution and transportation",
    "construction_real_estate": "Construction and real estate",
    "financials": "Banks, insurance and other financials",
    "energy_resources": "Energy, utilities, mining and agriculture",
    "media_telecom": "Telecom, media and publishing",
    "other": "Other",
}


@lru_cache(maxsize=1)
def ff49_table(path: Path = FF49_FILE) -> pd.DataFrame:
    """One row per SIC range: lo, hi, ff49 (number), ff49_short, ff49_name."""
    rows, current = [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        rng = re.match(r"^\s+(\d{4})-(\d{4})", line)
        if rng:
            if current is None:
                raise ValueError(f"SIC range before any industry: {line!r}")
            rows.append({"lo": int(rng[1]), "hi": int(rng[2]), **current})
            continue
        head = re.match(r"^\s*(\d+)\s+(\S+)\s+(.*\S)\s*$", line)
        if head:
            current = {"ff49": int(head[1]), "ff49_short": head[2], "ff49_name": head[3]}
    return pd.DataFrame(rows)


@lru_cache(maxsize=1)
def ff49_names() -> dict[str, str]:
    t = ff49_table()
    return dict(zip(t["ff49_short"], t["ff49_name"]))


def ff49_of(sic4: str | int | float | None) -> str:
    """The FF49 short name for a SIC code ("Mach"); "Other" if it is in no
    range or missing. The first matching range wins (French's file has no
    overlaps)."""
    if sic4 is None or (isinstance(sic4, float) and np.isnan(sic4)) or str(sic4).strip() == "":
        return OTHER
    s = int(str(sic4).strip())
    t = ff49_table()
    hit = t[(t["lo"] <= s) & (t["hi"] >= s)]
    return hit["ff49_short"].iloc[0] if len(hit) else OTHER


def sector_table(info: pd.DataFrame, sic_col: str = "target_sic4_code") -> pd.DataFrame:
    """Per company (same index as `info`): sic4, ff49, ff49_name, sector."""
    sic = info[sic_col].astype(str).str.strip().str.zfill(4)
    ff = sic.map(ff49_of)
    return pd.DataFrame({"sic4": sic, "ff49": ff, "ff49_name": ff.map(ff49_names()).fillna(OTHER),
                         "sector": ff.map(GROUP_OF).fillna("other")}, index=info.index)


def sector_similarity(sectors: pd.DataFrame, ids: list[str], same_ff49: float = 1.0,
                      same_sector: float = 0.5) -> np.ndarray:
    """The sector facet as a similarity matrix in the order of `ids`: 1 for
    the same FF49 industry, 0.5 for another industry in the same sector
    group, 0 otherwise."""
    s = sectors.reindex(ids)
    ff = s["ff49"].to_numpy()
    grp = s["sector"].to_numpy()
    return np.where(ff[:, None] == ff[None, :], same_ff49,
                    np.where(grp[:, None] == grp[None, :], same_sector, 0.0)).astype(float)


def sic_similarity(sectors: pd.DataFrame, ids: list[str]) -> np.ndarray:
    """Sub-sector from the SIC code, no LLM: 1 for the same 4-digit SIC,
    2/3 for the same 3-digit, 1/3 for the same 2-digit, 0 otherwise."""
    sic = sectors.reindex(ids)["sic4"].astype(str).to_numpy()
    out = np.zeros((len(ids), len(ids)))
    for digits, score in ((2, 1 / 3), (3, 2 / 3), (4, 1.0)):
        p = np.array([s[:digits] for s in sic])
        out = np.where(p[:, None] == p[None, :], score, out)
    return out
