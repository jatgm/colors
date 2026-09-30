"""
Multi-monitor display manager for Windows.
Enables borderless fullscreen spanning across multiple monitors,
individual monitor targeting, and DPI-aware coordinate mapping.
"""

import os
import sys
import ctypes
from ctypes import wintypes
import pygame

# Initialize DPI awareness so Windows reports exact physical pixels
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.windll.user32


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
        """Query connected monitors via Windows User32 API."""
        self.monitors = []
        SM_XVIRTUALSCREEN = 76
        SM_YVIRTUALSCREEN = 77
        SM_CXVIRTUALSCREEN = 78
        SM_CYVIRTUALSCREEN = 79

        self.virtual_x = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        self.virtual_y = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        self.virtual_w = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        self.virtual_h = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)

        raw_rects = []

        def enum_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
            r = lprcMonitor.contents
            raw_rects.append((r.left, r.top, r.right, r.bottom))
            return True

        MonitorEnumProc = ctypes.WINFUNCTYPE(
            ctypes.c_bool, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
        )
        user32.EnumDisplayMonitors(None, None, MonitorEnumProc(enum_proc), 0)

        # Sort monitors left-to-right
        raw_rects.sort(key=lambda r: (r[0], r[1]))

        for idx, (l, t, r, b) in enumerate(raw_rects):
            self.monitors.append(MonitorInfo(idx, l, t, r, b))

        if not self.monitors:
            # Fallback
            self.monitors.append(MonitorInfo(0, 0, 0, 1920, 1080))

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

        if self.current_mode == self.MODE_DUAL_SPAN and len(self.monitors) >= 2:
            # Span entire virtual screen across both monitors borderless
            x, y = self.virtual_x, self.virtual_y
            w, h = self.virtual_w, self.virtual_h
            os.environ['SDL_VIDEO_WINDOW_POS'] = f"{x},{y}"

            flags = pygame.NOFRAME | pygame.DOUBLEBUF
            screen = pygame.display.set_mode((w, h), flags)

            try:
                hwnd = pygame.display.get_wm_info().get('window')
                if hwnd:
                    user32.SetWindowPos(hwnd, HWND_TOP, x, y, w, h, SWP_SHOWWINDOW)
            except Exception:
                pass

            return screen, w, h, True

        elif self.current_mode == self.MODE_MONITOR_1 or (self.current_mode == self.MODE_DUAL_SPAN and len(self.monitors) < 2):
            # Target Monitor 1
            m = self.monitors[0]
            x, y, w, h = m.left, m.top, m.width, m.height
            os.environ['SDL_VIDEO_WINDOW_POS'] = f"{x},{y}"

            flags = pygame.NOFRAME | pygame.DOUBLEBUF
            screen = pygame.display.set_mode((w, h), flags)

            try:
                hwnd = pygame.display.get_wm_info().get('window')
                if hwnd:
                    user32.SetWindowPos(hwnd, HWND_TOP, x, y, w, h, SWP_SHOWWINDOW)
            except Exception:
                pass

            return screen, w, h, False

        elif self.current_mode == self.MODE_MONITOR_2 and len(self.monitors) >= 2:
            # Target Monitor 2
            m = self.monitors[1]
            x, y, w, h = m.left, m.top, m.width, m.height
            os.environ['SDL_VIDEO_WINDOW_POS'] = f"{x},{y}"

            flags = pygame.NOFRAME | pygame.DOUBLEBUF
            screen = pygame.display.set_mode((w, h), flags)

            try:
                hwnd = pygame.display.get_wm_info().get('window')
                if hwnd:
                    user32.SetWindowPos(hwnd, HWND_TOP, x, y, w, h, SWP_SHOWWINDOW)
            except Exception:
                pass

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
            screen = pygame.display.set_mode((w, h), flags)

            try:
                hwnd = pygame.display.get_wm_info().get('window')
                if hwnd:
                    user32.SetWindowPos(hwnd, HWND_TOP, x, y, w, h, SWP_SHOWWINDOW)
            except Exception:
                pass

            return screen, w, h, False
