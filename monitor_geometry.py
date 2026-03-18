import ctypes
import re
from ctypes import wintypes


MONITORINFOF_PRIMARY = 1


def _display_number_from_device(device_name):
    if not device_name:
        return 0
    match = re.search(r"DISPLAY(\d+)", device_name.upper())
    return int(match.group(1)) if match else 0


def get_selected_monitor():
    """Return the highest-numbered attached monitor, else primary monitor fallback."""
    user32 = ctypes.windll.user32

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
            ("szDevice", ctypes.c_wchar * 32),
        ]

    monitors = []

    def _enum_proc(hmonitor, hdc, lprc, lparam):
        del hdc, lprc, lparam
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            monitor_w = int(info.rcMonitor.right - info.rcMonitor.left)
            monitor_h = int(info.rcMonitor.bottom - info.rcMonitor.top)
            work_w = int(info.rcWork.right - info.rcWork.left)
            work_h = int(info.rcWork.bottom - info.rcWork.top)
            monitors.append(
                {
                    "device": str(info.szDevice),
                    "display_number": _display_number_from_device(str(info.szDevice)),
                    "x": int(info.rcMonitor.left),
                    "y": int(info.rcMonitor.top),
                    "width": monitor_w,
                    "height": monitor_h,
                    "work_x": int(info.rcWork.left),
                    "work_y": int(info.rcWork.top),
                    "work_width": work_w,
                    "work_height": work_h,
                    "is_primary": bool(info.dwFlags & MONITORINFOF_PRIMARY),
                }
            )
        return 1

    try:
        enum_proc = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(RECT),
            wintypes.LPARAM,
        )(_enum_proc)
        user32.EnumDisplayMonitors(0, 0, enum_proc, 0)
    except Exception:
        monitors = []

    if monitors:
        return max(monitors, key=lambda m: (m["display_number"], m["x"], m["y"]))

    screen_w = int(user32.GetSystemMetrics(0))
    screen_h = int(user32.GetSystemMetrics(1))
    return {
        "device": "",
        "display_number": 1,
        "x": 0,
        "y": 0,
        "width": screen_w,
        "height": screen_h,
        "work_x": 0,
        "work_y": 0,
        "work_width": screen_w,
        "work_height": screen_h,
        "is_primary": True,
    }


def center_on_monitor(width, height, monitor, margin=40):
    """Return clamped (width, height, x, y) centered in monitor work area."""
    work_x = int(monitor["work_x"])
    work_y = int(monitor["work_y"])
    work_w = int(monitor["work_width"])
    work_h = int(monitor["work_height"])

    max_w = max(640, work_w - margin)
    max_h = max(480, work_h - margin)
    target_w = min(int(width), max_w)
    target_h = min(int(height), max_h)

    x = work_x + max(0, (work_w - target_w) // 2)
    y = work_y + max(0, (work_h - target_h) // 2)
    return target_w, target_h, x, y


def set_tk_window_geometry(window, width, height, monitor=None):
    """Set a Tk window geometry centered on selected monitor work area."""
    monitor = monitor or get_selected_monitor()
    w, h, x, y = center_on_monitor(width, height, monitor)
    window.geometry(f"{w}x{h}+{x}+{y}")
    return w, h, x, y
