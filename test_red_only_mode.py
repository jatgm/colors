"""
Unit tests for Red Only Strobe Mode (MODE_RED_ONLY):
- Mode registration in STROBE_MODES and PALETTES
- VisualizerEngine toggle_red_only() and is_red_only_active()
- Strict red color generation: green and blue channels remain strictly 0
- Peripheral lighting synchronization (col_left, col_right = 255, 0, 0)
- Suppression of white bleaching, snare whitewashing, and hi-hat sparkles into other hues
- Absolute blackout between beats and during silence
"""

import unittest
import pygame
from config import (
    MODE_RED_ONLY,
    MODE_STROBE_2_0,
    MODE_PSYCHO_OVERDRIVE,
    STROBE_MODES,
    PALETTES,
)
from visualizer import VisualizerEngine, DUAL_SCHEME_ALTERNATING, DUAL_SCHEME_SYNCED


class TestRedOnlyMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def setUp(self):
        self.vis = VisualizerEngine(1280, 720)

    def test_mode_registration(self):
        """Verify MODE_RED_ONLY is defined and present in STROBE_MODES."""
        self.assertEqual(MODE_RED_ONLY, "[RED] Red Only")
        self.assertIn(MODE_RED_ONLY, STROBE_MODES)
        self.assertIn("Pure Red", PALETTES)

    def test_toggle_red_only(self):
        """Verify toggling Red Only mode switches to MODE_RED_ONLY and restores previous mode."""
        self.vis.set_mode(MODE_STROBE_2_0)
        self.assertFalse(self.vis.is_red_only_active())

        # Toggle on
        res = self.vis.toggle_red_only()
        self.assertTrue(res)
        self.assertTrue(self.vis.is_red_only_active())
        self.assertEqual(self.vis.mode, MODE_RED_ONLY)
        self.assertEqual(self.vis.current_color, (255, 0, 0))
        self.assertEqual(self.vis.secondary_color, (255, 0, 0))

        # Toggle off
        res_off = self.vis.toggle_red_only()
        self.assertFalse(res_off)
        self.assertFalse(self.vis.is_red_only_active())
        self.assertEqual(self.vis.mode, MODE_STROBE_2_0)

    def test_kick_generates_pure_red(self):
        """Verify trigger_kick sets pure red and peripheral flashes."""
        self.vis.set_mode(MODE_RED_ONLY)
        self.vis.trigger_kick()

        self.assertEqual(self.vis.current_color, (255, 0, 0))
        self.assertEqual(self.vis.secondary_color, (255, 0, 0))
        self.assertEqual(self.vis.peripheral_flash_color_left, (255, 0, 0))
        self.assertEqual(self.vis.peripheral_flash_color_right, (255, 0, 0))

        col_left, col_right, is_strobe = self.vis.get_peripheral_colors()
        self.assertTrue(is_strobe)
        self.assertEqual(col_left, (255, 0, 0))
        self.assertEqual(col_right, (255, 0, 0))

    def test_snare_and_hihat_generate_pure_red(self):
        """Verify snares and hi-hats stay strictly red without white/cyan bleaching."""
        self.vis.set_mode(MODE_RED_ONLY)

        # Snare
        self.vis.trigger_snare()
        self.assertEqual(self.vis.peripheral_flash_color_left, (255, 0, 0))
        self.assertEqual(self.vis.peripheral_flash_color_right, (255, 0, 0))

        # Hihat
        self.vis.peripheral_flash_until = 0.0
        self.vis.trigger_hihat()
        self.assertEqual(self.vis.peripheral_flash_color_left, (255, 0, 0))
        self.assertEqual(self.vis.peripheral_flash_color_right, (255, 0, 0))

    def test_drop_generates_pure_red(self):
        """Verify massive bass drop surge produces red blast instead of white blast."""
        self.vis.set_mode(MODE_RED_ONLY)
        self.vis.trigger_drop()
        self.assertEqual(self.vis.peripheral_flash_color_left, (255, 0, 0))
        self.assertEqual(self.vis.peripheral_flash_color_right, (255, 0, 0))

    def test_rendered_rgb_has_zero_green_and_blue(self):
        """Verify _calc_color_and_intensity produces colors with strictly g=0 and b=0."""
        self.vis.set_mode(MODE_RED_ONLY)
        audio_state = {
            "total_level": 0.85,
            "bass_level": 0.90,
            "mid_level": 0.70,
            "high_level": 0.65,
            "raw_peak": 0.95,
            "is_kick": True,
            "is_snare": True,
            "is_hihat": True,
            "is_drop": True,
            "is_paused": False,
        }
        self.vis.update(0.016, audio_state)
        col, eff = self.vis._calc_color_and_intensity(self.vis.current_color, 1.0, audio_state)

        r, g, b = col
        self.assertGreater(r, 0, "Red channel must be positive during beat flash")
        self.assertEqual(g, 0, "Green channel must be strictly 0 in Red Only mode")
        self.assertEqual(b, 0, "Blue channel must be strictly 0 in Red Only mode")
        self.assertGreater(eff, 0.0)

    def test_blackout_between_beats_and_on_silence(self):
        """Verify pitch-black blackout between beats and when audio is silent."""
        self.vis.set_mode(MODE_RED_ONLY)

        # Silent audio
        audio_silent = {
            "total_level": 0.0,
            "bass_level": 0.0,
            "mid_level": 0.0,
            "high_level": 0.0,
            "raw_peak": 0.0,
            "is_paused": False,
        }
        self.vis.update(0.016, audio_silent)
        col, eff = self.vis._calc_color_and_intensity(self.vis.current_color, 0.0, audio_silent)
        self.assertEqual(col, (0, 0, 0))
        self.assertEqual(eff, 0.0)

        # Peripherals blackout
        col_l, col_r, is_strobe = self.vis.get_peripheral_colors()
        self.assertEqual(col_l, (0, 0, 0))
        self.assertEqual(col_r, (0, 0, 0))

    def test_alternating_dual_scheme_in_red_only(self):
        """Verify alternating dual monitor scheme alternates pure red between left and right."""
        self.vis.set_mode(MODE_RED_ONLY)
        self.vis.dual_scheme = DUAL_SCHEME_ALTERNATING

        # Side 0 (Left active)
        self.vis.alternating_side = 1
        self.vis.trigger_kick()
        self.assertEqual(self.vis.alternating_side, 0)
        col_left, col_right, is_strobe = self.vis.get_peripheral_colors()
        self.assertTrue(is_strobe)
        self.assertEqual(col_left, (255, 0, 0))
        self.assertEqual(col_right, (0, 0, 0))

        # Side 1 (Right active)
        self.vis.trigger_kick()
        self.assertEqual(self.vis.alternating_side, 1)
        col_left, col_right, is_strobe = self.vis.get_peripheral_colors()
        self.assertTrue(is_strobe)
        self.assertEqual(col_left, (0, 0, 0))
        self.assertEqual(col_right, (255, 0, 0))


if __name__ == "__main__":
    unittest.main()
