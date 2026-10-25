"""Build versioned common inputs from the team's captures; never edit sources."""

from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
import pandas as pd
from matching.private_evidence import source_document, POLICY_VERSION

MPNET = "sentence-transformers/all-mpnet-base-v2"
REVISION = "e8c3b32edf5434bc2275fc9bab85f82640a19130"


def prepare_bundle(companies, captures, output, min_words=50):
    output, captures = Path(output), Path(captures)
    if output.exists():
        raise ValueError(
            "Use a new output directory; previous experiment inputs are immutable"
        )
    output.mkdir(parents=True)
    documents, rows, excluded = {}, [], []
    for row in companies.to_dict("records"):
        cid = row["IQ_COMPANY_ID"]
        path = captures / (cid + ".json")
        if not path.exists():
            excluded.append({"company_id": cid, "reason": "no_capture"})
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        docs = [source_document(cid, page) for page in record.get("pages", [])]
        documents.update({d["source_id"]: d for d in docs})
        text = "\n".join(d["text"] for d in docs if d["eligible"])
        if len(text.split()) < min_words:
            excluded.append(
                {
                    "company_id": cid,
                    "reason": "insufficient_permitted_text",
                    "words": len(text.split()),
                }
            )
            continue
        rows.append(
            {
                **row,
                "text": text,
                "words": len(text.split()),
                "urls": [d["source_url"] for d in docs if d["eligible"]],
                "status": record.get("status"),
                "page_count": sum(d["eligible"] for d in docs),
            }
        )
    data = pd.DataFrame(rows)
    data.to_json(
        output / "companies.json", orient="records", indent=1, force_ascii=False
    )
    (output / "documents.json").write_text(
        json.dumps(documents, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (output / "preparation.json").write_text(
        json.dumps(
            {
                "policy": POLICY_VERSION,
                "input_companies": len(companies),
                "retained_companies": len(data),
                "min_words": min_words,
                "excluded": excluded,
                "removed_items": sum(len(d["removed"]) for d in documents.values()),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return data


def build_representations(path, include_clusters=True):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import TruncatedSVD
    from sklearn.preprocessing import normalize
    from sentence_transformers import SentenceTransformer
    from huggingface_hub import snapshot_download
    import torch
    from matching.peer_selectors import umap_clusters

    torch.set_num_threads(2)
    path = Path(path)
    data = pd.read_json(path / "companies.json")
    out = path / "features"
    out.mkdir(exist_ok=False)
    sparse = TfidfVectorizer(
        ngram_range=(1, 2), min_df=1, max_features=12000, sublinear_tf=True
    ).fit_transform(data.text)
    tfidf = sparse.toarray().astype("float32")
    lsa = normalize(
        TruncatedSVD(
            n_components=min(96, len(data) - 1), random_state=4511
        ).fit_transform(sparse)
    ).astype("float32")
    model_path = snapshot_download(
        MPNET,
        revision=REVISION,
        local_files_only=True,
        token=False,
        allow_patterns=["*.json", "*.txt", "*.safetensors", "1_Pooling/*"],
        ignore_patterns=["onnx/*", "openvino/*"],
    )
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda":
        torch.cuda.set_per_process_memory_fraction(0.5)
    model = SentenceTransformer(
        model_path, device=device, local_files_only=True, trust_remote_code=False
    )
    chunks, owners = [], []
    for i, text in enumerate(data.text):
        words = text.split()
        for start in range(0, len(words), 200):
            chunks.append(" ".join(words[start : start + 200]))
            owners.append(i)
    vectors = model.encode(
        chunks, batch_size=4, normalize_embeddings=True, show_progress_bar=False
    )
    E = normalize(
        np.stack(
            [vectors[np.array(owners) == i].mean(axis=0) for i in range(len(data))]
        )
    ).astype("float32")
    del model
    if device == "cuda":
        torch.cuda.empty_cache()
    for name, matrix in [("mpnet", E), ("tfidf", tfidf), ("lsa", lsa)]:
        np.save(out / ("team_" + name + ".npy"), matrix)
    if include_clusters:
        _, labels = umap_clusters(E, seed=0)
        np.savez(out / "cluster_labels_seed0.npz", **labels)
    (out / "manifest.json").write_text(
        json.dumps(
            {
                "company_ids": data.IQ_COMPANY_ID.tolist(),
                "text_sha256": hashlib.sha256(
                    "\0".join(data.text).encode()
                ).hexdigest(),
                "representations": ["mpnet", "tfidf", "lsa"],
                "model": MPNET,
                "revision": REVISION,
                "policy": POLICY_VERSION,
                "chunks": len(chunks),
                "chunk_words": 200,
                "tfidf_max_features": 12000,
                "lsa_components": lsa.shape[1],
                "seed": 4511,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "companies": len(data),
        "chunks": len(chunks),
        "model": MPNET,
        "device": device,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--captures", type=Path, default=Path("outputs-local/website_scrape/page_text")
    )
    args = parser.parse_args()
    from src.project_data import snapshot_path, normalize_sic_codes

    companies = normalize_sic_codes(pd.read_csv(snapshot_path(), dtype=str))
    prepare_bundle(companies, args.captures, args.output)
    print(json.dumps(build_representations(args.output)))


if __name__ == "__main__":
    main()
