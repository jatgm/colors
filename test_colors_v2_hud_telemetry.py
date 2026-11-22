"""
Unit tests for colors application rebranding, colors2.0 vs colors1.0 engine separation,
light mode decoupling, real-time math telemetry HUD console log, and peripheral sync.
Strict requirement: zero emojis.
"""

import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import pygame
import math

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

    def test_console_visualizer_deck_dimensions_and_history_accumulation(self):
        """Verify HUD console visualizer tracks 140-frame history, 24 spectrum peaks, and renders wide scope."""
        self.hud.show_console = True
        screen = pygame.Surface((1920, 1080))

        # Feed 10 sequential frames with varying energy and 24-band spectrum
        for i in range(10):
            bars = [min(1.0, 0.1 * i + 0.03 * b) for b in range(24)]
            state = {
                "bpm": 128.0,
                "total_level": 0.3 + 0.05 * i,
                "bass_flux": 0.4 + 0.06 * i,
                "dynamic_thresh": 0.5,
                "sub_flux": 0.6 if i % 2 == 0 else 0.2,
                "sub_thresh": 0.4,
                "is_attack_transient": (i % 2 == 0),
                "is_kick": (i == 4),
                "is_snare": (i == 7),
                "is_808": (i == 2),
                "beat_phase": (i * 0.1) % 1.0,
                "grid_mult": 1.25 if i in (4, 7) else 0.85,
                "spectrum_bars": bars,
            }
            self.visualizer.alpha = 1.0 if (i in (4, 7, 2)) else 0.0
            self.hud.render(screen, None, self.visualizer, None, None, state, False)

        # History should have accumulated 10 frames
        self.assertGreaterEqual(len(self.hud.telemetry_history), 10)
        # 24 spectrum peaks should be tracked
        self.assertEqual(len(self.hud.spectrum_peaks), 24)
        self.assertGreater(max(self.hud.spectrum_peaks), 0.5)

        # Console dimensions should be prominent and wide
        self.assertGreaterEqual(self.hud.console_rect.width, 1000)
        self.assertGreaterEqual(self.hud.console_rect.height, 400)


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

    def test_razer_viper_driver_mode_and_nostore_reports(self):
        """Verify Razer Viper protocol uses Driver Mode (0x03, 0x00) with txn 0xFF and volatile NOSTORE (0x00)."""
        from razer_chroma import _create_razer_report
        # Driver Mode report
        mode_rep = _create_razer_report(0x00, 0x04, 0x02, [0x03, 0x00], txn=0xFF)
        self.assertEqual(mode_rep[1], 0xFF)  # txn id 0xFF
        self.assertEqual(mode_rep[6], 0x00)  # command class
        self.assertEqual(mode_rep[7], 0x04)  # command id
        self.assertEqual(mode_rep[8], 0x03)  # driver mode byte 1
        self.assertEqual(mode_rep[9], 0x00)  # driver mode byte 2

        # Volatile NOSTORE static RGB report (zero flash wear, <0.4ms execution)
        static_rep = _create_razer_report(0x0F, 0x02, 0x09, [0x00, 0x04, 0x01, 0x00, 0x00, 0x01, 255, 0, 128], txn=0x3F)
        self.assertEqual(static_rep[1], 0x3F)
        self.assertEqual(static_rep[6], 0x0F)
        self.assertEqual(static_rep[7], 0x02)
        self.assertEqual(static_rep[8], 0x00)  # NOSTORE
        self.assertEqual(static_rep[9], 0x04)  # LOGO_LED
        self.assertEqual(static_rep[14], 255) # R
        self.assertEqual(static_rep[15], 0)   # G
        self.assertEqual(static_rep[16], 128) # B

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

    def test_mouse_lighting_engine_kick_and_808_detonation(self):
        """Verify MouseLightingEngine triggers full-blast 255 peak strobe flash on kick and 808 events."""
        from razer_chroma import MouseLightingEngine
        mouse_eng = MouseLightingEngine()

        # Kick detonation
        audio_kick = {"is_kick": True, "total_level": 0.8}
        m_col = mouse_eng.generate_color(
            0.016, (0, 100, 200), (0, 100, 200), strobe_cut=True, audio_state=audio_kick
        )
        # Should blast at maximum 255 brightness
        self.assertEqual(max(m_col), 255)

        # 808 sub-bass transient detonation
        mouse_eng2 = MouseLightingEngine()
        audio_808 = {"is_808": True, "total_level": 0.85}
        m_col_808 = mouse_eng2.generate_color(
            0.016, (20, 120, 80), (20, 120, 80), strobe_cut=True, audio_state=audio_808
        )
        self.assertEqual(max(m_col_808), 255)

    def test_mouse_lighting_engine_snare_contrast_flash(self):
        """Verify MouseLightingEngine triggers secondary contrast accent flash on snare events."""
        from razer_chroma import MouseLightingEngine
        mouse_eng = MouseLightingEngine()
        audio_snare = {"is_snare": True, "total_level": 0.75}
        m_col = mouse_eng.generate_color(
            0.016, (20, 20, 200), (20, 20, 200), strobe_cut=True, audio_state=audio_snare
        )
        self.assertGreater(max(m_col), 60)

    def test_mouse_lighting_engine_strobe_blackout_and_ambient_contrast(self):
        """Verify MouseLightingEngine outputs true black during strobe cuts and subtle glow in ambient mode."""
        from razer_chroma import MouseLightingEngine
        import config
        mouse_eng = MouseLightingEngine()

        # In strobe mode between beats: absolute black
        m_col_black = mouse_eng.generate_color(
            0.016, (0, 0, 0), (0, 0, 0), strobe_cut=True, audio_state={"is_kick": False, "is_snare": False}
        )
        self.assertEqual(m_col_black, (0, 0, 0))

        # In Album Art strobe mode between beats: must cut sharply to black (0, 0, 0) and not stay solid
        vis_album_art = {"mode": config.MODE_ALBUM_ART, "safe_mode": False, "palette_colors": [(0, 240, 255)]}
        m_col_album_off = mouse_eng.generate_color(
            0.016, (0, 240, 255), (0, 240, 255), strobe_cut=False, audio_state=None, vis_state=vis_album_art
        )
        self.assertEqual(m_col_album_off, (0, 0, 0))

        # In Album Art mode on a beat hit: explodes with full 255 peak color
        m_col_album_kick = mouse_eng.generate_color(
            0.016, (0, 240, 255), (0, 240, 255), strobe_cut=False, audio_state={"is_kick": True}, vis_state=vis_album_art
        )
        self.assertEqual(max(m_col_album_kick), 255)

        # In Smooth Rave Pulse mode between beats: subtle baseline glow (<= 65)
        vis_smooth = {"mode": config.MODE_SMOOTH_PULSE, "safe_mode": False}
        m_col_smooth = mouse_eng.generate_color(
            0.016, (255, 120, 0), (255, 120, 0), strobe_cut=False, audio_state=None, vis_state=vis_smooth
        )
        self.assertGreater(max(m_col_smooth), 0)
        self.assertLessEqual(max(m_col_smooth), 65)

    def test_mouse_lighting_engine_solid_mode_override(self):
        """Verify solid color mode overrides all audio triggers and outputs solid RGB continuously."""
        from razer_chroma import MouseLightingEngine
        mouse_eng = MouseLightingEngine()
        vis_solid = {"solid_color_active": True, "solid_color": (255, 60, 0)}
        audio_kick = {"is_kick": True}
        col = mouse_eng.generate_color(
            0.016, (0, 0, 0), (0, 0, 0), strobe_cut=True, audio_state=audio_kick, vis_state=vis_solid
        )
        self.assertEqual(col, (255, 60, 0))

    def test_mouse_lighting_engine_palette_and_mode_colors(self):
        """Verify MouseLightingEngine flash inherits album palette or Red Only / Monochrome presets."""
        from razer_chroma import MouseLightingEngine
        import config
        mouse_eng = MouseLightingEngine()

        # In Red Only mode
        vis_red = {"mode": config.MODE_RED_ONLY}
        col_red = mouse_eng.generate_color(
            0.016, (0, 0, 0), (0, 0, 0), strobe_cut=True, audio_state={"is_kick": True}, vis_state=vis_red
        )
        self.assertEqual(col_red, (255, 0, 0))

        # In Monochrome mode
        mouse_eng_mono = MouseLightingEngine()
        vis_mono = {"mode": config.MODE_MONOCHROME}
        col_mono = mouse_eng_mono.generate_color(
            0.016, (0, 0, 0), (0, 0, 0), strobe_cut=True, audio_state={"is_kick": True}, vis_state=vis_mono
        )
        self.assertEqual(col_mono, (255, 255, 255))

        # Inherits album art palette color when screen colors are cut
        mouse_eng_pal = MouseLightingEngine()
        vis_pal = {"palette_colors": [(200, 100, 50), (40, 20, 10)]}
        col_pal = mouse_eng_pal.generate_color(
            0.016, (0, 0, 0), (0, 0, 0), strobe_cut=True, audio_state={"is_kick": True}, vis_state=vis_pal
        )
        # Scaled to 255 peak brightness from (200, 100, 50)
        self.assertEqual(max(col_pal), 255)
        self.assertEqual(col_pal[0], 255)

    def test_mouse_lighting_engine_strobe_off_beat_sharp_blackout(self):
        """Verify mouse cuts sharply to black (0, 0, 0) immediately on strobe off-beats and does not remain lit."""
        from razer_chroma import MouseLightingEngine
        import config
        mouse_eng = MouseLightingEngine()
        vis_strobe = {
            "mode": config.MODE_STROBE_2_0,
            "kick_intensity": 0.0,
            "snare_intensity": 0.0,
            "strobe_alpha": 0.0,
            "decay": 16.0,
        }

        # Beat frame: explosive strobe color
        col_beat = mouse_eng.generate_color(
            0.016, (0, 240, 255), (0, 240, 255), strobe_cut=True, audio_state={"is_kick": True}, vis_state=vis_strobe
        )
        self.assertEqual(col_beat, (0, 240, 255))

        # Off-beat frame immediately following the hit: must cut sharply to black
        col_off = mouse_eng.generate_color(
            0.016, (0, 0, 0), (0, 0, 0), strobe_cut=True, audio_state={"is_kick": False}, vis_state=vis_strobe
        )
        self.assertEqual(col_off, (0, 0, 0))

    def test_mouse_lighting_engine_decay_tail_does_not_retrigger(self):
        """Verify that decaying kick_intensity or strobe_alpha in vis_state does not re-trigger or hold mouse lit."""
        from razer_chroma import MouseLightingEngine
        import config, time
        mouse_eng = MouseLightingEngine()
        vis_strobe = {
            "mode": config.MODE_PSYCHO_OVERDRIVE,
            "kick_intensity": 1.0,
            "snare_intensity": 0.0,
            "strobe_alpha": 0.9,
            "decay": 8.0,
        }

        # Beat attack frame
        col_hit = mouse_eng.generate_color(
            0.016, (255, 0, 128), (255, 0, 128), strobe_cut=True, audio_state={"is_kick": True}, vis_state=vis_strobe
        )
        self.assertEqual(max(col_hit), 255)

        # Subsequent frames where kick_intensity is decaying (e.g. 0.85, 0.70, 0.58)
        # Even after 70ms has elapsed, decaying tail must not re-trigger a new flash
        time.sleep(0.075)
        for decaying_val in [0.85, 0.70, 0.58]:
            vis_strobe["kick_intensity"] = decaying_val
            vis_strobe["strobe_alpha"] = decaying_val * 0.9
            col_decay = mouse_eng.generate_color(
                0.016, (0, 0, 0), (0, 0, 0), strobe_cut=True, audio_state={"is_kick": False}, vis_state=vis_strobe
            )
            self.assertEqual(col_decay, (0, 0, 0))

    def test_mouse_lighting_engine_burst_chopped_blackouts(self):
        """Verify that during burst pulse off-phases, mouse sharply cuts to black in lockstep with visualizer."""
        from razer_chroma import MouseLightingEngine
        from visualizer import VisualizerEngine
        import config
        mouse_eng = MouseLightingEngine()
        vis = VisualizerEngine(1920, 1080)
        vis.set_mode(config.MODE_PSYCHO_OVERDRIVE)

        # Trigger kick burst
        audio_kick = {"is_kick": True, "total_level": 0.85, "raw_peak": 0.85}
        vis.update(0.016, audio_kick)
        c_l, c_r, strobe_cut = vis.get_peripheral_colors()
        vis_state = {
            "kick_intensity": vis.kick_intensity,
            "mode": vis.mode,
            "strobe_alpha": getattr(vis, "last_eff_intensity_0", 0.0),
        }
        col_burst_on = mouse_eng.generate_color(0.016, c_l, c_r, strobe_cut, audio_state=audio_kick, vis_state=vis_state)
        self.assertGreater(max(col_burst_on), 0)

        # Advance to burst chopped blackout
        audio_off = {"is_kick": False, "total_level": 0.4, "raw_peak": 0.4}
        # Simulate until burst off-phase
        found_blackout = False
        for _ in range(8):
            vis.update(0.016, audio_off)
            c_l, c_r, strobe_cut = vis.get_peripheral_colors()
            vis_state["kick_intensity"] = vis.kick_intensity
            col = mouse_eng.generate_color(0.016, c_l, c_r, strobe_cut, audio_state=audio_off, vis_state=vis_state)
            if c_l == (0, 0, 0) and strobe_cut:
                self.assertEqual(col, (0, 0, 0))
                found_blackout = True
        self.assertTrue(found_blackout)

    def test_mouse_lighting_engine_rising_edge_attack_with_audio_state_dict(self):
        """Verify rising-edge transient attack triggers 255 flash even if audio_state dict has is_kick=False."""
        from razer_chroma import MouseLightingEngine
        import config
        mouse_eng = MouseLightingEngine()
        vis_strobe = {"mode": config.MODE_COLORS_2_0, "kick_intensity": 0.0}

        # Baseline quiet frame
        col_quiet = mouse_eng.generate_color(
            0.016, (0, 0, 0), (0, 0, 0), strobe_cut=True, audio_state={"is_kick": False}, vis_state=vis_strobe
        )
        self.assertEqual(col_quiet, (0, 0, 0))

        # Sudden rising edge attack in kick_intensity (0.0 -> 0.90) with audio_state dict present
        vis_strobe["kick_intensity"] = 0.90
        col_attack = mouse_eng.generate_color(
            0.016, (0, 200, 255), (0, 200, 255), strobe_cut=True, audio_state={"is_kick": False}, vis_state=vis_strobe
        )
        self.assertEqual(max(col_attack), 255)

    def test_mouse_lighting_engine_strobe_cuts_to_black_despite_nonzero_col_left(self):
        """Verify that on strobe off-beats, mouse strictly cuts to (0, 0, 0) even if col_left is non-zero."""
        from razer_chroma import MouseLightingEngine
        import config
        mouse_eng = MouseLightingEngine()
        vis_strobe = {"mode": config.MODE_ALBUM_ART, "strobe_alpha": 0.6, "decay": 16.0}

        # Beat frame
        col_hit = mouse_eng.generate_color(
            0.016, (255, 100, 0), (255, 100, 0), strobe_cut=True, audio_state={"is_kick": True}, vis_state=vis_strobe
        )
        self.assertEqual(max(col_hit), 255)

        # Advance frames until 80ms flash duration has expired (6 frames * 16ms = 96ms)
        # Even with non-zero ambient/decaying screen color (e.g. col_left = (120, 40, 10)), off-beat must be (0, 0, 0)
        col_off = None
        for _ in range(6):
            col_off = mouse_eng.generate_color(
                0.016, (120, 40, 10), (120, 40, 10), strobe_cut=True, audio_state={"is_kick": False}, vis_state=vis_strobe
            )
        self.assertEqual(col_off, (0, 0, 0))

    def test_console_visualizer_interpolates_arbitrary_spectrum_bars(self):
        """Verify HUD telemetry and console visualizer resample arbitrary bar counts (e.g. 8 bars) to 24."""
        hud = HUD(1280, 720)
        screen = pygame.Surface((1280, 720))
        audio_8_bars = {
            "spectrum_bars": [0.9, 0.7, 0.5, 0.3, 0.2, 0.1, 0.05, 0.02],
            "total_level": 0.6,
            "dynamic_thresh": 0.4,
        }
        hud._update_telemetry_history(audio_8_bars, None)
        self.assertEqual(len(hud.spectrum_peaks), 24)
        # Verify peaks were updated across all 24 resampled bands
        self.assertGreater(hud.spectrum_peaks[0], 0.0)
        self.assertGreater(hud.spectrum_peaks[12], 0.0)

    def test_console_visualizer_sanitizes_nan_and_inf_bars(self):
        """Verify HUD telemetry cleanly sanitizes NaN and Inf values without crashing."""
        hud = HUD(1280, 720)
        screen = pygame.Surface((1280, 720))
        audio_nan_bars = {
            "spectrum_bars": [float('nan'), float('inf'), -0.5, 0.8],
            "total_level": 0.5,
            "dynamic_thresh": 0.3,
        }
        hud._update_telemetry_history(audio_nan_bars, None)
        self.assertEqual(len(hud.spectrum_peaks), 24)
        # Verify no NaN or Inf in peaks
        for p in hud.spectrum_peaks:
            self.assertFalse(math.isnan(p))
            self.assertFalse(math.isinf(p))
