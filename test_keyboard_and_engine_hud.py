"""
Unit tests for Razer Chroma Keyboard Matrix RGB Engine and HUD Engine Status Badge.
STRICT REQUIREMENT: Zero emojis. Pure high-tech telemetry.
"""

import unittest
import numpy as np
import pygame
from config import (
    MODE_STROBE_2_0,
    MODE_CLASSIC_RAPID,
    MODE_PSYCHO_OVERDRIVE,
    SOLID_COLORS,
)
from visualizer import VisualizerEngine
from hud import HUD
from razer_chroma import KeyboardMatrixEngine, RazerChromaManager


class TestEngineIndicatorHUD(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def setUp(self):
        self.hud = HUD(1280, 720)
        self.hud.warning_dismissed = True
        self.vis = VisualizerEngine(1280, 720)

    def test_btn_engine_exists_and_aliases_btn_mode_2_0(self):
        """Verify btn_engine exists and btn_mode_2_0 points to the same hitbox for backward compatibility."""
        self.assertTrue(hasattr(self.hud, "btn_engine"))
        self.assertTrue(hasattr(self.hud, "btn_mode_2_0"))
        self.assertEqual(self.hud.btn_engine, self.hud.btn_mode_2_0)

    def test_clicking_btn_engine_toggles_smart_and_classic(self):
        """Verify clicking the engine badge toggles between Smart PLL and Classic Raw engines."""
        self.assertTrue(self.vis.is_smart_mode_active())
        self.assertFalse(self.vis.is_classic_rapid_active())

        # Click to toggle into Classic Raw engine
        click_pos = (self.hud.btn_engine.centerx, self.hud.btn_engine.centery)
        consumed = self.hud.handle_mouse_down(click_pos, None, self.vis, None, None, lambda: None)
        self.assertTrue(consumed)
        self.assertTrue(self.vis.is_classic_rapid_active())

        # Click again to toggle back into Smart PLL engine
        consumed2 = self.hud.handle_mouse_down(click_pos, None, self.vis, None, None, lambda: None)
        self.assertTrue(consumed2)
        self.assertTrue(self.vis.is_smart_mode_active())

    def test_engine_badge_rendering_states(self):
        """Verify HUD renders cleanly across all engine states: Smart PLL, Classic Raw, Overdrive, Solid."""
        surf = pygame.Surface((1280, 720))
        dummy_audio = {"bpm": 128.0, "total_level": 0.5, "bass_level": 0.6, "mid_level": 0.4, "high_level": 0.3}

        # 1. Smart PLL engine state
        self.vis.set_mode(MODE_STROBE_2_0)
        self.vis.overdrive_mode = False
        self.hud.render(surf, None, self.vis, None, None, dummy_audio, False)

        # 2. Classic Raw engine state
        self.vis.set_mode(MODE_CLASSIC_RAPID)
        self.hud.render(surf, None, self.vis, None, None, dummy_audio, False)

        # 3. Overdrive engine state
        self.vis.overdrive_mode = True
        self.hud.render(surf, None, self.vis, None, None, dummy_audio, False)

        # 4. Solid Color state
        self.vis.set_solid_color(0, activate=True)
        self.hud.render(surf, None, self.vis, None, None, dummy_audio, False)
        self.assertTrue(True)


class TestKeyboardMatrixEngine(unittest.TestCase):
    def setUp(self):
        self.engine = KeyboardMatrixEngine()

    def test_dimensions_and_initial_blackout(self):
        """Verify matrix dimensions are exactly 6 rows by 22 columns with initial blackout."""
        self.assertEqual(self.engine.ROWS, 6)
        self.assertEqual(self.engine.COLS, 22)
        matrix, is_blackout = self.engine.generate_matrix(0.016, (0, 0, 0), (0, 0, 0), strobe_cut=True)
        self.assertEqual(matrix.shape, (6, 22, 3))
        self.assertTrue(is_blackout)
        self.assertTrue(np.all(matrix == 0))

    def test_spectrum_row_mapping(self):
        """Verify Row 0 (Function Keys) maps frequency spectrum bars across 22 columns."""
        audio_state = {
            "spectrum_bars": [1.0, 0.8, 0.6, 0.4, 0.2, 0.1, 0.05, 0.0],
            "total_level": 0.6,
        }
        matrix, is_blackout = self.engine.generate_matrix(
            0.016, (0, 240, 255), (255, 60, 200), strobe_cut=False, audio_state=audio_state
        )
        self.assertFalse(is_blackout)
        # Function row should be illuminated across columns with audio energy
        self.assertGreater(matrix[0, 0].max(), 0)
        self.assertGreater(matrix[0, 2].max(), 0)

    def test_kick_shockwave_propagation_from_spacebar(self):
        """Verify kick event spawns radial shockwave originating from spacebar (row 5, col 8)."""
        audio_kick = {
            "is_kick": True,
            "is_snare": False,
            "is_hihat": False,
            "total_level": 0.8,
            "spectrum_bars": [0.8] * 8,
        }
        # Frame 1: Kick initiates shockwave
        matrix, is_blackout = self.engine.generate_matrix(
            0.016, (0, 240, 255), (0, 240, 255), strobe_cut=True, audio_state=audio_kick
        )
        self.assertFalse(is_blackout)
        self.assertEqual(len(self.engine.shockwaves), 1)
        self.assertGreater(self.engine.shockwaves[0]["radius"], 0.0)

        # Advance 5 frames (approx 80ms)
        for _ in range(5):
            matrix, _ = self.engine.generate_matrix(
                0.016, (0, 0, 0), (0, 0, 0), strobe_cut=True, audio_state={"spectrum_bars": []}
            )

        # Shockwave has expanded outwards across matrix rows
        self.assertGreater(self.engine.shockwaves[0]["radius"], 2.0)
        # Verify keys along the wavefront are illuminated
        self.assertGreater(matrix.max(), 0)

    def test_snare_lateral_wave_across_typing_rows(self):
        """Verify snare event triggers lateral wave across rows 2, 3, 4."""
        audio_snare = {
            "is_kick": False,
            "is_snare": True,
            "is_hihat": False,
            "total_level": 0.7,
            "spectrum_bars": [0.5] * 8,
        }
        matrix, is_blackout = self.engine.generate_matrix(
            0.016, (0, 240, 255), (255, 60, 200), strobe_cut=True, audio_state=audio_snare
        )
        self.assertFalse(is_blackout)
        self.assertGreater(self.engine.snare_intensity, 0.0)

        # Advance 2 frames
        matrix, _ = self.engine.generate_matrix(
            0.016, (0, 0, 0), (0, 0, 0), strobe_cut=True, audio_state={"spectrum_bars": []}
        )
        # Typing rows (2..4) should have active lateral burst illumination
        typing_slice = matrix[2:5, :]
        self.assertGreater(typing_slice.max(), 0)

    def test_hihat_micro_sparkles(self):
        """Verify hi-hat hits trigger micro-sparkles across keycaps."""
        audio_hihat = {
            "is_kick": False,
            "is_snare": False,
            "is_hihat": True,
            "total_level": 0.5,
            "spectrum_bars": [0.3] * 8,
        }
        matrix, is_blackout = self.engine.generate_matrix(
            0.016, (0, 240, 255), (255, 60, 200), strobe_cut=True, audio_state=audio_hihat
        )
        self.assertFalse(is_blackout)
        self.assertGreater(len(self.engine.sparkles), 0)

    def test_spatial_stereo_spread_dual_monitors(self):
        """Verify left monitor maps to cols 0-9 and right monitor maps to cols 12-21 in dual mode."""
        col_left = (255, 0, 0)    # Pure Red Left Monitor
        col_right = (0, 0, 255)   # Pure Blue Right Monitor
        matrix, _ = self.engine.generate_matrix(
            0.016, col_left, col_right, strobe_cut=False, is_dual=True, audio_state={"spectrum_bars": []}
        )
        # Col 0..4 on Row 3 should be Red
        self.assertEqual(tuple(matrix[3, 2]), col_left)
        # Col 15..20 on Row 3 should be Blue
        self.assertEqual(tuple(matrix[3, 18]), col_right)

    def test_solid_color_mode_full_matrix(self):
        """Verify solid color override lights up all 6x22 keys continuously without strobe blackout."""
        vis_state = {
            "solid_color_active": True,
            "solid_color": (0, 255, 128),
        }
        matrix, is_blackout = self.engine.generate_matrix(
            0.016, (0, 0, 0), (0, 0, 0), strobe_cut=True, vis_state=vis_state
        )
        self.assertFalse(is_blackout)
        self.assertTrue(np.all(matrix == (0, 255, 128)))


class TestRazerManagerIntegration(unittest.TestCase):
    def setUp(self):
        self.mgr = RazerChromaManager()

    def tearDown(self):
        self.mgr.stop()

    def test_set_colors_backward_compatible_signature(self):
        """Verify set_colors can be called with legacy 2-arg, 3-arg, or full kwargs signatures."""
        self.mgr.set_colors((255, 0, 0), (255, 0, 0))
        self.mgr.set_colors((0, 255, 0), (0, 255, 0), strobe_cut=False)
        self.mgr.set_colors(
            (0, 0, 255), (0, 0, 255), strobe_cut=True,
            audio_state={"is_kick": True, "spectrum_bars": [0.5] * 8},
            is_dual=False, visualizer=None
        )
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
