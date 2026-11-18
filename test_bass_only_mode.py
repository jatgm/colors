"""
Unit tests for Bass Only Strobe Mode (MODE_BASS_ONLY):
- Mode registration in STROBE_MODES
- Engine toggle_bass_only() and is_bass_only_active()
- Selective beat trigger filtering: only kicks, 808s, and heavy sub-bass trigger
- Complete suppression of snares, hi-hats, and vocal/midrange frequencies
- Blackout contrast between bass hits and peripheral lighting lockstep
"""

import unittest
import pygame
from config import (
    MODE_BASS_ONLY,
    MODE_STROBE_2_0,
    MODE_PSYCHO_OVERDRIVE,
    STROBE_MODES,
)
from visualizer import VisualizerEngine


class TestBassOnlyMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def setUp(self):
        self.vis = VisualizerEngine(1280, 720)

    def test_mode_registration(self):
        """Verify MODE_BASS_ONLY is defined and present in STROBE_MODES."""
        self.assertEqual(MODE_BASS_ONLY, "[BASS] Bass Only")
        self.assertIn(MODE_BASS_ONLY, STROBE_MODES)

    def test_toggle_bass_only(self):
        """Verify toggling Bass Only mode switches to MODE_BASS_ONLY and restores previous mode."""
        self.vis.set_mode(MODE_STROBE_2_0)
        self.assertFalse(self.vis.is_bass_only_active())

        # Toggle on
        res = self.vis.toggle_bass_only()
        self.assertTrue(res)
        self.assertTrue(self.vis.is_bass_only_active())
        self.assertEqual(self.vis.mode, MODE_BASS_ONLY)

        # Toggle off
        res_off = self.vis.toggle_bass_only()
        self.assertFalse(res_off)
        self.assertFalse(self.vis.is_bass_only_active())
        self.assertEqual(self.vis.mode, MODE_STROBE_2_0)

    def test_snare_and_hihat_ignored_in_bass_only(self):
        """Verify snares and hi-hats are completely ignored and do not trigger flashes."""
        self.vis.set_mode(MODE_BASS_ONLY)

        # 1. Feed audio state with only snare active
        audio_snare = {
            "is_kick": False,
            "is_808": False,
            "is_snare": True,
            "is_hihat": False,
            "bass_level": 0.0,
            "sub_bass_level": 0.0,
            "mid_level": 0.8,
            "total_level": 0.8,
            "raw_peak": 0.5,
        }
        self.vis.update(0.016, audio_snare)

        self.assertEqual(self.vis.kick_intensity, 0.0)
        self.assertEqual(self.vis.snare_intensity, 0.0)
        col, eff = self.vis._calc_color_and_intensity(self.vis.current_color, 0.0, audio_snare)
        self.assertEqual(col, (0, 0, 0))
        self.assertEqual(eff, 0.0)

        # 2. Feed audio state with only hi-hat active
        audio_hihat = {
            "is_kick": False,
            "is_808": False,
            "is_snare": False,
            "is_hihat": True,
            "bass_level": 0.0,
            "sub_bass_level": 0.0,
            "high_level": 0.9,
            "total_level": 0.7,
            "raw_peak": 0.5,
        }
        self.vis.update(0.016, audio_hihat)

        self.assertEqual(self.vis.kick_intensity, 0.0)
        self.assertEqual(self.vis.hihat_intensity, 0.0)
        col, eff = self.vis._calc_color_and_intensity(self.vis.current_color, 0.0, audio_hihat)
        self.assertEqual(col, (0, 0, 0))
        self.assertEqual(eff, 0.0)

    def test_kick_and_808_trigger_flashes_in_bass_only(self):
        """Verify kicks and 808s detonate full strobe flashes and advance colors."""
        self.vis.set_mode(MODE_BASS_ONLY)
        initial_color = self.vis.current_color

        # Feed kick beat
        audio_kick = {
            "is_kick": True,
            "is_808": False,
            "is_snare": False,
            "is_hihat": False,
            "bass_level": 0.9,
            "sub_bass_level": 0.85,
            "total_level": 0.9,
            "raw_peak": 0.9,
        }
        self.vis.update(0.016, audio_kick)

        self.assertGreater(self.vis.kick_intensity, 0.8)
        col, eff = self.vis._calc_color_and_intensity(self.vis.current_color, self.vis.kick_intensity, audio_kick)
        self.assertGreater(max(col), 150)
        self.assertGreater(eff, 0.8)
        self.assertNotEqual(self.vis.current_color, initial_color)

    def test_vocal_and_melody_blackout(self):
        """Verify high/mid vocal sections with no bass produce true blackout in Bass Only mode."""
        self.vis.set_mode(MODE_BASS_ONLY)

        # Loud vocals and lead synths, zero bass
        audio_vocals = {
            "is_kick": False,
            "is_808": False,
            "is_snare": False,
            "is_hihat": False,
            "bass_level": 0.0,
            "sub_bass_level": 0.0,
            "mid_level": 0.95,
            "high_level": 0.90,
            "total_level": 0.92,
            "raw_peak": 0.8,
        }
        self.vis.update(0.016, audio_vocals)

        col, eff = self.vis._calc_color_and_intensity(self.vis.current_color, 0.0, audio_vocals)
        self.assertEqual(col, (0, 0, 0))
        self.assertEqual(eff, 0.0)

    def test_peripheral_sync_in_bass_only(self):
        """Verify peripherals flash only on bass hits and stay black during other sounds."""
        self.vis.set_mode(MODE_BASS_ONLY)

        # Non-bass audio
        audio_mid = {
            "is_kick": False,
            "is_808": False,
            "bass_level": 0.0,
            "sub_bass_level": 0.0,
            "mid_level": 0.9,
            "total_level": 0.9,
            "raw_peak": 0.8,
        }
        self.vis.update(0.016, audio_mid)
        col_l, col_r, is_strobe = self.vis.get_peripheral_colors()
        self.assertEqual(col_l, (0, 0, 0))
        self.assertEqual(col_r, (0, 0, 0))

        # Kick hit
        audio_kick = {
            "is_kick": True,
            "bass_level": 0.9,
            "sub_bass_level": 0.9,
            "total_level": 0.9,
            "raw_peak": 0.9,
        }
        self.vis.update(0.016, audio_kick)
        col_l, col_r, is_strobe = self.vis.get_peripheral_colors()
        self.assertGreater(max(col_l), 100)
        self.assertGreater(max(col_r), 100)


if __name__ == "__main__":
    unittest.main()
