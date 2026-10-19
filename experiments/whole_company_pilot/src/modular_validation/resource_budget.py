"""Conservative local execution budget; no model or source-policy changes."""
import os
import shutil
import time
from pathlib import Path
import psutil

GIB = 1024 ** 3


def check_capacity(path, *, initial_free=None, minimum_free_gib=30,
                   maximum_consumed_gib=60, minimum_ram_gib=12):
    free = shutil.disk_usage(Path(path).anchor or path).free
    ram = psutil.virtual_memory().available
    if free < minimum_free_gib * GIB:
        raise RuntimeError('Resource guard: preserve at least 30 GiB free disk')
    if initial_free is not None and initial_free - free > maximum_consumed_gib * GIB:
        raise RuntimeError('Resource guard: cumulative free-space reduction exceeds 60 GiB')
    if ram < minimum_ram_gib * GIB:
        raise RuntimeError('Resource guard: preserve at least 12 GiB available system RAM')
    return {'free_disk_bytes': free, 'available_ram_bytes': ram}


def configure_process():
    os.environ['QUAL2CAST_CPU_THREADS'] = '2'
    os.environ['QUAL2CAST_GPU_MEMORY_FRACTION'] = '0.5'
    os.environ['OMP_NUM_THREADS'] = '2'
    os.environ['MKL_NUM_THREADS'] = '2'
    if os.name == 'nt' and not os.environ.get('QUAL2CAST_BACKGROUND_ACTIVE'):
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)


def cool_down(elapsed_seconds):
    # The worker is backgrounded. Each pause is bounded, allowing progress checks.
    time.sleep(2.)
