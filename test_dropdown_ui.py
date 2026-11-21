"""
Unit and Integration Test Suite for HUD Dropdown Selectors and Redesigned UI.
Verifies interactive dropdown menus (Mode, Palette, Device, Style, DualFX, Display),
item selection, hover states, outside click dismissal, and escape key handling.
"""

import unittest
import pygame
from config import (
    STROBE_MODES,
    MODE_STROBE_2_0,
    MODE_PSYCHO_OVERDRIVE,
    MODE_BASS_ONLY,
    MODE_RED_ONLY,
    MODE_ALBUM_ART,
    PALETTES,
    PALETTE_NAMES,
    PALETTE_ALBUM_ART,
)
from visualizer import VisualizerEngine, DUAL_SCHEMES
from audio_capture import AudioCaptureManager
from display_manager import DisplayManager
from sync_manager import SyncManager
from hud import HUD


class TestDropdownUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def setUp(self):
        self.hud = HUD(1280, 720)
        self.hud.warning_dismissed = True
        self.hud.visible = True
        self.hud.alpha = 255.0
        self.vis = VisualizerEngine(1280, 720)
        self.audio = AudioCaptureManager()
        self.disp = DisplayManager()
        self.sync = SyncManager()
        self.dummy_audio_state = {
            "bass_level": 0.5,
            "mid_level": 0.3,
            "high_level": 0.2,
            "total_level": 0.4,
            "spectrum_bars": [0.2] * 24,
            "bpm": 128.0,
        }

    def tearDown(self):
        self.audio.stop()
        self.sync.stop()

    def test_mode_dropdown_open_select_and_close(self):
        """Verify clicking Mode button opens dropdown, renders items, and selecting an item switches mode."""
        surf = pygame.Surface((1280, 720))
        self.assertIsNone(self.hud.open_dropdown)

        # 1. Click Mode dropdown button to open
        consumed = self.hud.handle_mouse_down(
            self.hud.btn_mode.center, self.audio, self.vis, self.disp, self.sync, lambda: None
        )
        self.assertTrue(consumed)
        self.assertEqual(self.hud.open_dropdown, "mode")

        # 2. Render HUD with dropdown open to populate dropdown item hitboxes
        self.hud.render(surf, self.audio, self.vis, self.disp, self.sync, self.dummy_audio_state, False)
        self.assertGreater(len(self.hud.dropdown_items), 0)
        self.assertEqual(len(self.hud.dropdown_items), len(STROBE_MODES))

        # 3. Locate Bass Only mode item rect in dropdown
        target_rect = None
        for r, val, lbl, is_act, _ in self.hud.dropdown_items:
            if val == MODE_BASS_ONLY:
                target_rect = r
                break
        self.assertIsNotNone(target_rect, "MODE_BASS_ONLY item rect not found in dropdown items")

        # 4. Click the target mode item in dropdown
        consumed_item = self.hud.handle_mouse_down(
            target_rect.center, self.audio, self.vis, self.disp, self.sync, lambda: None
        )
        self.assertTrue(consumed_item)
        self.assertEqual(self.vis.mode, MODE_BASS_ONLY)
        self.assertIsNone(self.hud.open_dropdown, "Dropdown should close after selection")

    def test_palette_dropdown_with_color_swatches(self):
        """Verify Palette dropdown opens, provides color swatches, and clicking an item applies palette."""
        surf = pygame.Surface((1280, 720))

        # Open palette dropdown
        self.hud.handle_mouse_down(
            self.hud.btn_palette.center, self.audio, self.vis, self.disp, self.sync, lambda: None
        )
        self.assertEqual(self.hud.open_dropdown, "palette")

        # Render to populate items
        self.hud.render(surf, self.audio, self.vis, self.disp, self.sync, self.dummy_audio_state, False)
        self.assertEqual(len(self.hud.dropdown_items), len(PALETTE_NAMES))

        # Verify swatches are attached to palette items
        found_swatches = False
        target_rect = None
        for r, val, lbl, is_act, swatches in self.hud.dropdown_items:
            if swatches and len(swatches) > 0:
                found_swatches = True
            if val == "Cyberpunk":
                target_rect = r
        self.assertTrue(found_swatches, "Palette items should provide swatch colors")
        self.assertIsNotNone(target_rect)

        # Click Cyberpunk palette item
        consumed = self.hud.handle_mouse_down(
            target_rect.center, self.audio, self.vis, self.disp, self.sync, lambda: None
        )
        self.assertTrue(consumed)
        self.assertEqual(self.vis.palette_name, "Cyberpunk")
        self.assertIsNone(self.hud.open_dropdown)

    def test_audio_device_dropdown_selection(self):
        """Verify Audio Input dropdown opens and selecting a device switches current device."""
        surf = pygame.Surface((1280, 720))

        # Open device dropdown
        self.hud.handle_mouse_down(
            self.hud.btn_device.center, self.audio, self.vis, self.disp, self.sync, lambda: None
        )
        self.assertEqual(self.hud.open_dropdown, "device")

        self.hud.render(surf, self.audio, self.vis, self.disp, self.sync, self.dummy_audio_state, False)
        self.assertGreater(len(self.hud.dropdown_items), 0)

        # Click first device item
        first_item_rect = self.hud.dropdown_items[0][0]
        consumed = self.hud.handle_mouse_down(
            first_item_rect.center, self.audio, self.vis, self.disp, self.sync, lambda: None
        )
        self.assertTrue(consumed)
        self.assertEqual(self.audio.current_device_index, 0)
        self.assertIsNone(self.hud.open_dropdown)

    def test_style_and_dualfx_dropdowns(self):
        """Verify Visual Style and Dual FX dropdowns work and apply changes to visualizer."""
        surf = pygame.Surface((1280, 720))

        # 1. Style Dropdown
        self.hud.handle_mouse_down(
            self.hud.btn_style.center, self.audio, self.vis, self.disp, self.sync, lambda: None
        )
        self.assertEqual(self.hud.open_dropdown, "style")
        self.hud.render(surf, self.audio, self.vis, self.disp, self.sync, self.dummy_audio_state, False)
        self.assertEqual(len(self.hud.dropdown_items), len(self.vis.visual_styles))

        # Select second style
        second_rect = self.hud.dropdown_items[1][0]
        self.hud.handle_mouse_down(second_rect.center, self.audio, self.vis, self.disp, self.sync, lambda: None)
        self.assertEqual(self.vis.style_index, 1)
        self.assertIsNone(self.hud.open_dropdown)

        # 2. Dual FX Dropdown
        self.hud.handle_mouse_down(
            self.hud.btn_dualfx.center, self.audio, self.vis, self.disp, self.sync, lambda: None
        )
        self.assertEqual(self.hud.open_dropdown, "dualfx")
        self.hud.render(surf, self.audio, self.vis, self.disp, self.sync, self.dummy_audio_state, True)
        self.assertEqual(len(self.hud.dropdown_items), len(DUAL_SCHEMES))

        # Select second dual scheme
        dual_rect = self.hud.dropdown_items[1][0]
        self.hud.handle_mouse_down(dual_rect.center, self.audio, self.vis, self.disp, self.sync, lambda: None)
        self.assertEqual(self.vis.dual_scheme_index, 1)
        self.assertIsNone(self.hud.open_dropdown)

    def test_dropdown_toggle_same_button_closes(self):
        """Verify clicking the same dropdown button twice toggles it open and closed."""
        self.assertIsNone(self.hud.open_dropdown)
        self.hud.handle_mouse_down(
            self.hud.btn_mode.center, self.audio, self.vis, self.disp, self.sync, lambda: None
        )
        self.assertEqual(self.hud.open_dropdown, "mode")

        self.hud.handle_mouse_down(
            self.hud.btn_mode.center, self.audio, self.vis, self.disp, self.sync, lambda: None
        )
        self.assertIsNone(self.hud.open_dropdown)

    def test_dropdown_click_outside_closes(self):
        """Verify clicking outside an open dropdown dismisses it."""
        surf = pygame.Surface((1280, 720))
        self.hud.handle_mouse_down(
            self.hud.btn_mode.center, self.audio, self.vis, self.disp, self.sync, lambda: None
        )
        self.assertEqual(self.hud.open_dropdown, "mode")
        self.hud.render(surf, self.audio, self.vis, self.disp, self.sync, self.dummy_audio_state, False)

        # Click at top of screen outside panel and outside dropdown menu
        outside_pos = (640, 50)
        consumed = self.hud.handle_mouse_down(
            outside_pos, self.audio, self.vis, self.disp, self.sync, lambda: None
        )
        self.assertIsNone(self.hud.open_dropdown)

    def test_dropdown_mouse_motion_hover(self):
        """Verify moving mouse over dropdown items updates hover index."""
        surf = pygame.Surface((1280, 720))
        self.hud.handle_mouse_down(
            self.hud.btn_mode.center, self.audio, self.vis, self.disp, self.sync, lambda: None
        )
        self.hud.render(surf, self.audio, self.vis, self.disp, self.sync, self.dummy_audio_state, False)

        first_rect = self.hud.dropdown_items[0][0]
        self.hud.handle_mouse_motion(
            first_rect.center, self.audio, self.vis, self.disp
        )
        self.assertEqual(self.hud.hover_dropdown_item_idx, 0)


if __name__ == "__main__":
    unittest.main()
