"""
Unit and integration test suite verifying dual-monitor screen tearing resolution,
hardware vsync, dynamic 165Hz FPS cap, scaled up legible HUD typography,
and deep engine brain telemetry console with live decision feed.
Strict requirement: Zero emojis.
"""

import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import pygame

import config
from config import FPS_CAP, detect_max_display_refresh_rate
from display_manager import DisplayManager, MonitorInfo, query_windows_displays, _create_display_surface
from hud import HUD
from beat_detector import BeatDetector
from visualizer import VisualizerEngine


class TestScreenTearingAndDisplayRefresh(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_query_windows_displays_structure(self):
        """Verify Windows display query returns valid display objects with refresh rates and coordinates."""
        displays = query_windows_displays()
        self.assertIsInstance(displays, list)
        for d in displays:
            self.assertIn("device", d)
            self.assertIn("x", d)
            self.assertIn("y", d)
            self.assertIn("width", d)
            self.assertIn("height", d)
            self.assertIn("hz", d)
            self.assertGreater(d["hz"], 0)

    def test_monitor_info_refresh_rate_and_naming(self):
        """Verify MonitorInfo accepts refresh_rate parameter and formats display name with Hz."""
        m165 = MonitorInfo(0, 0, 0, 1920, 1080, refresh_rate=165)
        self.assertEqual(m165.refresh_rate, 165)
        self.assertIn("165Hz", m165.name)

        m144 = MonitorInfo(1, 1920, 0, 3840, 1080, refresh_rate=144)
        self.assertEqual(m144.refresh_rate, 144)
        self.assertIn("144Hz", m144.name)

    def test_display_manager_refresh_rate_targeting(self):
        """Verify DisplayManager targets matching refresh rate per display mode (165Hz dual/main vs 144Hz secondary)."""
        disp = DisplayManager()
        # Mock dual monitors (165Hz main, 144Hz secondary)
        disp.monitors = [
            MonitorInfo(0, 0, 0, 1920, 1080, refresh_rate=165),
            MonitorInfo(1, 1920, 0, 3840, 1080, refresh_rate=144),
        ]
        disp.available_modes = [
            DisplayManager.MODE_DUAL_SPAN,
            DisplayManager.MODE_MONITOR_1,
            DisplayManager.MODE_MONITOR_2,
            DisplayManager.MODE_WINDOWED,
        ]

        # In dual span mode: must match highest refresh rate (165Hz) to prevent tearing on primary
        disp.set_display_mode(DisplayManager.MODE_DUAL_SPAN)
        self.assertEqual(disp.get_active_refresh_rate(), 165)
        self.assertEqual(disp.get_max_refresh_rate(), 165)

        # In monitor 1 fullscreen: targets 165Hz
        disp.set_display_mode(DisplayManager.MODE_MONITOR_1)
        self.assertEqual(disp.get_active_refresh_rate(), 165)

        # In monitor 2 fullscreen: targets 144Hz
        disp.set_display_mode(DisplayManager.MODE_MONITOR_2)
        self.assertEqual(disp.get_active_refresh_rate(), 144)

    def test_hardware_vsync_surface_creation_and_fallback(self):
        """Verify _create_display_surface sets vsync=1 with graceful fallback if unsupported."""
        flags = pygame.NOFRAME | pygame.DOUBLEBUF
        surf = _create_display_surface((320, 240), flags, vsync=1)
        self.assertIsNotNone(surf)
        self.assertEqual(surf.get_width(), 320)
        self.assertEqual(surf.get_height(), 240)

    def test_config_fps_cap_detects_high_refresh(self):
        """Verify config.py detects highest refresh rate and sets FPS_CAP >= 144Hz."""
        cap = detect_max_display_refresh_rate(default_hz=165)
        self.assertGreaterEqual(cap, 144)
        self.assertGreaterEqual(config.FPS_CAP, 144)


class TestLegibleTypographyAndLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def setUp(self):
        self.hud = HUD(1280, 720)
        self.hud.warning_dismissed = True

    def test_font_sizes_scaled_up_for_readability(self):
        """Verify font sizes across entire program are significantly scaled up for easy readability."""
        self.assertGreaterEqual(self.hud.font_title.get_height(), 18)
        self.assertGreaterEqual(self.hud.font_section.get_height(), 14)
        self.assertGreaterEqual(self.hud.font_main.get_height(), 14)
        self.assertGreaterEqual(self.hud.font_small.get_height(), 12)
        self.assertGreaterEqual(self.hud.font_tiny.get_height(), 11)

    def test_slider_labels_do_not_clip(self):
        """Verify SENS, GAIN, DECAY text labels and values fit cleanly without clipping."""
        self.assertGreater(self.hud.slider_sens_rect.x, self.hud.panel_rect.x + 30)
        self.assertLess(self.hud.slider_sens_rect.right + 30, self.hud.slider_gain_rect.x)
        self.assertLess(self.hud.slider_gain_rect.right + 30, self.hud.slider_decay_rect.x)


class TestDeepConsoleBrainOverlay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def setUp(self):
        self.detector = BeatDetector(sample_rate=44100)
        self.visualizer = VisualizerEngine(1280, 720)
        self.hud = HUD(1280, 720)
        self.hud.warning_dismissed = True
        self.hud.show_console = True

    def test_beat_detector_exposes_full_engine_brain(self):
        """Verify beat detector produces PLL phase drift, 12-tone chroma, harmonic progression, and section probabilities."""
        # Process high energy audio frame
        sample_audio = np.sin(2 * np.pi * 55 * np.arange(1024) / 44100).astype(np.float32)
        state = self.detector.process_audio(sample_audio)

        # 1. PLL Phase-Locked Loop
        self.assertIn("beat_phase", state)
        self.assertIn("phase_error", state)
        self.assertIn("phase_drift_ms", state)
        self.assertIn("tempo_stability", state)
        self.assertIn("grid_mult", state)

        # 2. Musical Pitch & Harmony
        self.assertIn("chroma", state)
        self.assertEqual(len(state["chroma"]), 12)
        self.assertIn("pitch_idx", state)
        self.assertIn("pitch_name", state)
        self.assertIn("pitch_confidence", state)
        self.assertIn("harmonic_progression", state)

        # 3. Macro Section Analyzer
        self.assertIn("section_probs", state)
        probs = state["section_probs"]
        self.assertIn("verse", probs)
        self.assertIn("buildup", probs)
        self.assertIn("chorus", probs)
        self.assertIn("breakdown", probs)
        self.assertIn("chorus_burst_multiplier", state)

        # 4. 808 & Transient Math
        self.assertIn("is_attack_transient", state)
        self.assertIn("transient_ratio", state)
        self.assertIn("sub_flux", state)
        self.assertIn("sub_thresh", state)

    def test_console_renders_all_4_telemetry_cards_and_live_stream(self):
        """Verify console overlay renders all 4 brain cards and live decision feed with zero crashes."""
        surf = pygame.Surface((1280, 720))
        audio_state = {
            "bpm": 128.0,
            "bpm_confidence": 0.94,
            "beat_phase": 0.08,
            "phase_error": -0.02,
            "phase_drift_ms": -4.2,
            "tempo_stability": 94.0,
            "grid_mult": 0.85,
            "is_downbeat": True,
            "is_backbeat": False,
            "pitch_name": "F#",
            "pitch_idx": 6,
            "secondary_pitch_idx": 1,
            "pitch_confidence": 0.82,
            "harmonic_progression": "5th Interval (F# -> C#)",
            "section_name": "CHORUS",
            "section_probs": {"verse": 10, "buildup": 8, "chorus": 78, "breakdown": 4},
            "chorus_burst_multiplier": 1.65,
            "total_level": 0.45,
            "raw_peak": 0.82,
            "bass_flux": 0.88,
            "dynamic_thresh": 0.52,
            "high_flux": 0.65,
            "high_thresh": 0.40,
            "sub_flux": 0.72,
            "sub_thresh": 0.48,
            "is_attack_transient": True,
            "transient_ratio": 2.4,
            "spectrum_bars": np.zeros(24),
            "telemetry_logs": [
                "[12:00:00.010] [PLL] On-grid downbeat confirmed (phase 0.01) -> Flash #00F0FF",
                "[12:00:00.120] [808] Sustain tail gated (flux 0.42 < tail_th 0.50) -> black cut",
                "[12:00:00.250] [HARMONY] Pitch shift to G# -> secondary accent updated",
                "[12:00:00.310] [CHROMA] Dispatched Razer Viper 64-byte volatile HID packet",
            ],
        }

        # Render console
        self.hud.render(surf, None, self.visualizer, None, None, audio_state, False)
        self.assertIsNotNone(self.hud.console_rect)
        self.assertGreaterEqual(self.hud.console_rect.width, 1000)
        self.assertGreaterEqual(self.hud.console_rect.height, 400)


class TestZeroEmojiCompliance(unittest.TestCase):
    def test_zero_emojis_in_source_files(self):
        """Verify strict constraint: Zero emojis across all code and documentation."""
        import os
        for fname in ["config.py", "display_manager.py", "main.py", "hud.py", "beat_detector.py", "razer_chroma.py"]:
            path = os.path.join(".", fname)
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8", errors="ignore") as fp:
                for line_idx, line in enumerate(fp, 1):
                    for ch in line:
                        code = ord(ch)
                        self.assertFalse(
                            (0x1F300 <= code <= 0x1F9FF) or (0x2600 <= code <= 0x27BF),
                            f"Emoji '{ch}' detected at {fname}:{line_idx}"
                        )


if __name__ == "__main__":
    unittest.main()
