"""Enter Windows background I/O/CPU scheduling before heavy imports."""
import ctypes as C
from ctypes import wintypes as W
import os
import runpy
import sys

if os.name == 'nt':
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = W.HANDLE
    kernel.SetPriorityClass.argtypes = [W.HANDLE, W.DWORD]
    if not kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x00100000):
        raise OSError(C.get_last_error(), 'Cannot enter task-local background resource scheduling')
    # Models reuse pages extensively. Keep the normal page-retention priority
    # while yielding I/O/CPU; very-low retention can cause repeated page faults.
    kernel.SetProcessInformation.argtypes = [W.HANDLE, C.c_int, C.c_void_p, W.DWORD]
    memory_priority = W.ULONG(5)
    if not kernel.SetProcessInformation(kernel.GetCurrentProcess(), 0,
                                       C.byref(memory_priority), C.sizeof(memory_priority)):
        raise OSError(C.get_last_error(), 'Cannot preserve normal memory page retention')
    os.environ['QUAL2CAST_BACKGROUND_ACTIVE'] = '1'
    print('BACKGROUND_RESOURCE_SCHEDULING_ENABLED', flush=True)
if len(sys.argv) < 2:
    raise ValueError('Explicit Python script required')
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name='__main__')
