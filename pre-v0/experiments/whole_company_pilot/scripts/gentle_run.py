"""Monitor only this task's worker tree and yield under desktop load.

Disk activity is a sampled metric, not a hard bandwidth cap. Short spikes may
precede suspension. No unrelated process is changed and no system setting is set.
"""
from pathlib import Path
import argparse
import ctypes as C
from ctypes import wintypes as W
import json
import os
import subprocess
import sys
import time
import psutil


class DiskActivity:
    def __init__(self):
        self.dll = C.WinDLL('pdh')
        self.query = W.HANDLE()
        self.counter = W.HANDLE()
        self.dll.PdhOpenQueryW.argtypes = [W.LPCWSTR, C.c_size_t, C.POINTER(W.HANDLE)]
        self.dll.PdhAddEnglishCounterW.argtypes = [W.HANDLE, W.LPCWSTR, C.c_size_t, C.POINTER(W.HANDLE)]
        self.dll.PdhCollectQueryData.argtypes = [W.HANDLE]
        self.dll.PdhGetFormattedCounterValue.argtypes = [W.HANDLE, W.DWORD, C.POINTER(W.DWORD), C.c_void_p]
        self.dll.PdhCloseQuery.argtypes = [W.HANDLE]
        if self.dll.PdhOpenQueryW(None, 0, C.byref(self.query)):
            raise RuntimeError('Cannot initialize disk activity monitor')
        self.path = r'\PhysicalDisk(0 C:)\% Idle Time'
        if self.dll.PdhAddEnglishCounterW(self.query, self.path, 0, C.byref(self.counter)):
            raise RuntimeError('Cannot monitor the observed C: physical disk')
        self.dll.PdhCollectQueryData(self.query)

    def read(self):
        class Value(C.Structure):
            _fields_ = [('status', W.DWORD), ('value', C.c_double)]
        value = Value()
        self.dll.PdhCollectQueryData(self.query)
        status = self.dll.PdhGetFormattedCounterValue(self.counter, 0x200, None, C.byref(value))
        if status or value.status not in (0, 1):
            raise RuntimeError('Disk activity counter unavailable; do not run unmonitored')
        return max(0., min(100., 100. - value.value))

    def close(self):
        self.dll.PdhCloseQuery(self.query)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        raise ValueError('An explicit local worker command is required')
    disk = DiskActivity()
    psutil.cpu_percent()
    time.sleep(1)
    disk.read()  # Monitoring must work before starting any computation.
    env = os.environ.copy()
    env.update(OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2',
               QUAL2CAST_CPU_THREADS='2', QUAL2CAST_GPU_MEMORY_FRACTION='0.5')
    child = subprocess.Popen(command, env=env, creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW)
    root = psutil.Process(child.pid)
    paused = []
    calm = 0
    events = []
    peak = {'disk_active_percent': 0., 'system_cpu_percent': 0., 'system_memory_percent': 0.}
    started = time.time()
    try:
        while child.poll() is None:
            time.sleep(1)
            reading = {'disk_active_percent': disk.read(), 'system_cpu_percent': psutil.cpu_percent(),
                       'system_memory_percent': psutil.virtual_memory().percent}
            for key, value in reading.items():
                peak[key] = max(peak[key], value)
            high = reading['disk_active_percent'] >= 88 or reading['system_cpu_percent'] >= 85 or reading['system_memory_percent'] >= 75
            low = reading['disk_active_percent'] < 60 and reading['system_cpu_percent'] < 65 and reading['system_memory_percent'] < 65
            if high and not paused:
                for process in root.children(recursive=True) + [root]:
                    try:
                        process.suspend()
                        paused.append(process)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                events.append({'seconds': round(time.time()-started, 1), 'action': 'pause_owned_worker', **reading})
                print('RESOURCE_YIELD', json.dumps(reading), flush=True)
                calm = 0
            elif paused:
                calm = calm + 1 if low else 0
                if calm >= 3:
                    for process in paused:
                        try:
                            process.resume()
                        except psutil.NoSuchProcess:
                            pass
                    paused = []
                    events.append({'seconds': round(time.time()-started, 1), 'action': 'resume_owned_worker', **reading})
                    print('RESOURCE_RESUME', flush=True)
        code = child.wait()
    except BaseException:
        for process in root.children(recursive=True) + [root]:
            try:
                process.terminate()
            except psutil.NoSuchProcess:
                pass
        raise
    finally:
        for process in paused:
            try:
                process.resume()
            except psutil.NoSuchProcess:
                pass
        disk.close()
    result = {'command': command, 'exit_code': code, 'elapsed_seconds': time.time()-started,
              'counter': disk.path, 'sampling_seconds': 1, 'peak_observed_system_load': peak,
              'events': events, 'limitation': 'Sampled cooperative pause, not a hard activity-time cap; other applications contribute to system readings.'}
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('GENTLE_RUN_COMPLETE', json.dumps(result['peak_observed_system_load']), 'exit', code, flush=True)
    raise SystemExit(code)


if __name__ == '__main__':
    main()
