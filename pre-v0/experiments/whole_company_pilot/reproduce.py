"""Execute the published notebook with this Python interpreter; no model refit."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys


def main():
    from jupyter_client import KernelManager
    from jupyter_client.kernelspec import KernelSpecManager
    from nbclient import NotebookClient
    import nbformat

    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notebook", type=Path, default=root.parents[1]/"notebooks/whole_company_pilot.ipynb")
    args = parser.parse_args()
    work = root/".local"/datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    kernel = work/"kernels"/"pilot"
    kernel.mkdir(parents=True)
    (kernel/"kernel.json").write_text(json.dumps({
        "argv":[sys.executable,"-m","ipykernel_launcher","-f","{connection_file}"],
        "display_name":"Pilot replay", "language":"python"}), encoding="utf-8")
    manager = KernelManager(kernel_name="pilot", kernel_spec_manager=KernelSpecManager(kernel_dirs=[str(work/"kernels")]))
    notebook = nbformat.read(args.notebook, as_version=4)
    env = os.environ.copy()
    env.update(OMP_NUM_THREADS="2", MKL_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2",
               HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    notebook = NotebookClient(notebook, km=manager, timeout=300, allow_errors=False,
        resources={"metadata":{"path":str(work)}}).execute(env=env)
    destination = work/"replayed.ipynb"
    nbformat.write(notebook, destination)
    print("Reproduced notebook:", destination)


if __name__ == "__main__":
    main()
