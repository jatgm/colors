"""
Multi-monitor display manager for Windows.
Enables borderless fullscreen spanning across multiple monitors,
individual monitor targeting, and DPI-aware coordinate mapping.
"""

import os
import sys
import ctypes
import pygame
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


class MonitorInfo:
    def __init__(self, index, left, top, right, bottom):
        self.index = index
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom
        self.width = right - left
        self.height = bottom - top
        self.rect = pygame.Rect(left, top, self.width, self.height)
        self.name = f"Monitor {index + 1} ({self.width}x{self.height})"

    def contains(self, x, y):
        return self.left <= x < self.right and self.top <= y < self.bottom


class DisplayManager:
    # Display arrangement modes
    MODE_DUAL_SPAN = "Dual Monitor Fullscreen"
    MODE_MONITOR_1 = "Monitor 1 Fullscreen"
    MODE_MONITOR_2 = "Monitor 2 Fullscreen"
    MODE_WINDOWED = "Windowed (1280x720)"

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
                import ctypes.util
                cg_path = ctypes.util.find_library("CoreGraphics")
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

        for idx, (l, t, r, b) in enumerate(raw_rects):
            self.monitors.append(MonitorInfo(idx, l, t, r, b))

        if not self.monitors:
            # Fallback single monitor
            self.monitors.append(MonitorInfo(0, 0, 0, 1920, 1080))

        min_x = min(m.left for m in self.monitors)
        min_y = min(m.top for m in self.monitors)
        max_x = max(m.right for m in self.monitors)
        max_y = max(m.bottom for m in self.monitors)
        self.virtual_x = min_x
        self.virtual_y = min_y
        self.virtual_w = max_x - min_x
        self.virtual_h = max_y - min_y

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

    def apply_current_mode(self):
        """
        Creates and positions the Pygame display window according to current mode.
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
            # Span entire virtual screen across both monitors borderless
            x, y = self.virtual_x, self.virtual_y
            w, h = self.virtual_w, self.virtual_h
            os.environ['SDL_VIDEO_WINDOW_POS'] = f"{x},{y}"

            flags = pygame.NOFRAME | pygame.DOUBLEBUF
            screen = pygame.display.set_mode((w, h), flags)
            _set_win32_pos(x, y, w, h)
            return screen, w, h, True

        elif self.current_mode == self.MODE_MONITOR_1 or (self.current_mode == self.MODE_DUAL_SPAN and len(self.monitors) < 2):
            # Target Monitor 1
            m = self.monitors[0]
            x, y, w, h = m.left, m.top, m.width, m.height
            os.environ['SDL_VIDEO_WINDOW_POS'] = f"{x},{y}"

            flags = pygame.NOFRAME | pygame.DOUBLEBUF
            try:
                screen = pygame.display.set_mode((w, h), flags, display=0)
            except TypeError:
                screen = pygame.display.set_mode((w, h), flags)
            _set_win32_pos(x, y, w, h)
            return screen, w, h, False

        elif self.current_mode == self.MODE_MONITOR_2 and len(self.monitors) >= 2:
            # Target Monitor 2
            m = self.monitors[1]
            x, y, w, h = m.left, m.top, m.width, m.height
            os.environ['SDL_VIDEO_WINDOW_POS'] = f"{x},{y}"

            flags = pygame.NOFRAME | pygame.DOUBLEBUF
            try:
                screen = pygame.display.set_mode((w, h), flags, display=1)
            except TypeError:
                screen = pygame.display.set_mode((w, h), flags)
            _set_win32_pos(x, y, w, h)
            return screen, w, h, False

        else:
            # Windowed mode
            w, h = 1280, 720
            # Center on primary monitor
            m = self.monitors[0]
            x = m.left + (m.width - w) // 2
            y = m.top + (m.height - h) // 2
            os.environ['SDL_VIDEO_WINDOW_POS'] = f"{x},{y}"

            flags = pygame.RESIZABLE | pygame.DOUBLEBUF
            try:
                screen = pygame.display.set_mode((w, h), flags, display=0)
            except TypeError:
                screen = pygame.display.set_mode((w, h), flags)
            _set_win32_pos(x, y, w, h)
            return screen, w, h, False
