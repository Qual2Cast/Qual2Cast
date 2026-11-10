"""Verify every reused MPNet vector against the installed local model."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import sentence_transformers
import torch

import b3_facet_add_drop as b3
import candidates as cd
import facet_weighting as fw


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "outputs-local/v1"
OUT = V1 / "integration/embedding_audit.json"
TOLERANCE = 5e-5


def general(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    filled = pd.read_csv(path, dtype=str).fillna("")
    filled = filled[(filled["business_id"] == "B1") & (filled["llm_status"] == "ok")]
    if filled["IQ_COMPANY_ID"].nunique() != 533 or filled["IQ_COMPANY_ID"].duplicated().any():
        raise ValueError(f"Incomplete general facet table: {path}")
    return filled, fw.facet_texts(filled)


def b0_cache(texts: pd.DataFrame) -> Path:
    key = json.dumps([cd.EMBED_MODEL, list(texts.index), texts.to_dict("list")],
                     ensure_ascii=False)
    name = f"facets_{cd.EMBED_MODEL.split('/')[-1]}_{hashlib.sha256(key.encode()).hexdigest()[:16]}.npz"
    return V1 / "embeddings" / name


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-only", action="store_true")
    args = parser.parse_args()
    sonnet, sonnet_text = general(V1 / "integration/sources/facets_sonnet_corrected.csv")
    gpt, gpt_text = general(V1 / "facets_codex_gpt61sol/tables/facets.csv")
    general_texts = {"sonnet": sonnet_text, "gpt": gpt_text}
    cited = None
    if not args.baseline_only:
        cited, general_texts["cited"] = general(V1 / "facets_source_gpt61sol/tables/facets.csv")
    sector = pd.read_csv(V1 / "sector_facets_codex_gpt61sol/tables/sector_facets.csv", dtype=str)
    industry = pd.read_csv(V1 / "industry_facets_codex_gpt61sol/tables/industry_facets_long.csv", dtype=str)
    texts = b3.required_texts(general_texts, sector, industry)
    texts.update(piece for table in general_texts.values()
                 for name in table for value in table[name].dropna()
                 for piece in fw.pieces(value))
    if not args.baseline_only:
        yifan = pd.read_csv(V1 / "integration/yifan_facets/facets.csv", dtype=str).fillna("")
        if yifan["IQ_COMPANY_ID"].nunique() != 533:
            raise ValueError("Incomplete Orbis-aligned facet table")
        for name in ("primary_offering", "end_markets"):
            texts.update(yifan.loc[yifan[name + "_status"].eq("stated"), name].dropna())
    originals = {"sonnet": cd.facet_texts(sonnet), "gpt": cd.facet_texts(gpt)}
    if cited is not None:
        originals["cited"] = cd.facet_texts(cited)
    for table in originals.values():
        texts.update(str(value) for name in table for value in table[name].dropna())

    work = fw.load_text_cache(b3.WORK_CACHE)
    seed = fw.load_text_cache(b3.EMBED_CACHE)
    reused = sorted(text for text in texts if fw._key(text) in work or fw._key(text) in seed)
    b0_paths = {name: b0_cache(table) for name, table in originals.items()}
    if not all(path.exists() for path in b0_paths.values()):
        raise FileNotFoundError("A B0 embedding cache is missing")
    audit_texts = set(reused)
    for table in originals.values():
        audit_texts.update(str(value) for name in table for value in table[name].dropna())
    ordered = sorted(audit_texts)
    fresh = dict(zip(ordered, cd.embed(ordered)))
    text_max = max((float(np.max(np.abs(
        fresh[text] - (work.get(fw._key(text)) if fw._key(text) in work
                       else seed[fw._key(text)])))) for text in reused), default=0.0)
    b0_max = 0.0
    for name, table in originals.items():
        with np.load(b0_paths[name]) as saved:
            for facet in table:
                matrix = saved[facet]
                for index, value in enumerate(table[facet]):
                    if pd.notna(value):
                        b0_max = max(b0_max, float(np.max(np.abs(matrix[index] - fresh[value]))))
    report = {"model": cd.EMBED_MODEL, "device": torch.cuda.get_device_name(0)
              if torch.cuda.is_available() else "CPU",
              "sentence_transformers": sentence_transformers.__version__,
              "torch": torch.__version__, "unique_texts": len(texts),
              "reused_texts_checked": len(reused), "b0_caches_checked": len(b0_paths),
              "max_abs_text_difference": text_max, "max_abs_b0_difference": b0_max,
              "tolerance": TOLERANCE,
              "status": "compatible" if max(text_max, b0_max) <= TOLERANCE else "mismatch"}
    output = OUT.with_name("embedding_audit_baseline.json") if args.baseline_only else OUT
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["status"] != "compatible":
        raise ValueError("Existing embeddings differ from the installed MPNet model")


if __name__ == "__main__":
    main()
