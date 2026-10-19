"""Verify pinned public models locally; no company inputs or external model API."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

ROOT = Path(__file__).resolve().parents[1]
MPNET = "sentence-transformers/all-mpnet-base-v2"
MPNET_REVISION = "e8c3b32edf5434bc2275fc9bab85f82640a19130"
QWEN = "Qwen/Qwen2.5-3B-Instruct"
QWEN_REVISION = "aa8e72537993ba99e69dfaafa59ed015b17504d1"


def run(download: bool, llm: bool):
    import numpy as np
    import torch
    import ot
    from gensim.models.doc2vec import Doc2Vec, TaggedDocument
    from huggingface_hub import snapshot_download
    from sentence_transformers import SentenceTransformer
    import trafilatura

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = {"timestamp_utc": stamp, "company_data_used": False,
              "external_model_api_used": False, "packages": {}}
    for name in ["numpy", "pandas", "scipy", "scikit-learn", "torch",
                 "sentence-transformers", "transformers", "gensim", "POT",
                 "trafilatura", "huggingface-hub", "accelerate"]:
        report["packages"][name] = importlib.metadata.version(name)
    report["cuda"] = {"available": torch.cuda.is_available(), "build": torch.version.cuda,
                      "architectures": torch.cuda.get_arch_list()}
    assert torch.cuda.is_available(), "CUDA is required for this local model smoke test"
    report["cuda"]["device"] = torch.cuda.get_device_name(0)
    report["cuda"]["capability"] = list(torch.cuda.get_device_capability(0))
    a = torch.ones((64, 64), device="cuda")
    assert float((a @ a.T)[0, 0]) == 64.0
    del a
    report["cuda"]["matrix_smoke"] = "passed"

    path = snapshot_download(MPNET, revision=MPNET_REVISION, token=False,
                             local_files_only=not download,
                             allow_patterns=["*.json", "*.txt", "*.safetensors", "1_Pooling/*"],
                             ignore_patterns=["onnx/*", "openvino/*"])
    model = SentenceTransformer(path, device="cuda", local_files_only=True,
                                trust_remote_code=False)
    embeddings = model.encode(["Synthetic payroll software example.",
                               "Synthetic fleet fuel payment example."],
                              normalize_embeddings=True, show_progress_bar=False)
    assert embeddings.shape == (2, 768) and np.isfinite(embeddings).all()
    report["mpnet"] = {"id": MPNET, "revision": MPNET_REVISION,
                       "cache_path": path, "shape": list(embeddings.shape),
                       "max_seq_length": model.max_seq_length, "smoke": "passed"}
    del model, embeddings
    torch.cuda.empty_cache()

    docs = [TaggedDocument("synthetic payroll software service".split(), ["A"]),
            TaggedDocument("synthetic fleet fuel payment".split(), ["B"])]
    d2v = Doc2Vec(vector_size=10, min_count=1, epochs=5, workers=1, seed=4511, dm=0)
    d2v.build_vocab(docs)
    d2v.train(docs, total_examples=len(docs), epochs=d2v.epochs)
    assert np.isfinite(d2v.dv["A"]).all()
    report["doc2vec_smoke"] = "passed"
    cost = np.array([[0.0, 1.0], [1.0, 0.0]])
    mass = np.array([0.5, 0.5])
    plan = ot.emd(mass, mass, cost)
    np.testing.assert_allclose(plan.sum(axis=0), mass)
    np.testing.assert_allclose(plan.sum(axis=1), mass)
    uplan, ulog = ot.unbalanced.sinkhorn_unbalanced(
        mass, mass, cost, reg=0.05, reg_m=1.0, reg_type="kl", log=True)
    assert np.isfinite(uplan).all() and "total_cost" in ulog
    report["ot_smoke"] = {"balanced": "passed", "unbalanced": "passed",
                           "uot_total_cost": float(ulog["total_cost"]),
                           "uot_linear_cost": float(ulog["cost"])}
    html = "<html><body><article><p>" + "Synthetic company manufactures durable pumps for water treatment. " * 10 + "</p></article></body></html>"
    assert trafilatura.extract(html)
    report["trafilatura_smoke"] = "passed"

    if llm:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        qpath = snapshot_download(QWEN, revision=QWEN_REVISION, token=False,
                                  local_files_only=True)
        tokenizer = AutoTokenizer.from_pretrained(qpath, local_files_only=True,
                                                  trust_remote_code=False)
        qmodel = AutoModelForCausalLM.from_pretrained(
            qpath, local_files_only=True, trust_remote_code=False,
            dtype=torch.bfloat16, device_map={"": "cuda:0"})
        messages = [{"role": "system", "content": "Use only the supplied synthetic evidence. Return JSON only."},
                    {"role": "user", "content": 'Evidence S1: The fictional company makes pumps. Return {"product":"pumps","source_id":"S1"}.'}]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda:0")
        with torch.inference_mode():
            output = qmodel.generate(**inputs, max_new_tokens=80, do_sample=False,
                                     pad_token_id=tokenizer.eos_token_id)
        generated = tokenizer.decode(output[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        start, end = generated.find("{"), generated.rfind("}")
        parsed = json.loads(generated[start:end+1])
        assert parsed == {"product": "pumps", "source_id": "S1"}
        report["local_llm"] = {"id": QWEN, "revision": QWEN_REVISION,
                               "cache_path": qpath, "synthetic_output": parsed,
                               "smoke": "passed", "human_truth": False}
        del qmodel
        torch.cuda.empty_cache()

    out = ROOT / "outputs-local/modular-validation/runtime"
    out.mkdir(parents=True, exist_ok=True)
    destination = out / f"runtime_{stamp}.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(destination), "checks": report}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--download-mpnet", action="store_true")
    parser.add_argument("--llm-smoke", action="store_true")
    args = parser.parse_args()
    run(args.download_mpnet, args.llm_smoke)
