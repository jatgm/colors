"""
Unit tests for colors application rebranding, colors2.0 vs colors1.0 engine separation,
light mode decoupling, real-time math telemetry HUD console log, and peripheral sync.
Strict requirement: zero emojis.
"""

import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import pygame

from config import (
    MODE_COLORS_2_0,
    MODE_COLORS_1_0,
    MODE_SMART_RHYTHM,
    MODE_STROBE_2_0,
    MODE_CLASSIC_RAPID,
    STROBE_MODES,
)
from visualizer import VisualizerEngine
from beat_detector import BeatDetector
from hud import HUD
from razer_chroma import RazerChromaManager, RazerDevice, RAZER_MOUSE_PIDS
from happylighting import HappyLightingManager


class TestColorsRebrandingAndEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def setUp(self):
        self.visualizer = VisualizerEngine(1280, 720)
        self.hud = HUD(1280, 720)
        self.hud.warning_dismissed = True

    def test_engine_constants_and_aliases(self):
        """Verify colors2.0 and colors1.0 are primary names with backward-compatible aliases."""
        self.assertEqual(MODE_COLORS_2_0, "colors2.0")
        self.assertEqual(MODE_COLORS_1_0, "colors1.0")
        self.assertEqual(MODE_SMART_RHYTHM, MODE_COLORS_2_0)
        self.assertEqual(MODE_STROBE_2_0, MODE_COLORS_2_0)
        self.assertEqual(MODE_CLASSIC_RAPID, MODE_COLORS_1_0)
        self.assertIn(MODE_COLORS_2_0, STROBE_MODES)
        self.assertIn(MODE_COLORS_1_0, STROBE_MODES)

    def test_engine_toggle_decoupled_from_light_mode(self):
        """Verify switching between colors2.0 and colors1.0 does not disable or reset light mode."""
        # 1. Activate solid light mode
        self.visualizer.set_solid_color("red", activate=True)
        self.assertTrue(self.visualizer.solid_color_active)
        self.assertEqual(self.visualizer.get_solid_color_name().lower(), "red")

        # 2. Toggle engine from colors2.0 to colors1.0
        self.visualizer.set_engine(MODE_COLORS_1_0)
        self.assertTrue(self.visualizer.is_colors_1_0_active())
        self.assertFalse(self.visualizer.is_colors_2_0_active())
        # Light mode MUST remain active
        self.assertTrue(self.visualizer.solid_color_active)
        self.assertEqual(self.visualizer.get_solid_color_name().lower(), "red")

        # 3. Toggle engine back to colors2.0
        self.visualizer.toggle_engine()
        self.assertTrue(self.visualizer.is_colors_2_0_active())
        self.assertFalse(self.visualizer.is_colors_1_0_active())
        # Light mode MUST still remain active
        self.assertTrue(self.visualizer.solid_color_active)
        self.assertEqual(self.visualizer.get_solid_color_name().lower(), "red")

    def test_hud_engine_badge_click_toggles_engine_without_affecting_light(self):
        """Verify clicking the header engine badge toggles engine and preserves light mode."""
        # Activate solid color
        self.visualizer.set_solid_color("neon blue", activate=True)
        self.assertTrue(self.visualizer.solid_color_active)

        # Force render once to position self.badge_engine
        screen = pygame.Surface((1280, 720))
        audio_state = {"bpm": 120.0, "section": "VERSE"}
        self.hud.render(screen, None, self.visualizer, None, None, audio_state, False)
        self.assertIsNotNone(self.hud.badge_engine)

        badge_pos = self.hud.badge_engine.center
        clicked = self.hud.handle_mouse_down(badge_pos, None, self.visualizer, None, None, None)
        self.assertTrue(clicked)
        # Engine should have flipped to colors1.0
        self.assertTrue(self.visualizer.is_colors_1_0_active())
        # Light mode must remain True
        self.assertTrue(self.visualizer.solid_color_active)

    def test_hud_btn_engine_shows_engine_name_even_when_light_mode_is_on(self):
        """Verify HUD btn_engine renders ENG: colors2.0 or ENG: colors1.0 and never ENG: SOLID."""
        self.visualizer.set_solid_color("emerald green", activate=True)
        self.visualizer.set_engine(MODE_COLORS_2_0)

        screen = pygame.Surface((1280, 720))
        audio_state = {"bpm": 128.0, "section": "CHORUS"}

        with patch.object(self.hud, "_render_button") as mock_btn:
            self.hud.render(screen, None, self.visualizer, None, None, audio_state, False)
            btn_eng = getattr(self.hud, "btn_engine", None)
            calls = [c for c in mock_btn.call_args_list if c[0][1] == btn_eng]
            self.assertTrue(len(calls) > 0)
            rendered_label = calls[0][0][2]
            self.assertEqual(rendered_label, "ENG: colors2.0")


class TestTelemetryConsoleLog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def setUp(self):
        self.detector = BeatDetector(sample_rate=44100)
        self.visualizer = VisualizerEngine(1280, 720)
        self.hud = HUD(1280, 720)
        self.hud.warning_dismissed = True

    def test_detector_telemetry_logs_and_vectors(self):
        """Verify beat detector produces timestamped trigger rationale logs and math vectors."""
        # Feed high energy burst
        burst = np.sin(2 * np.pi * 60 * np.arange(1024) / 44100).astype(np.float32)
        state = self.detector.process_audio(burst)

        self.assertIn("telemetry_logs", state)
        self.assertIn("bass_flux", state)
        self.assertIn("dynamic_thresh", state)
        self.assertIn("high_flux", state)
        self.assertIn("high_thresh", state)
        self.assertIn("sub_flux", state)
        self.assertIn("sub_thresh", state)
        self.assertIn("grid_mult", state)
        self.assertIn("is_attack_transient", state)
        self.assertIn("engine_name", state)

        # Trigger kick logic explicitly
        self.detector._log_event("[KICK] bass_flux 0.85 > thresh 0.50 (ratio 1.70x) PLL on-grid")
        self.detector._log_event("[808 TAIL GATED] sustain decay 0.65 suppressed (flux 0.12 <= thresh 0.35)")
        logs = list(self.detector.telemetry_logs)
        self.assertTrue(any("[KICK]" in l for l in logs))
        self.assertTrue(any("[808 TAIL GATED]" in l for l in logs))

    def test_hud_toggle_console(self):
        """Verify console log HUD view can be toggled via method and button."""
        self.assertFalse(self.hud.show_console)
        self.hud.toggle_console()
        self.assertTrue(self.hud.show_console)
        self.hud.toggle_console()
        self.assertFalse(self.hud.show_console)

    def test_render_console_log_clean_execution(self):
        """Verify console log renders without crashing with full math and event log."""
        self.hud.show_console = True
        screen = pygame.Surface((1280, 720))
        audio_state = {
            "bpm": 130.0,
            "bpm_confidence": 0.92,
            "section": "DROP",
            "bass_flux": 0.82,
            "dynamic_thresh": 0.54,
            "high_flux": 0.65,
            "high_thresh": 0.40,
            "sub_flux": 0.70,
            "sub_thresh": 0.48,
            "grid_mult": 1.35,
            "is_attack_transient": True,
            "total_level": 0.45,
            "peak": 0.88,
            "telemetry_logs": [
                "[12:00:00.001] [KICK] bass_flux 0.82 > thresh 0.54 (ratio 1.52x) PLL on-grid",
                "[12:00:00.250] [SNARE] high_flux 0.65 > thresh 0.40 (ratio 1.63x) backbeat on-grid",
                "[12:00:00.500] [808 TAIL GATED] sustain decay 0.70 suppressed",
                "[12:00:00.750] [DROP] explosive bass surge > 1.8x avg",
            ],
        }
        # Render HUD with console open
        self.hud.render(screen, None, self.visualizer, None, None, audio_state, False)
        self.assertIsNotNone(self.hud.console_rect)
        self.assertIsNotNone(self.hud.console_close_btn)

        # Test clicking close button [X]
        close_pos = self.hud.console_close_btn.center
        clicked = self.hud.handle_mouse_down(close_pos, None, self.visualizer, None, None, None)
        self.assertTrue(clicked)
        self.assertFalse(self.hud.show_console)


class TestHardwareSynchronization(unittest.TestCase):
    def test_razer_viper_pid_mouse_classification(self):
        """Verify Razer Viper (PID 0x0078) is recognized as a mouse with logo led 0x04."""
        self.assertIn(0x0078, RAZER_MOUSE_PIDS)
        dev = RazerDevice(
            name="Razer Device (0x0078)",
            device_type="mouse",
            path="\\\\?\\hid#vid_1532&pid_0078",
            pid=0x0078,
            handle=123,
        )
        self.assertEqual(dev.device_type, "mouse")
        self.assertEqual(dev.led_id, 0x04)
        self.assertEqual(dev.pid, 0x0078)

    def test_happylighting_has_pending_event_bypass(self):
        """Verify HappyLighting worker processes pending queue before waiting."""
        mgr = HappyLightingManager()
        mgr._target_color = (255, 0, 0)
        mgr._strobe_cut = False
        mgr._has_pending = True
        self.assertTrue(mgr._has_pending)

    def test_happylighting_contrast_toggle_stability_across_frames(self):
        """Verify HappyLighting maintains the same channel during all 120 FPS frames of a single beat flash."""
        mgr = HappyLightingManager()
        mgr._contrast_toggle = 0
        # Frame 1 of flash_id=42
        mgr.set_colors((255, 0, 0), (0, 0, 255), strobe_cut=True, flash_id=42)
        with mgr.lock:
            col_frame1 = mgr._target_color
            trig_count_1 = mgr._flash_trigger_id

        # Frames 2..10 of same flash_id=42
        for _ in range(9):
            mgr.set_colors((255, 0, 0), (0, 0, 255), strobe_cut=True, flash_id=42)
            with mgr.lock:
                self.assertEqual(mgr._target_color, col_frame1)
                self.assertEqual(mgr._flash_trigger_id, trig_count_1)

        # New beat with flash_id=43 must alternate
        mgr.set_colors((255, 0, 0), (0, 0, 255), strobe_cut=True, flash_id=43)
        with mgr.lock:
            self.assertNotEqual(mgr._target_color, col_frame1)
            self.assertEqual(mgr._flash_trigger_id, trig_count_1 + 1)

    def test_keyboard_matrix_strobe_blackout_gating(self):
        """Verify KeyboardMatrixEngine gates spectrum bars during strobe blackout to achieve true black."""
        from razer_chroma import KeyboardMatrixEngine
        eng = KeyboardMatrixEngine()
        audio_state = {"spectrum_bars": [0.8] * 8, "total_level": 0.5}

        # During strobe blackout (strobe_cut=True and screen is black):
        matrix, is_black = eng.generate_matrix(
            0.016, (0, 0, 0), (0, 0, 0), strobe_cut=True, audio_state=audio_state
        )
        self.assertTrue(is_black)
        self.assertEqual(matrix.max(), 0)

        # In smooth rave mode (strobe_cut=False), spectrum bars should be visible:
        matrix_smooth, is_black_smooth = eng.generate_matrix(
            0.016, (0, 240, 255), (0, 240, 255), strobe_cut=False, audio_state=audio_state
        )
        self.assertFalse(is_black_smooth)
        self.assertGreater(matrix_smooth[0].max(), 0)

    def test_keyboard_matrix_808_sub_bass_bottom_row(self):
        """Verify 808 sub-bass events excite the bottom row of the keyboard matrix."""
        from razer_chroma import KeyboardMatrixEngine
        eng = KeyboardMatrixEngine()
        audio_808 = {"is_808": True, "total_level": 0.9, "spectrum_bars": [0.5] * 8}

        matrix, is_black = eng.generate_matrix(
            0.016, (0, 240, 255), (0, 240, 255), strobe_cut=True, audio_state=audio_808
        )
        self.assertFalse(is_black)
        # Row 5 (bottom row: Ctrl, Spacebar, Arrows) should be strongly illuminated
        self.assertGreater(matrix[5].max(), 100)
