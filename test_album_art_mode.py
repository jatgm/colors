"""
Unit and Integration Test Suite for Native Album Cover Art Mode & Hardware Peripheral Sync.
"""

import sys
import io
import time
import unittest
import numpy as np
import pygame
import colorsys

from config import (
    PALETTES,
    PALETTE_NAMES,
    PALETTE_ALBUM_ART,
    STROBE_MODES,
    MODE_ALBUM_ART,
    MODE_PSYCHO_OVERDRIVE,
)
from visualizer import VisualizerEngine
from hud import HUD
from sync_manager import SyncManager
from media_sync import MediaArtManager, extract_cover_palette, DEFAULT_ALBUM_PALETTE


class TestPaletteExtraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_empty_and_corrupt_input(self):
        """Verify extraction handles empty or corrupt bytes gracefully without crashing."""
        pal_none = extract_cover_palette(b"")
        self.assertEqual(len(pal_none), 5)
        self.assertEqual(pal_none, DEFAULT_ALBUM_PALETTE)

        pal_corrupt = extract_cover_palette(b"not an image data bytes")
        self.assertEqual(len(pal_corrupt), 5)
        self.assertEqual(pal_corrupt, DEFAULT_ALBUM_PALETTE)

    def test_synthetic_vibrant_cover(self):
        """Test multi-color vibrant artwork extraction."""
        surf = pygame.Surface((100, 100))
        surf.fill((255, 0, 100))  # Magenta
        pygame.draw.rect(surf, (0, 240, 255), (0, 0, 50, 50))  # Cyan
        pygame.draw.rect(surf, (255, 230, 0), (50, 50, 50, 50))  # Yellow
        pygame.draw.rect(surf, (0, 255, 100), (50, 0, 50, 50))  # Green

        buf = io.BytesIO()
        pygame.image.save(surf, buf)
        raw_bytes = buf.getvalue()

        palette = extract_cover_palette(raw_bytes, num_colors=5)
        self.assertEqual(len(palette), 5)
        for col in palette:
            self.assertEqual(len(col), 3)
            r, g, b = col
            self.assertTrue(0 <= r <= 255)
            self.assertTrue(0 <= g <= 255)
            self.assertTrue(0 <= b <= 255)

    def test_monochrome_artwork_extraction(self):
        """Test grayscale / monochrome artwork extraction produces distinct steps."""
        surf = pygame.Surface((100, 100))
        for y in range(100):
            val = int(255 * (y / 100.0))
            pygame.draw.line(surf, (val, val, val), (0, y), (99, y))

        buf = io.BytesIO()
        pygame.image.save(surf, buf)
        raw_bytes = buf.getvalue()

        palette = extract_cover_palette(raw_bytes, num_colors=5)
        self.assertEqual(len(palette), 5)
        # Should produce valid non-zero luminance entries
        for r, g, b in palette:
            self.assertTrue(max(r, g, b) > 30)

    def test_single_color_artwork(self):
        """Test single-dominant color artwork generates rich tonal variations of that hue."""
        surf = pygame.Surface((100, 100))
        surf.fill((220, 20, 20))  # Pure crimson

        buf = io.BytesIO()
        pygame.image.save(surf, buf)
        raw_bytes = buf.getvalue()

        palette = extract_cover_palette(raw_bytes, num_colors=5)
        self.assertEqual(len(palette), 5)
        # All colors should be valid RGB and in the red hue family
        for col in palette:
            self.assertEqual(len(col), 3)
            r, g, b = col
            self.assertTrue(r > max(g, b), f"Expected red dominant color, got {col}")

    def test_dominant_orange_cover_art(self):
        """Test album artwork dominated by orange produces a palette that is majority/wholly orange."""
        surf = pygame.Surface((200, 200))
        surf.fill((240, 115, 30))  # Frank Ocean Channel Orange hue
        # Subtle white text overlay
        pygame.draw.rect(surf, (255, 255, 255), (40, 90, 120, 20))

        buf = io.BytesIO()
        pygame.image.save(surf, buf, "PNG")
        palette = extract_cover_palette(buf.getvalue(), num_colors=5)

        self.assertEqual(len(palette), 5)
        orange_count = 0
        for r, g, b in palette:
            h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            hue_deg = h * 360.0
            # Orange range: ~10 to 45 degrees
            if 10.0 <= hue_deg <= 45.0 and s >= 0.50:
                orange_count += 1

        # At least 4 of 5 (80%+) or 5 of 5 must be in the orange hue family
        self.assertGreaterEqual(orange_count, 4, f"Expected majority orange, got {orange_count}/5 in palette: {palette}")

    def test_dominant_color_with_secondary_accent(self):
        """Test artwork with dominant color (70% blue) and secondary accent (30% yellow) maintains majority dominant hue."""
        surf = pygame.Surface((100, 100))
        surf.fill((20, 80, 220))  # Dominant blue
        pygame.draw.rect(surf, (245, 220, 20), (0, 0, 55, 55))  # Secondary yellow accent

        buf = io.BytesIO()
        pygame.image.save(surf, buf, "PNG")
        palette = extract_cover_palette(buf.getvalue(), num_colors=5)

        self.assertEqual(len(palette), 5)
        # Dominant hue (blue: ~200-240 deg) should have majority (>= 3 of 5)
        blue_count = 0
        yellow_count = 0
        for r, g, b in palette:
            h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            deg = h * 360.0
            if 190.0 <= deg <= 250.0:
                blue_count += 1
            elif 40.0 <= deg <= 70.0:
                yellow_count += 1

        self.assertGreaterEqual(blue_count, 3, f"Expected at least 3 blue swatches, got {blue_count}: {palette}")
        self.assertGreaterEqual(yellow_count, 1, f"Expected at least 1 yellow accent swatch, got {yellow_count}: {palette}")


class TestVisualizerAlbumArtMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def setUp(self):
        self.vis = VisualizerEngine(1280, 720)

    def test_mode_and_palette_definitions(self):
        """Verify MODE_ALBUM_ART and PALETTE_ALBUM_ART exist in config collections."""
        self.assertIn(MODE_ALBUM_ART, STROBE_MODES)
        self.assertIn(PALETTE_ALBUM_ART, PALETTES)
        self.assertIn(PALETTE_ALBUM_ART, PALETTE_NAMES)

    def test_toggle_album_art_mode(self):
        """Verify toggle_album_art_mode toggles between Album Art mode and previous mode."""
        self.vis.set_mode(MODE_PSYCHO_OVERDRIVE)
        self.vis.set_palette("Cyberpunk")

        # Toggle ON
        is_on = self.vis.toggle_album_art_mode()
        self.assertTrue(is_on)
        self.assertEqual(self.vis.mode, MODE_ALBUM_ART)
        self.assertEqual(self.vis.palette_name, PALETTE_ALBUM_ART)

        # Toggle OFF
        is_on = self.vis.toggle_album_art_mode()
        self.assertFalse(is_on)
        self.assertEqual(self.vis.mode, MODE_PSYCHO_OVERDRIVE)
        self.assertEqual(self.vis.palette_name, "Cyberpunk")

    def test_set_mode_auto_selects_palette(self):
        """Verify selecting MODE_ALBUM_ART automatically switches palette to PALETTE_ALBUM_ART."""
        self.vis.set_mode(MODE_ALBUM_ART)
        self.assertEqual(self.vis.palette_name, PALETTE_ALBUM_ART)

    def test_update_album_art_palette(self):
        """Verify update_album_art_palette updates active colors."""
        test_pal = [(10, 20, 30), (40, 50, 60), (70, 80, 90), (100, 110, 120), (130, 140, 150)]
        self.vis.set_mode(MODE_ALBUM_ART)
        self.vis.update_album_art_palette(test_pal)

        self.assertEqual(PALETTES[PALETTE_ALBUM_ART], test_pal)
        self.assertEqual(self.vis.palette_colors, test_pal)

    def test_kick_cycles_album_art_colors(self):
        """Verify trigger_kick cycles through the album art colors."""
        test_pal = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255)]
        self.vis.set_mode(MODE_ALBUM_ART)
        self.vis.update_album_art_palette(test_pal)

        self.vis.trigger_kick()
        col1 = self.vis.current_color
        self.assertIn(col1, test_pal)

        self.vis.trigger_kick()
        col2 = self.vis.current_color
        self.assertIn(col2, test_pal)

    def test_peripheral_colors_sync_to_album_art(self):
        """Verify get_peripheral_colors returns album art colors during strobe."""
        test_pal = [(255, 10, 20), (10, 255, 30), (10, 20, 255), (255, 255, 10), (10, 255, 255)]
        self.vis.set_mode(MODE_ALBUM_ART)
        self.vis.update_album_art_palette(test_pal)
        self.vis.trigger_kick()

        col_left, col_right, is_strobe = self.vis.get_peripheral_colors()
        self.assertTrue(is_strobe)
        # Scaled color should have peak 255 in primary component
        self.assertGreater(max(col_left), 0)
        self.assertGreater(max(col_right), 0)

    def test_peripheral_ambient_illumination_between_beats(self):
        """Verify peripherals in Album Art mode retain ambient cover glow between beats rather than dying into pitch black."""
        test_pal = [(255, 0, 128), (0, 240, 255), (157, 0, 255), (255, 230, 0), (0, 255, 170)]
        self.vis.set_mode(MODE_ALBUM_ART)
        self.vis.update_album_art_palette(test_pal)

        # Render dummy frame so last_render_rgb_0 is populated with music floor
        dummy_audio = {"total_level": 0.5, "bass_level": 0.4, "mid_level": 0.3, "spectrum_bars": np.zeros(24)}
        surf = pygame.Surface((100, 100))
        self.vis.render(surf, dummy_audio)

        # Clear any strobe flash timer
        self.vis.peripheral_flash_until = 0.0

        col_left, col_right, is_strobe = self.vis.get_peripheral_colors()
        # Should not be a strobe blackout
        self.assertFalse(is_strobe)
        # Should retain ambient glowing illumination in album colors
        self.assertGreater(max(col_left), 0)
        self.assertGreater(max(col_right), 0)

    def test_toggle_when_palette_is_album_art_but_mode_differs(self):
        """Verify toggle_album_art_mode properly deactivates when only palette is PALETTE_ALBUM_ART."""
        self.vis.set_mode(MODE_PSYCHO_OVERDRIVE)
        self.vis.set_palette(PALETTE_ALBUM_ART)
        self.assertTrue(self.vis.is_album_art_active())

        # Calling toggle should deactivate it and revert to non-album-art mode and palette
        res = self.vis.toggle_album_art_mode()
        self.assertFalse(res)
        self.assertFalse(self.vis.is_album_art_active())
        self.assertNotEqual(self.vis.palette_name, PALETTE_ALBUM_ART)
        self.assertNotEqual(self.vis.mode, MODE_ALBUM_ART)

    def test_sync_packet_includes_album_art_colors(self):
        """Verify Host packet includes palette_colors and Client applies them."""
        test_pal = [(42, 84, 126), (100, 200, 50), (150, 20, 80), (200, 210, 220), (30, 40, 50)]
        self.vis.set_mode(MODE_ALBUM_ART)
        self.vis.update_album_art_palette(test_pal)

        dummy_audio = {"spectrum_bars": np.zeros(24)}
        packet = self.vis.get_sync_packet(dummy_audio, is_beat_event=True)

        self.assertIn("palette_colors", packet)
        self.assertEqual(packet["palette_colors"], [list(c) for c in test_pal])

        # Client instance
        client_vis = VisualizerEngine(1280, 720)
        client_vis.apply_sync_packet(packet)
        self.assertEqual(client_vis.mode, MODE_ALBUM_ART)
        self.assertEqual(client_vis.palette_name, PALETTE_ALBUM_ART)
        self.assertEqual(client_vis.palette_colors, test_pal)

    def test_render_strobe_album_art(self):
        """Verify rendering in MODE_ALBUM_ART produces valid display output."""
        surface = pygame.Surface((640, 360))
        dummy_audio = {
            "is_kick": True,
            "bass_level": 0.8,
            "mid_level": 0.5,
            "high_level": 0.3,
            "total_level": 0.7,
        }
        self.vis.set_mode(MODE_ALBUM_ART)
        self.vis.update(0.016, dummy_audio)
        self.vis.render(surface, dummy_audio)

        self.assertGreaterEqual(self.vis.last_eff_intensity_0, 0.0)
        self.assertGreater(max(self.vis.last_render_rgb_0), 0)


class TestHUDIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def setUp(self):
        self.hud = HUD(1280, 720)
        self.vis = VisualizerEngine(1280, 720)
        self.media_mgr = MediaArtManager()

    def tearDown(self):
        self.media_mgr.stop()

    def test_hud_elements_exist(self):
        """Verify btn_album_art and card_album_art are created in HUD layout."""
        self.assertTrue(hasattr(self.hud, "btn_album_art"))
        self.assertTrue(hasattr(self.hud, "card_album_art"))
        self.assertGreater(self.hud.btn_album_art.width, 0)
        self.assertGreater(self.hud.card_album_art.width, 0)

    def test_hud_button_click_toggles_mode(self):
        """Verify clicking btn_album_art toggles visualizer into Album Art mode."""
        self.hud.warning_dismissed = True
        btn_pos = (self.hud.btn_album_art.centerx, self.hud.btn_album_art.centery)

        # Click button
        consumed = self.hud.handle_mouse_down(
            btn_pos,
            None,
            self.vis,
            None,
            None,
            lambda: None,
            media_mgr=self.media_mgr,
        )
        self.assertTrue(consumed)
        self.assertEqual(self.vis.mode, MODE_ALBUM_ART)
        self.assertEqual(self.vis.palette_name, PALETTE_ALBUM_ART)

    def test_hud_card_click_toggles_mode(self):
        """Verify clicking Now Playing card toggles visualizer into Album Art mode."""
        self.hud.warning_dismissed = True
        self.vis.set_mode(MODE_PSYCHO_OVERDRIVE)

        card_pos = (self.hud.card_album_art.centerx, self.hud.card_album_art.centery)
        consumed = self.hud.handle_mouse_down(
            card_pos,
            None,
            self.vis,
            None,
            None,
            lambda: None,
            media_mgr=self.media_mgr,
        )
        self.assertTrue(consumed)
        self.assertEqual(self.vis.mode, MODE_ALBUM_ART)

    def test_hud_render_without_crash(self):
        """Verify HUD renders cleanly with media_mgr provided."""
        self.hud.warning_dismissed = True
        surface = pygame.Surface((1280, 720))
        class DummyAudioMgr:
            current_device_name = "Test Audio"
            demo_mode = False
            def get_sensitivity(self): return 1.5
            def get_preamp_gain(self): return 2.0
        dummy_audio_mgr = DummyAudioMgr()
        sync_mgr = SyncManager()

        dummy_state = {
            "bass_level": 0.5,
            "mid_level": 0.4,
            "high_level": 0.3,
            "total_level": 0.5,
            "spectrum_bars": np.zeros(24),
            "bpm": 128.0,
            "raw_peak": 0.5,
            "agc_gain": 1.2,
        }

        # Should render without throwing any exceptions
        self.hud.render(
            surface,
            dummy_audio_mgr,
            self.vis,
            None,
            sync_mgr,
            dummy_state,
            is_dual=False,
            media_mgr=self.media_mgr,
        )

    def test_hud_layout_no_bpm_overlap(self):
        """Verify BPM label and Now Playing card never collide or overlap across common window resolutions."""
        resolutions = [(1280, 720), (1024, 768), (800, 600)]
        for w, h in resolutions:
            hud = HUD(w, h)
            hud.warning_dismissed = True
            card_x = hud.card_album_art.x

            # Calculate BPM rightmost extent as rendered in HUD
            panel = hud.panel_rect
            avail_for_audio = max(240, card_x - (panel.x + 20) - 30)
            spec_w = min(220, int(avail_for_audio * 0.46))
            levels_x = panel.x + 20 + spec_w + 14
            meter_w = min(96, int(avail_for_audio * 0.21))
            beat_x = levels_x + 36 + meter_w + 22

            bpm_str = "140 BPM"
            bpm_text_w = hud.font_title.size(bpm_str)[0]
            bpm_right = beat_x + 22 + bpm_text_w

            # Verify BPM text ends strictly before the Now Playing card begins
            self.assertLess(bpm_right, card_x, f"BPM text at x={bpm_right} overlaps card at x={card_x} in {w}x{h}")

    def test_media_info_playback_status(self):
        """Verify MediaArtManager info includes paused/playing status."""
        info = self.media_mgr.get_info()
        self.assertIn("is_paused", info)
        self.assertIn("is_playing", info)
        self.assertIn("status", info)

    def test_hud_panel_sleek_height(self):
        """Verify HUD panel height is streamlined down to <= 300px to maximize visualizer screen space."""
        hud = HUD(1280, 720)
        self.assertLessEqual(hud.panel_rect.height, 300)
        self.assertEqual(hud.panel_rect.height, 282)

    def test_hud_sliders_horizontal_compact(self):
        """Verify the 3 sliders (sensitivity, gain, decay) share the same horizontal row."""
        hud = HUD(1280, 720)
        self.assertEqual(hud.slider_sens_rect.y, hud.slider_gain_rect.y)
        self.assertEqual(hud.slider_gain_rect.y, hud.slider_decay_rect.y)
        self.assertLess(hud.slider_sens_rect.right, hud.slider_gain_rect.left)
        self.assertLess(hud.slider_gain_rect.right, hud.slider_decay_rect.left)

    def test_app_album_art_default(self):
        """Verify BeatStrobeApp initializes with Album Cover Art mode active by default."""
        from main import BeatStrobeApp
        app = BeatStrobeApp()
        try:
            self.assertEqual(app.visualizer.mode, MODE_ALBUM_ART)
            self.assertEqual(app.visualizer.palette_name, PALETTE_ALBUM_ART)
        finally:
            app.audio_mgr.stop()
            app.media_mgr.stop()
            app.razer_mgr.stop()
            app.happylighting_mgr.stop()
            app.lenovo_mgr.stop()
            app.sync_mgr.stop()

    def test_audio_device_selection_and_auto_spotify(self):
        """Verify AudioCaptureManager device selection methods and Spotify auto-switch."""
        from audio_capture import AudioCaptureManager, PROCTAP_AVAILABLE
        mgr = AudioCaptureManager()
        self.assertTrue(mgr.select_device(0))
        self.assertEqual(mgr.current_device_index, 0)
        if PROCTAP_AVAILABLE and "spotify" in mgr.devices:
            success = mgr.select_device("spotify")
            self.assertTrue(success)
            self.assertEqual(mgr.devices[mgr.current_device_index], "spotify")


if __name__ == "__main__":
    unittest.main()
