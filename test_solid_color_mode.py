"""
Unit tests for Solid Color Lighting Mode:
- Preset validation in config.py (14 vibrant presets)
- VisualizerEngine state, toggle_solid_color(), set_solid_color(), cycle_solid_color()
- Fullscreen solid color rendering regardless of audio silence or beat drops
- Continuous peripheral output (strobe_cut=False) on Razer Chroma, Room BLE, and Lenovo Legion RGB
- Seamless toggle between solid color lighting and music-reactive strobing
- Network sync packet serialization and deserialization
- HUD GUI button layout, swatch click hitboxes, and mode toggling
"""

import unittest
import pygame
from config import (
    SOLID_COLORS,
    SOLID_COLOR_NAMES,
    SOLID_COLOR_MAP,
    MODE_STROBE_2_0,
    MODE_PSYCHO_OVERDRIVE,
)
from visualizer import VisualizerEngine
from hud import HUD
from sync_manager import SyncManager


class TestSolidColorMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def setUp(self):
        self.vis = VisualizerEngine(1280, 720)
        self.hud = HUD(1280, 720)

    def test_solid_color_presets_defined(self):
        """Verify SOLID_COLORS contains valid presets with correct RGB tuples."""
        self.assertGreaterEqual(len(SOLID_COLORS), 12)
        self.assertEqual(len(SOLID_COLORS), len(SOLID_COLOR_NAMES))
        for name, col in SOLID_COLORS:
            self.assertIsInstance(name, str)
            self.assertEqual(len(col), 3)
            for ch in col:
                self.assertGreaterEqual(ch, 0)
                self.assertLessEqual(ch, 255)
            self.assertEqual(SOLID_COLOR_MAP[name], col)

    def test_visualizer_initial_state(self):
        """Verify initial visualizer state has solid color mode off and valid default color."""
        self.assertFalse(self.vis.is_solid_color_active())
        self.assertFalse(self.vis.solid_color_active)
        self.assertEqual(self.vis.solid_color, SOLID_COLORS[0][1])
        self.assertEqual(self.vis.get_solid_color_name(), SOLID_COLORS[0][0])

    def test_toggle_solid_color(self):
        """Verify toggle_solid_color switches between solid lighting and music strobing."""
        # Toggle on
        res = self.vis.toggle_solid_color()
        self.assertTrue(res)
        self.assertTrue(self.vis.is_solid_color_active())

        # Toggle off
        res_off = self.vis.toggle_solid_color()
        self.assertFalse(res_off)
        self.assertFalse(self.vis.is_solid_color_active())

    def test_set_solid_color_by_index_name_and_rgb(self):
        """Verify setting solid color by index, preset name, or RGB tuple."""
        # By index
        self.vis.set_solid_color(1, activate=True)
        self.assertEqual(self.vis.solid_color, SOLID_COLORS[1][1])
        self.assertEqual(self.vis.get_solid_color_name(), SOLID_COLORS[1][0])
        self.assertTrue(self.vis.is_solid_color_active())

        # By name
        self.vis.set_solid_color("Cyan", activate=True)
        self.assertEqual(self.vis.solid_color, (0, 220, 255))
        self.assertEqual(self.vis.get_solid_color_name(), "Cyan")

        # By RGB
        self.vis.set_solid_color((120, 150, 180), activate=False)
        self.assertEqual(self.vis.solid_color, (120, 150, 180))

    def test_cycle_solid_color(self):
        """Verify cycling solid colors advances through presets and wraps around."""
        initial_idx = self.vis.solid_color_index
        next_col = self.vis.cycle_solid_color()
        self.assertEqual(self.vis.solid_color_index, (initial_idx + 1) % len(SOLID_COLORS))
        self.assertEqual(next_col, SOLID_COLORS[(initial_idx + 1) % len(SOLID_COLORS)][1])
        self.assertTrue(self.vis.is_solid_color_active())

    def test_screen_rendering_in_solid_mode(self):
        """Verify screen renders solid color at full intensity even during silence or drops."""
        screen = pygame.Surface((1280, 720))
        target_color = (0, 220, 255)
        self.vis.set_solid_color(target_color, activate=True)

        silent_audio = {
            "total_level": 0.0,
            "bass_level": 0.0,
            "mid_level": 0.0,
            "high_level": 0.0,
            "raw_peak": 0.0,
            "is_paused": True,
        }

        self.vis.render(screen, silent_audio)
        self.assertEqual(self.vis.last_render_rgb_0, target_color)
        self.assertEqual(self.vis.last_render_rgb_1, target_color)
        self.assertEqual(self.vis.last_eff_intensity_0, 1.0)
        self.assertEqual(self.vis.last_eff_intensity_1, 1.0)

        # Check surface pixel
        pixel_col = screen.get_at((640, 360))[:3]
        self.assertEqual(pixel_col, target_color)

    def test_peripheral_lighting_in_solid_mode(self):
        """Verify peripheral hardware continuously outputs solid color with strobe_cut=False."""
        target_color = (255, 95, 0)
        self.vis.set_solid_color(target_color, activate=True)

        # Even with complete silence
        self.vis.is_audio_silent = True
        self.vis.is_paused = True
        self.vis.music_energy = 0.0

        col_left, col_right, is_strobe = self.vis.get_peripheral_colors()
        self.assertEqual(col_left, target_color)
        self.assertEqual(col_right, target_color)
        self.assertFalse(is_strobe)  # False indicates no strobe blackout cut!

    def test_returning_to_music_mode(self):
        """Verify toggling solid mode off cleanly restores music strobe reactivity."""
        self.vis.set_mode(MODE_STROBE_2_0)
        self.vis.toggle_solid_color()
        self.assertTrue(self.vis.is_solid_color_active())

        # Toggle back to music
        self.vis.toggle_solid_color()
        self.assertFalse(self.vis.is_solid_color_active())
        self.assertEqual(self.vis.mode, MODE_STROBE_2_0)

        # Explicitly choosing a strobe mode also deactivates solid mode
        self.vis.toggle_solid_color()
        self.assertTrue(self.vis.is_solid_color_active())
        self.vis.set_mode(MODE_PSYCHO_OVERDRIVE)
        self.assertFalse(self.vis.is_solid_color_active())
        self.assertEqual(self.vis.mode, MODE_PSYCHO_OVERDRIVE)

    def test_network_sync_packet(self):
        """Verify solid color active state and color are serialized and applied over network."""
        self.vis.set_solid_color("Lime", activate=True)
        pkt = self.vis.get_sync_packet({"spectrum_bars": []})

        self.assertIn("solid_active", pkt)
        self.assertTrue(pkt["solid_active"])
        self.assertEqual(tuple(pkt["solid_color"]), SOLID_COLOR_MAP["Lime"])

        # Apply to client visualizer
        client_vis = VisualizerEngine(1280, 720)
        self.assertFalse(client_vis.is_solid_color_active())
        client_vis.apply_sync_packet(pkt)
        self.assertTrue(client_vis.is_solid_color_active())
        self.assertEqual(client_vis.solid_color, SOLID_COLOR_MAP["Lime"])

    def test_hud_layout_and_mouse_interactions(self):
        """Verify HUD provides solid toggle button, swatches row, and responds to mouse clicks."""
        self.assertIsNotNone(self.hud.btn_solid_toggle)
        self.assertGreaterEqual(len(self.hud.solid_swatch_rects), 12)
        self.assertIsNotNone(self.hud.solid_name_rect)

        # 1. Click toggle button
        self.hud.warning_dismissed = True
        self.hud.visible = True
        self.hud.alpha = 255.0

        toggle_pos = self.hud.btn_solid_toggle.center
        consumed = self.hud.handle_mouse_down(
            toggle_pos, None, self.vis, None, None, lambda: None
        )
        self.assertTrue(consumed)
        self.assertTrue(self.vis.is_solid_color_active())

        # Click toggle button again
        consumed_off = self.hud.handle_mouse_down(
            toggle_pos, None, self.vis, None, None, lambda: None
        )
        self.assertTrue(consumed_off)
        self.assertFalse(self.vis.is_solid_color_active())

        # 2. Click a color swatch
        cyan_rect = None
        for rect, idx, name, rgb in self.hud.solid_swatch_rects:
            if name == "Cyan":
                cyan_rect = rect
                break
        self.assertIsNotNone(cyan_rect)

        consumed_swatch = self.hud.handle_mouse_down(
            cyan_rect.center, None, self.vis, None, None, lambda: None
        )
        self.assertTrue(consumed_swatch)
        self.assertTrue(self.vis.is_solid_color_active())
        self.assertEqual(self.vis.solid_color, (0, 220, 255))
        self.assertEqual(self.vis.get_solid_color_name(), "Cyan")


if __name__ == "__main__":
    unittest.main()
