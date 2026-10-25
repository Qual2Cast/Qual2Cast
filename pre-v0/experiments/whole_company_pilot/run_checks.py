"""Run the packaged implementation checks without model downloads."""
import os
from pathlib import Path
import subprocess
import sys
import uuid
root = Path(__file__).resolve().parent
(root/'outputs-local/modular-validation').mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
env.update(PYTHONPATH=str(root/'src'), MPLBACKEND='Agg', OMP_NUM_THREADS='2',
           MKL_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
(root/'.local').mkdir(exist_ok=True)
base_tmp = root/'.local'/('pytest-' + uuid.uuid4().hex)
assert base_tmp.resolve().is_relative_to(root.resolve()) and not base_tmp.exists()
result = subprocess.run([sys.executable,'-m','pytest','tests','-q','--basetemp',str(base_tmp)], cwd=root, env=env, capture_output=True, text=True)
(root/'.local/implementation-tests.txt').write_text(result.stdout + result.stderr, encoding='utf-8')
print(result.stdout + result.stderr)
raise SystemExit(result.returncode)
