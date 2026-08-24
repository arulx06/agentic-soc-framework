"""Cross-platform memory probing without hard dependencies.

Used by the resource-profile resolver (auto mode) and by the CLI to log peak
RSS for bounded-memory verification.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes  # noqa: F401
import sys

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_DARWIN = sys.platform == "darwin"


def _windows_memory() -> tuple[int, int] | None:
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_uint64),
            ("ullAvailPhys", ctypes.c_uint64),
            ("ullTotalPageFile", ctypes.c_uint64),
            ("ullAvailPageFile", ctypes.c_uint64),
            ("ullTotalVirtual", ctypes.c_uint64),
            ("ullAvailVirtual", ctypes.c_uint64),
            ("ullAvailExtendedVirtual", ctypes.c_uint64),
        ]

    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
        return None
    return int(stat.ullTotalPhys), int(stat.ullAvailPhys)


def _linux_memory() -> tuple[int, int] | None:
    try:
        with open("/proc/meminfo", "r", encoding="ascii") as fh:
            values = {}
            for line in fh:
                key, _, rest = line.partition(":")
                parts = rest.split()
                if parts:
                    values[key] = int(parts[0]) * 1024
        if "MemTotal" in values and "MemAvailable" in values:
            return values["MemTotal"], values["MemAvailable"]
    except OSError:
        return None
    return None


def _darwin_memory() -> tuple[int, int] | None:
    try:
        import subprocess

        out = subprocess.run(
            ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, check=True
        )
        total = int(out.stdout.strip())
        vm_stat = subprocess.run(["vm_stat"], capture_output=True, text=True, check=True)
        page_size = 4096
        free = 0
        for line in vm_stat.stdout.splitlines():
            if "page size of" in line:
                page_size = int(line.split("page size of")[1].split()[0])
            elif "Pages free" in line:
                free = int(line.split(":")[1].strip().rstrip("."))
        return total, free * page_size
    except Exception:
        return None


def total_and_available_bytes() -> tuple[int, int]:
    """Return (total_physical_bytes, currently_available_bytes)."""
    result = None
    if IS_WINDOWS:
        result = _windows_memory()
    elif IS_LINUX:
        result = _linux_memory()
    elif IS_DARWIN:
        result = _darwin_memory()
    if result is None:
        raise RuntimeError("memory probe unsupported on this platform")
    return result


def _process_memory_counters_windows() -> tuple[int, int] | None:
    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.wintypes.HANDLE
    kernel32.K32GetProcessMemoryInfo.argtypes = (
        ctypes.wintypes.HANDLE,
        ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
        ctypes.c_ulong,
    )
    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
    handle = kernel32.GetCurrentProcess()
    if not kernel32.K32GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
        return None
    return int(counters.WorkingSetSize), int(counters.PeakWorkingSetSize)


def current_and_peak_rss_bytes() -> tuple[int, int]:
    """Return (current_rss_bytes, peak_rss_bytes) for this process."""
    if IS_WINDOWS:
        result = _process_memory_counters_windows()
        if result is not None:
            return result
        return 0, 0
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        current = 0
        try:
            with open("/proc/self/status", "r", encoding="ascii") as fh:
                for line in fh:
                    if line.startswith("VmRSS:"):
                        current = int(line.split()[1]) * 1024
                        break
        except OSError:
            pass
        peak_kb = getattr(usage, "ru_maxrss", 0)
        peak_bytes = peak_kb * 1024
        return max(current, 0), max(peak_bytes, current)
    except Exception:
        return 0, 0
