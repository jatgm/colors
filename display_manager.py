"""
Multi-monitor display manager for Windows.
Enables borderless fullscreen spanning across multiple monitors,
individual monitor targeting, and DPI-aware coordinate mapping.
"""

import os
import sys
import ctypes
try:
    import ctypes.util
except Exception:
    pass
import pygame
from config import DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT
user32 = None
if sys.platform == "win32":
    try:
        from ctypes import wintypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
        user32 = ctypes.windll.user32
    except Exception:
        user32 = None


def query_windows_displays():
    """
    Query connected Windows display adapters and monitors via EnumDisplayDevices and EnumDisplaySettings.
    Returns list of dicts: [{'device': dev_name, 'x': x, 'y': y, 'width': w, 'height': h, 'hz': freq}, ...]
    """
    displays = []
    if sys.platform != "win32" or user32 is None:
        return displays
    try:
        from ctypes import wintypes

        class DEVMODE(ctypes.Structure):
            _fields_ = [
                ('dmDeviceName', ctypes.c_wchar * 32),
                ('dmSpecVersion', wintypes.WORD),
                ('dmDriverVersion', wintypes.WORD),
                ('dmSize', wintypes.WORD),
                ('dmDriverExtra', wintypes.WORD),
                ('dmFields', wintypes.DWORD),
                ('dmPosition_x', wintypes.LONG),
                ('dmPosition_y', wintypes.LONG),
                ('dmDisplayOrientation', wintypes.DWORD),
                ('dmDisplayFixedOutput', wintypes.DWORD),
                ('dmColor', wintypes.SHORT),
                ('dmDuplex', wintypes.SHORT),
                ('dmYResolution', wintypes.SHORT),
                ('dmTTOption', wintypes.SHORT),
                ('dmCollate', wintypes.SHORT),
                ('dmFormName', ctypes.c_wchar * 32),
                ('dmLogPixels', wintypes.WORD),
                ('dmBitsPerPel', wintypes.DWORD),
                ('dmPelsWidth', wintypes.DWORD),
                ('dmPelsHeight', wintypes.DWORD),
                ('dmDisplayFlags', wintypes.DWORD),
                ('dmDisplayFrequency', wintypes.DWORD),
                ('dmICMMethod', wintypes.DWORD),
                ('dmICMIntent', wintypes.DWORD),
                ('dmMediaType', wintypes.DWORD),
                ('dmDitherType', wintypes.DWORD),
                ('dmReserved1', wintypes.DWORD),
                ('dmReserved2', wintypes.DWORD),
                ('dmPanningWidth', wintypes.DWORD),
                ('dmPanningHeight', wintypes.DWORD),
            ]

        class DISPLAY_DEVICE(ctypes.Structure):
            _fields_ = [
                ('cb', wintypes.DWORD),
                ('DeviceName', ctypes.c_wchar * 32),
                ('DeviceString', ctypes.c_wchar * 128),
                ('StateFlags', wintypes.DWORD),
                ('DeviceID', ctypes.c_wchar * 128),
                ('DeviceKey', ctypes.c_wchar * 128),
            ]

        DISPLAY_DEVICE_ATTACHED_TO_DESKTOP = 0x00000001
        ENUM_CURRENT_SETTINGS = -1

        i = 0
        while True:
            dd = DISPLAY_DEVICE()
            dd.cb = ctypes.sizeof(dd)
            if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
                break
            if dd.StateFlags & DISPLAY_DEVICE_ATTACHED_TO_DESKTOP:
                dm = DEVMODE()
                dm.dmSize = ctypes.sizeof(dm)
                if user32.EnumDisplaySettingsW(dd.DeviceName, ENUM_CURRENT_SETTINGS, ctypes.byref(dm)):
                    displays.append({
                        'device': str(dd.DeviceName),
                        'x': int(dm.dmPosition_x),
                        'y': int(dm.dmPosition_y),
                        'width': int(dm.dmPelsWidth),
                        'height': int(dm.dmPelsHeight),
                        'hz': int(dm.dmDisplayFrequency),
                    })
            i += 1
    except Exception:
        pass
    return displays


def _create_display_surface(size, flags, display=None, vsync=1):
    """
    Creates Pygame display surface with hardware vsync support and graceful fallback.
    Prevents tearing across high refresh rate displays (e.g. 165Hz and 144Hz).
    """
    kwargs = {}
    if display is not None:
        kwargs["display"] = display
    if vsync:
        kwargs["vsync"] = 1

    try:
        return pygame.display.set_mode(size, flags, **kwargs)
    except (pygame.error, TypeError, Exception):
        try:
            kwargs.pop("vsync", None)
            return pygame.display.set_mode(size, flags, **kwargs)
        except (pygame.error, TypeError, Exception):
            kwargs.pop("display", None)
            return pygame.display.set_mode(size, flags)


class MonitorInfo:
    def __init__(self, index, left, top, right, bottom, refresh_rate=60):
        self.index = index
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom
        self.width = right - left
        self.height = bottom - top
        self.refresh_rate = int(refresh_rate) if refresh_rate else 60
        self.rect = pygame.Rect(left, top, self.width, self.height)
        if self.refresh_rate > 0:
            self.name = f"Monitor {index + 1} ({self.width}x{self.height} @ {self.refresh_rate}Hz)"
        else:
            self.name = f"Monitor {index + 1} ({self.width}x{self.height})"

    def contains(self, x, y):
        return self.left <= x < self.right and self.top <= y < self.bottom


class DisplayManager:
    # Display arrangement modes
    MODE_DUAL_SPAN = "Dual Monitor Fullscreen"
    MODE_MONITOR_1 = "Monitor 1 Fullscreen"
    MODE_MONITOR_2 = "Monitor 2 Fullscreen"
    MODE_WINDOWED = f"Windowed ({DEFAULT_WINDOW_WIDTH}x{DEFAULT_WINDOW_HEIGHT})"

    def __init__(self):
        self.monitors = []
        self.virtual_x = 0
        self.virtual_y = 0
        self.virtual_w = 1920
        self.virtual_h = 1080

        self.refresh_monitors()

        # Available display modes
        self.available_modes = []
        if len(self.monitors) >= 2:
            self.available_modes.append(self.MODE_DUAL_SPAN)
            self.available_modes.append(self.MODE_MONITOR_1)
            self.available_modes.append(self.MODE_MONITOR_2)
        else:
            self.available_modes.append(self.MODE_MONITOR_1)
        self.available_modes.append(self.MODE_WINDOWED)

        # Default to Dual Monitor Fullscreen if 2+ monitors are connected!
        self.current_mode_index = 0
        self.current_mode = self.available_modes[self.current_mode_index]

    def refresh_monitors(self):
        """Query connected monitors across Windows, macOS, and Linux."""
        self.monitors = []
        raw_rects = []

        if sys.platform == "win32" and user32 is not None:
            try:
                from ctypes import wintypes
                SM_XVIRTUALSCREEN = 76
                SM_YVIRTUALSCREEN = 77
                SM_CXVIRTUALSCREEN = 78
                SM_CYVIRTUALSCREEN = 79

                self.virtual_x = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
                self.virtual_y = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
                self.virtual_w = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
                self.virtual_h = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)

                def enum_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
                    r = lprcMonitor.contents
                    raw_rects.append((r.left, r.top, r.right, r.bottom))
                    return True

                MonitorEnumProc = ctypes.WINFUNCTYPE(
                    ctypes.c_bool, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
                )
                user32.EnumDisplayMonitors(None, None, MonitorEnumProc(enum_proc), 0)
            except Exception:
                pass

        elif sys.platform == "darwin":
            try:
                cg_path = ctypes.util.find_library("CoreGraphics") if hasattr(ctypes, "util") else None
                if cg_path:
                    cg = ctypes.cdll.LoadLibrary(cg_path)
                    max_displays = 16
                    displays = (ctypes.c_uint32 * max_displays)()
                    count = ctypes.c_uint32()
                    if cg.CGGetActiveDisplayList(max_displays, displays, ctypes.byref(count)) == 0 and count.value > 0:
                        class CGRect(ctypes.Structure):
                            _fields_ = [
                                ("x", ctypes.c_double),
                                ("y", ctypes.c_double),
                                ("w", ctypes.c_double),
                                ("h", ctypes.c_double),
                            ]
                        cg.CGDisplayBounds.restype = CGRect
                        cg.CGDisplayBounds.argtypes = [ctypes.c_uint32]
                        for i in range(count.value):
                            rect = cg.CGDisplayBounds(displays[i])
                            raw_rects.append((int(rect.x), int(rect.y), int(rect.x + rect.w), int(rect.y + rect.h)))
            except Exception:
                pass

        # Fallback for Linux or if platform-specific API returned no displays
        if not raw_rects:
            try:
                desktop_sizes = pygame.display.get_desktop_sizes()
                curr_x = 0
                for w, h in desktop_sizes:
                    raw_rects.append((curr_x, 0, curr_x + w, h))
                    curr_x += w
            except Exception:
                pass

        # Sort monitors left-to-right
        raw_rects.sort(key=lambda r: (r[0], r[1]))

        win_displays = query_windows_displays()
        pos_to_hz = {(d['x'], d['y']): d['hz'] for d in win_displays}
        size_to_hz = {(d['width'], d['height']): d['hz'] for d in win_displays}
        default_hz = max((d['hz'] for d in win_displays), default=165)

        for idx, (l, t, r, b) in enumerate(raw_rects):
            hz = pos_to_hz.get((l, t))
            if hz is None:
                hz = size_to_hz.get((r - l, b - t), default_hz)
            self.monitors.append(MonitorInfo(idx, l, t, r, b, refresh_rate=hz))

        if not self.monitors:
            # Fallback single monitor
            self.monitors.append(MonitorInfo(0, 0, 0, 1920, 1080, refresh_rate=default_hz))

        min_x = min(m.left for m in self.monitors)
        min_y = min(m.top for m in self.monitors)
        max_x = max(m.right for m in self.monitors)
        max_y = max(m.bottom for m in self.monitors)
        self.virtual_x = min_x
        self.virtual_y = min_y
        self.virtual_w = max_x - min_x
        self.virtual_h = max_y - min_y

    def get_max_refresh_rate(self):
        """Return highest refresh rate across all detected monitors (e.g. 165Hz)."""
        rates = [m.refresh_rate for m in self.monitors if getattr(m, 'refresh_rate', 0) > 0]
        return max(rates, default=165)

    def get_active_refresh_rate(self):
        """Return refresh rate target for current display arrangement mode."""
        if self.current_mode == self.MODE_DUAL_SPAN:
            return self.get_max_refresh_rate()
        elif self.current_mode == self.MODE_MONITOR_1:
            return self.monitors[0].refresh_rate if self.monitors else 165
        elif self.current_mode == self.MODE_MONITOR_2:
            return self.monitors[1].refresh_rate if len(self.monitors) >= 2 else (self.monitors[0].refresh_rate if self.monitors else 165)
        else:
            # Windowed mode
            return self.monitors[0].refresh_rate if self.monitors else 165

    def get_monitor_for_point(self, x, y):
        """Return the MonitorInfo that contains the given coordinate, or monitor 0."""
        for m in self.monitors:
            if m.contains(x, y):
                return m
        return self.monitors[0]

    def cycle_display_mode(self):
        """Cycle to the next display arrangement mode."""
        self.current_mode_index = (self.current_mode_index + 1) % len(self.available_modes)
        self.current_mode = self.available_modes[self.current_mode_index]
        return self.current_mode

    def set_display_mode(self, mode_or_idx):
        """Set the display arrangement mode by mode name or index."""
        if isinstance(mode_or_idx, int):
            self.current_mode_index = mode_or_idx % len(self.available_modes)
        elif mode_or_idx in self.available_modes:
            self.current_mode_index = self.available_modes.index(mode_or_idx)
        self.current_mode = self.available_modes[self.current_mode_index]
        return self.current_mode

    def apply_current_mode(self):
        """
        Creates and positions the Pygame display window according to current mode with hardware vsync.
        Returns (screen_surface, width, height, is_dual).
        """
        SWP_SHOWWINDOW = 0x0040
        HWND_TOP = 0

        def _set_win32_pos(x, y, w, h):
            if sys.platform == "win32" and user32 is not None:
                try:
                    hwnd = pygame.display.get_wm_info().get('window')
                    if hwnd:
                        user32.SetWindowPos(hwnd, HWND_TOP, x, y, w, h, SWP_SHOWWINDOW)
                except Exception:
                    pass

        if self.current_mode == self.MODE_DUAL_SPAN and len(self.monitors) >= 2:
            # Span entire virtual screen across both monitors borderless with vsync
            x, y = self.virtual_x, self.virtual_y
            w, h = self.virtual_w, self.virtual_h
            os.environ['SDL_VIDEO_WINDOW_POS'] = f"{x},{y}"

            flags = pygame.NOFRAME | pygame.DOUBLEBUF
            screen = _create_display_surface((w, h), flags, vsync=1)
            _set_win32_pos(x, y, w, h)
            return screen, w, h, True

        elif self.current_mode == self.MODE_MONITOR_1 or (self.current_mode == self.MODE_DUAL_SPAN and len(self.monitors) < 2):
            # Target Monitor 1 with vsync
            m = self.monitors[0]
            x, y, w, h = m.left, m.top, m.width, m.height
            os.environ['SDL_VIDEO_WINDOW_POS'] = f"{x},{y}"

            flags = pygame.NOFRAME | pygame.DOUBLEBUF
            screen = _create_display_surface((w, h), flags, display=0, vsync=1)
            _set_win32_pos(x, y, w, h)
            return screen, w, h, False

        elif self.current_mode == self.MODE_MONITOR_2 and len(self.monitors) >= 2:
            # Target Monitor 2 with vsync
            m = self.monitors[1]
            x, y, w, h = m.left, m.top, m.width, m.height
            os.environ['SDL_VIDEO_WINDOW_POS'] = f"{x},{y}"

            flags = pygame.NOFRAME | pygame.DOUBLEBUF
            screen = _create_display_surface((w, h), flags, display=1, vsync=1)
            _set_win32_pos(x, y, w, h)
            return screen, w, h, False

        else:
            # Windowed mode with vsync
            w, h = DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT
            # Center on primary monitor
            m = self.monitors[0]
            x = m.left + (m.width - w) // 2
            y = m.top + (m.height - h) // 2
            os.environ['SDL_VIDEO_WINDOW_POS'] = f"{x},{y}"

            flags = pygame.RESIZABLE | pygame.DOUBLEBUF
            screen = _create_display_surface((w, h), flags, display=0, vsync=1)
            _set_win32_pos(x, y, w, h)
            return screen, w, h, False
