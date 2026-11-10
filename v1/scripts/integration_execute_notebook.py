"""Execute only the new local-results cells; preserve the team's saved cells."""

from __future__ import annotations

import os
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

from integration_notebook import NOTEBOOK, ROOT, TAG


def main() -> None:
    environment = ROOT.parents[1] / ".venv" / "Scripts"
    if not (environment / "python.exe").exists():
        raise FileNotFoundError(environment / "python.exe")
    os.environ["PATH"] = str(environment) + os.pathsep + os.environ["PATH"]
    os.environ["PYTHONIOENCODING"] = "utf-8"
    notebook = nbf.read(NOTEBOOK, as_version=4)
    indices = [i for i, cell in enumerate(notebook.cells) if TAG in cell.metadata.get("tags", [])]
    part = nbf.v4.new_notebook(cells=[notebook.cells[i] for i in indices],
                               metadata={"kernelspec": {"name": "python3", "language": "python",
                                                        "display_name": "Python 3"}})
    executed = NotebookClient(part, timeout=120, kernel_name="python3",
                              resources={"metadata": {"path": str(ROOT)}}).execute()
    number = max((cell.execution_count or 0 for cell in notebook.cells
                  if cell.cell_type == "code" and TAG not in cell.metadata.get("tags", [])), default=0)
    for index, cell in zip(indices, executed.cells):
        if cell.cell_type == "code":
            number += 1
            cell.execution_count = number
        notebook.cells[index] = cell
    with NOTEBOOK.open("w", encoding="utf-8", newline="\n") as stream:
        nbf.write(notebook, stream)
    count = sum(cell.cell_type == "code" for cell in executed.cells)
    print(f"Executed {count} integration cells")


if __name__ == "__main__":
    main()
