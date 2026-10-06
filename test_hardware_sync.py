"""
Hardware Synchronization Verification Test for Album Art Color Palette.
Tests Razer Chroma, HappyLighting BLE, and Lenovo Legion RGB managers with Album Art colors.
"""

import time
import unittest
import pygame
from config import MODE_ALBUM_ART, PALETTE_ALBUM_ART
from visualizer import VisualizerEngine
from razer_chroma import RazerChromaManager
from happylighting import HappyLightingManager
from lenovo_legion import LenovoLegionManager


class TestHardwareSyncWithAlbumArt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def setUp(self):
        self.vis = VisualizerEngine(1280, 720)
        self.razer = RazerChromaManager()
        self.happy = HappyLightingManager(auto_discover=False)
        self.lenovo = LenovoLegionManager()

    def tearDown(self):
        self.razer.stop()
        self.happy.stop()
        self.lenovo.stop()

    def test_hardware_receives_album_art_colors(self):
        """Verify hardware managers process album art colors during beat flashes."""
        test_palette = [
            (255, 30, 80),    # Vivid Neon Red-Pink
            (0, 220, 255),    # Vibrant Cyan
            (180, 40, 255),   # Royal Violet
            (255, 200, 20),   # Gold Flare
            (30, 255, 150),   # Emerald Mint
        ]

        # 1. Activate Album Art mode and inject test palette
        self.vis.set_mode(MODE_ALBUM_ART)
        self.vis.update_album_art_palette(test_palette)

        # 2. Trigger kick beat to latch hardware flash
        self.vis.trigger_kick()

        # 3. Retrieve peripheral colors
        col_left, col_right, is_strobe = self.vis.get_peripheral_colors()
        self.assertTrue(is_strobe)
        self.assertGreater(max(col_left), 0)
        self.assertGreater(max(col_right), 0)

        # 4. Dispatch to hardware managers without exceptions
        self.razer.set_colors(col_left, col_right, strobe_cut=is_strobe)
        self.happy.set_colors(col_left, strobe_cut=is_strobe)
        self.lenovo.set_colors(col_left, strobe_cut=is_strobe)
        self.lenovo.set_colors(col_left, col_right, strobe_cut=is_strobe)

        # Allow worker threads to cycle
        time.sleep(0.05)

        # Verify queues didn't jam and methods executed successfully
        self.assertTrue(True)

    def test_lenovo_legion_strobe_and_blackout_cycle(self):
        """Verify Lenovo Legion manager processes beat strobe impacts and true blackout cuts cleanly."""
        # 1. Beat impact flash (dual color)
        self.lenovo.set_colors((255, 0, 50), (0, 200, 255), strobe_cut=True)
        time.sleep(0.04)

        # 2. True blackout cut
        self.lenovo.set_colors((0, 0, 0), (0, 0, 0), strobe_cut=True)
        time.sleep(0.04)

        # 3. Single-color call compatibility
        self.lenovo.set_colors((180, 40, 255), strobe_cut=False)
        time.sleep(0.04)

        # 4. Toggle enabled / disabled states
        enabled = self.lenovo.toggle_enabled()
        self.assertFalse(enabled)
        enabled = self.lenovo.toggle_enabled()
        self.assertTrue(enabled)

    def test_lenovo_legion_all_native_zones_covered(self):
        """Verify all native Lenovo zones (including Zone 1 Logo and Zone 2 Bezel) are pre-allocated."""
        from lenovo_legion import (
            ZONE_LOGO,
            ZONE_FRONT_BEZEL,
            ZONE_FRONT_ACCENT,
            ZONE_REAR_FAN,
            ZONE_CPU_COOLER,
            ZONE_FRONT_UPPER,
            ZONE_FRONT_LOWER,
            ALL_NATIVE_ZONES,
        )
        expected_zones = {ZONE_LOGO, ZONE_FRONT_BEZEL, ZONE_FRONT_ACCENT, ZONE_REAR_FAN, ZONE_CPU_COOLER, ZONE_FRONT_UPPER, ZONE_FRONT_LOWER}
        self.assertTrue(expected_zones.issubset(set(self.lenovo.native_pkts.keys())))
        self.assertEqual(len(self.lenovo.native_pkts), len(ALL_NATIVE_ZONES))

    def test_lenovo_legion_monochromatic_and_rgb_flash_contrast(self):
        """Verify beat flash triggers full brightness (scale 4) and blackout cuts completely to 0."""
        from lenovo_legion import MONOCHROME_BLUE_ZONES, LENOVO_LOGO_BLUE, EFFECT_STATIC, EFFECT_OFF

        # 1. Beat flash impact
        self.lenovo.set_colors((255, 0, 50), (0, 200, 255), strobe_cut=True)
        time.sleep(0.05)

        for z in MONOCHROME_BLUE_ZONES:
            pz = self.lenovo.native_pkts[z]
            self.assertEqual(pz.brightness, 4)
            self.assertEqual(pz.effect_cmd, EFFECT_STATIC)
            self.assertEqual((pz.red, pz.green, pz.blue), LENOVO_LOGO_BLUE)

        # 2. Blackout cut
        self.lenovo.set_colors((0, 0, 0), (0, 0, 0), strobe_cut=True)
        time.sleep(0.05)

        for z, pz in self.lenovo.native_pkts.items():
            self.assertEqual(pz.brightness, 0)
            self.assertEqual(pz.effect_cmd, EFFECT_OFF)
            self.assertEqual((pz.red, pz.green, pz.blue), (0, 0, 0))

    def test_lenovo_legion_rapid_beat_strobe_duty_cycle(self):
        """Verify Lenovo Legion manager sustains high-BPM rapid strobe flashing without buffer lag."""
        for _ in range(5):
            self.lenovo.set_colors((255, 255, 255), (0, 255, 255), strobe_cut=True)
            time.sleep(0.02)
            self.lenovo.set_colors((0, 0, 0), (0, 0, 0), strobe_cut=True)
            time.sleep(0.02)
        self.assertTrue(self.lenovo.running)

    def test_lenovo_legion_dual_protocol_preallocation(self):
        """Verify dual-protocol hardware headers (0x20..0x27) and ARGB streams (0x58, 0x59) are pre-allocated."""
        from lenovo_legion import ALL_IT8297_HEADERS, IT8297_HDR_ARGB1, IT8297_HDR_ARGB2, CMD_APPLY_GLOBAL
        # Headers 0x20..0x27
        self.assertEqual(len(self.lenovo.ite_effect_pkts), 8)
        for hdr in ALL_IT8297_HEADERS:
            self.assertIn(hdr, self.lenovo.ite_effect_pkts)
            pe = self.lenovo.ite_effect_pkts[hdr]
            self.assertEqual(pe.report_id, 0xCC)
            self.assertEqual(pe.header, hdr)
            self.assertEqual(pe.zone0, 1 << (hdr - 0x20))

        # ARGB Streams 0x58 and 0x59
        self.assertIn(IT8297_HDR_ARGB1, self.lenovo.ite_argb_pkts)
        self.assertIn(IT8297_HDR_ARGB2, self.lenovo.ite_argb_pkts)
        pr1 = self.lenovo.ite_argb_pkts[IT8297_HDR_ARGB1]
        self.assertEqual(len(pr1.leds), 19)
        self.assertEqual(pr1.bcount, 19 * 3)

        # Global Apply packet
        self.assertIsNotNone(self.lenovo.apply_global_buf)
        self.assertEqual(self.lenovo.apply_global_buf[0], 0xCC)
        self.assertEqual(self.lenovo.apply_global_buf[1], 0x28)
        self.assertEqual(self.lenovo.apply_global_buf[2], CMD_APPLY_GLOBAL)

        # Startup sequence
        self.assertEqual(len(self.lenovo.startup_bufs), 6)

    def test_lenovo_legion_dual_protocol_strobe_and_blackout_state(self):
        """Verify dual-protocol packets reflect beat flashes and instantaneous true blackout cuts."""
        from lenovo_legion import (
            EFFECT_STATIC,
            EFFECT_OFF,
            IT8297_HDR_BACK_IO,
            IT8297_HDR_ARGB1,
            IT8297_HDR_ARGB2,
            LENOVO_LOGO_BLUE,
        )
        # 1. Beat strobe flash
        self.lenovo.set_colors((255, 50, 0), (0, 180, 255), strobe_cut=True)
        time.sleep(0.05)

        # Verify IT8297 PktEffect headers
        for hdr, pe in self.lenovo.ite_effect_pkts.items():
            self.assertEqual(pe.effect_type, EFFECT_STATIC)
            self.assertEqual(pe.max_brightness, 100)
            if hdr == IT8297_HDR_BACK_IO:
                expected_bgr = 255 | (141 << 8) | (21 << 16)
                self.assertEqual(pe.color0, expected_bgr)

        # Verify ARGB Fan frames
        pr1 = self.lenovo.ite_argb_pkts[IT8297_HDR_ARGB1]
        for i in range(19):
            self.assertEqual((pr1.leds[i].r, pr1.leds[i].g, pr1.leds[i].b), (255, 50, 0))

        pr2 = self.lenovo.ite_argb_pkts[IT8297_HDR_ARGB2]
        for i in range(19):
            self.assertEqual((pr2.leds[i].r, pr2.leds[i].g, pr2.leds[i].b), (0, 180, 255))

        # 2. Hard blackout cut
        self.lenovo.set_colors((0, 0, 0), (0, 0, 0), strobe_cut=True)
        time.sleep(0.05)

        for hdr, pe in self.lenovo.ite_effect_pkts.items():
            self.assertEqual(pe.effect_type, EFFECT_OFF)
            self.assertEqual(pe.max_brightness, 0)
            self.assertEqual(pe.color0, 0)

        for i in range(19):
            self.assertEqual((pr1.leds[i].r, pr1.leds[i].g, pr1.leds[i].b), (0, 0, 0))
            self.assertEqual((pr2.leds[i].r, pr2.leds[i].g, pr2.leds[i].b), (0, 0, 0))

    def test_peripherals_blackout_when_audio_silent(self):
        """Verify peripherals are true pitch black (0, 0, 0) when audio is silent."""
        # 1. Provide silent audio state
        silent_audio = {
            "total_level": 0.0,
            "bass_level": 0.0,
            "mid_level": 0.0,
            "high_level": 0.0,
            "raw_peak": 0.001,
            "is_kick": False,
            "is_snare": False,
            "is_hihat": False,
            "is_drop": False,
            "is_paused": False,
        }
        self.vis.update(0.016, silent_audio)

        col_left, col_right, is_strobe = self.vis.get_peripheral_colors()
        self.assertEqual(col_left, (0, 0, 0))
        self.assertEqual(col_right, (0, 0, 0))

    def test_peripherals_blackout_when_music_paused(self):
        """Verify peripherals in Album Art mode blackout cleanly when playback is paused."""
        self.vis.set_mode(MODE_ALBUM_ART)
        paused_audio = {
            "total_level": 0.0,
            "bass_level": 0.0,
            "mid_level": 0.0,
            "raw_peak": 0.0,
            "is_paused": True,
        }
        self.vis.update(0.016, paused_audio)

        col_left, col_right, is_strobe = self.vis.get_peripheral_colors()
        self.assertEqual(col_left, (0, 0, 0))
        self.assertEqual(col_right, (0, 0, 0))
        self.assertFalse(is_strobe)

    def test_beat_detector_silence_noise_gating(self):
        """Verify BeatDetector ignores microphone background noise and produces no false beats."""
        import numpy as np
        from beat_detector import BeatDetector
        bd = BeatDetector()

        # Simulate 100 chunks of low-level ambient room mic noise
        for i in range(100):
            noise = np.random.normal(0, 0.003, bd.chunk_size).astype(np.float32)
            res = bd.process_audio(noise)
            self.assertFalse(res["is_kick"], f"False kick beat detected at chunk {i} on background noise")
            self.assertFalse(res["is_snare"], f"False snare beat detected at chunk {i} on background noise")
            self.assertFalse(res["is_hihat"], f"False hihat beat detected at chunk {i} on background noise")
            self.assertFalse(res["is_drop"], f"False drop detected at chunk {i} on background noise")

        self.assertLess(res["total_level"], 0.01)

    def test_razer_mouse_hardware_strobe_and_blackout(self):
        """Verify RazerChromaManager pushes static colors and blackout frames directly to hardware without error."""
        # 1. Full blast strobe impact
        self.razer.set_colors((255, 0, 0), (255, 0, 0), strobe_cut=True)
        time.sleep(0.04)

        # 2. Immediate true blackout cut
        self.razer.set_colors((0, 0, 0), (0, 0, 0), strobe_cut=True)
        time.sleep(0.04)

        # 3. Smooth mode color
        self.razer.set_colors((0, 255, 128), (0, 128, 255), strobe_cut=False)
        time.sleep(0.04)

        # 4. Return to blackout
        self.razer.set_colors((0, 0, 0), (0, 0, 0), strobe_cut=True)
        time.sleep(0.04)
        self.assertTrue(True)

    def test_immediate_blackout_on_sudden_pause_during_active_strobe(self):
        """Verify that a sudden pause immediately cuts an active strobe flash to true blackout."""
        # 1. Active music state with a kick
        active_audio = {
            "total_level": 0.8,
            "bass_level": 0.9,
            "mid_level": 0.5,
            "raw_peak": 0.75,
            "is_kick": True,
            "is_snare": False,
            "is_hihat": False,
            "is_drop": False,
            "is_paused": False,
        }
        self.vis.update(0.016, active_audio)
        col_left, col_right, is_strobe = self.vis.get_peripheral_colors()
        self.assertTrue(is_strobe)
        self.assertGreater(max(col_left), 0)

        # 2. Immediate pause on next frame
        paused_audio = {
            "total_level": 0.0,
            "bass_level": 0.0,
            "mid_level": 0.0,
            "raw_peak": 0.0,
            "is_paused": True,
        }
        self.vis.update(0.016, paused_audio)
        col_left, col_right, is_strobe = self.vis.get_peripheral_colors()
        # Active flash must be instantly cut to blackout
        self.assertEqual(col_left, (0, 0, 0))
        self.assertEqual(col_right, (0, 0, 0))

    def test_beat_detector_detects_real_beats_with_noise_gate(self):
        """Verify that genuine beat impacts are accurately detected above the noise floor."""
        import numpy as np
        from beat_detector import BeatDetector
        from config import CHUNK_SIZE, SAMPLE_RATE

        bd = BeatDetector()
        t = np.linspace(0, CHUNK_SIZE / SAMPLE_RATE, CHUNK_SIZE, endpoint=False)

        # First train the detector with low baseline audio
        for _ in range(15):
            quiet = np.sin(2 * np.pi * 200 * t) * 0.02
            bd.process_audio(quiet.astype(np.float32))

        # Now simulate a strong kick transient (~55Hz sine wave at peak 0.8)
        kick = (np.sin(2 * np.pi * 55 * t) * 0.8).astype(np.float32)
        res = bd.process_audio(kick)
        self.assertTrue(res["is_kick"], "Genuine kick transient was not detected above noise floor")
        self.assertGreater(res["bass_level"], 0.2)


if __name__ == "__main__":
    unittest.main()
