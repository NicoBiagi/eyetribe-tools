import ctypes
from ctypes import wintypes


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class MonitorInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", ctypes.c_ulong),
    ]


MONITORENUMPROC = ctypes.WINFUNCTYPE(
    ctypes.c_int,
    ctypes.c_ulong,
    ctypes.c_ulong,
    ctypes.POINTER(RECT),
    ctypes.c_double,
)


def get_monitors():
    monitors = []

    def callback(hmonitor, hdc, rect_pointer, data):
        info = MonitorInfo()
        info.cbSize = ctypes.sizeof(MonitorInfo)
        ctypes.windll.user32.GetMonitorInfoW(hmonitor, ctypes.byref(info))

        left = info.rcMonitor.left
        top = info.rcMonitor.top
        right = info.rcMonitor.right
        bottom = info.rcMonitor.bottom

        monitors.append(
            {
                "index": len(monitors),
                "left": left,
                "top": top,
                "right": right,
                "bottom": bottom,
                "width": right - left,
                "height": bottom - top,
                "is_primary": bool(info.dwFlags & 1),
            }
        )

        return 1

    ctypes.windll.user32.EnumDisplayMonitors(
        0,
        0,
        MONITORENUMPROC(callback),
        0,
    )

    return monitors


def get_monitor(monitor_index=0):
    monitors = get_monitors()

    if not monitors:
        raise RuntimeError("No monitors detected.")

    if monitor_index < 0 or monitor_index >= len(monitors):
        raise ValueError(
            f"Monitor index {monitor_index} does not exist. "
            f"Detected monitors: {monitors}"
        )

    return monitors[monitor_index]


def print_monitors():
    monitors = get_monitors()

    for monitor in monitors:
        primary = " primary" if monitor["is_primary"] else ""
        print(
            f'{monitor["index"]}: '
            f'{monitor["width"]}x{monitor["height"]} '
            f'at ({monitor["left"]}, {monitor["top"]})'
            f'{primary}'
        )