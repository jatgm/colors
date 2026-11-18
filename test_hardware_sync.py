"""
Hardware Synchronization Verification Test for Album Art Color Palette.
Tests Razer Chroma, HappyLighting BLE, and Lenovo Legion RGB managers with Album Art colors.
"""

import time
import unittest
import pygame
from config import MODE_ALBUM_ART, PALETTE_ALBUM_ART, MODE_SPECTRUM, MODE_MONOCHROME
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

    def test_spotify_isolated_device_prioritized(self):
        """Verify Spotify Isolated Audio is available while System Audio loopback is default."""
        from audio_capture import AudioCaptureManager, PROCTAP_AVAILABLE
        mgr = AudioCaptureManager()
        if PROCTAP_AVAILABLE:
            self.assertIn("spotify", mgr.devices)
            self.assertTrue(any("Spotify" in name for name in mgr.device_names))
            self.assertIn("System Audio", mgr.device_names[0])

    def test_spotify_silence_reset_triggers_blackout(self):
        """Verify _reset_to_silence clears all levels and triggers blackout."""
        from audio_capture import AudioCaptureManager
        mgr = AudioCaptureManager()
        # Set some active states
        with mgr.lock:
            mgr.latest_state["is_kick"] = True
            mgr.latest_state["bass_level"] = 0.95
            mgr.latest_state["total_level"] = 0.90
            mgr.latest_state["bpm"] = 128.0

        # Reset to silence
        mgr._reset_to_silence()
        st = mgr.get_latest_state()
        self.assertFalse(st["is_kick"])
        self.assertEqual(st["bass_level"], 0.0)
        self.assertEqual(st["total_level"], 0.0)
    def test_happylighting_dual_channel_selection(self):
        """Verify HappyLightingManager selects the active flashing channel in alternating multi-monitor setups."""
        # 1. Left is black, right is cyan flash -> should select right channel
        self.happy.set_colors((0, 0, 0), (0, 240, 255), strobe_cut=True)
        with self.happy.lock:
            self.assertEqual(self.happy._target_color, (0, 240, 255))

        # 2. Left is magenta flash, right is black -> should select left channel
        self.happy.set_colors((255, 0, 128), (0, 0, 0), strobe_cut=True)
        with self.happy.lock:
            self.assertEqual(self.happy._target_color, (255, 0, 128))

        # 3. Both equal -> primary channel preserved
        self.happy.set_colors((255, 100, 50), (255, 100, 50), strobe_cut=True)
        with self.happy.lock:
            self.assertEqual(self.happy._target_color, (255, 100, 50))

    def test_happylighting_consecutive_beat_edge_detection(self):
        """Verify consecutive beats on the same color increment flash trigger ID and are not dropped."""
        # Beat 1 (Red)
        self.happy.set_colors((255, 0, 0), strobe_cut=True)
        with self.happy.lock:
            id1 = self.happy._flash_trigger_id
        self.assertGreater(id1, 0)

        # Blackout cut
        self.happy.set_colors((0, 0, 0), strobe_cut=True)

        # Beat 2 (Red again - same color!)
        self.happy.set_colors((255, 0, 0), strobe_cut=True)
        with self.happy.lock:
            id2 = self.happy._flash_trigger_id
        self.assertGreater(id2, id1, "Consecutive beat with identical color failed to register edge trigger")

    def test_peripheral_spectrum_mode_color_matching(self):
        """Verify peripheral colors in Spectrum mode match audio frequency synthesis rather than palette."""
        self.vis.set_mode(MODE_SPECTRUM)
        # Heavy bass audio state (low mid, low high)
        bass_audio = {
            "total_level": 0.8,
            "bass_level": 0.95,
            "mid_level": 0.1,
            "high_level": 0.05,
            "raw_peak": 0.85,
            "is_kick": True,
            "is_snare": False,
            "is_hihat": False,
            "is_drop": False,
            "is_paused": False,
        }
        surf = pygame.Surface((100, 100))
        self.vis.render(surf, bass_audio)
        self.vis.trigger_kick()

        col_left, col_right, is_strobe = self.vis.get_peripheral_colors()
        self.assertTrue(is_strobe)
        # In spectrum bass kick, red component should dominate
        r, g, b = col_left
        self.assertGreater(r, g)
        self.assertGreater(r, b)

    def test_peripheral_monochrome_mode_white_matching(self):
        """Verify peripheral colors in Monochrome mode produce pure white rather than colorful palette hues."""
        self.vis.set_mode(MODE_MONOCHROME)
        self.vis.trigger_kick()

        col_left, col_right, is_strobe = self.vis.get_peripheral_colors()
        self.assertTrue(is_strobe)
        # Must be pure white (all channels equal to 255)
        self.assertEqual(col_left, (255, 255, 255))
        self.assertEqual(col_right, (255, 255, 255))

    def test_peripheral_hihat_sparkle_micro_flash(self):
        """Verify hi-hat sparkle triggers peripheral micro-flash window."""
        self.vis.trigger_hihat()
        col_left, col_right, is_strobe = self.vis.get_peripheral_colors()
        self.assertTrue(is_strobe)
        self.assertGreater(max(col_left), 0)

    def test_happylighting_flash_id_tracking_without_blackout(self):
        """Verify HappyLighting recognizes consecutive beats with identical color via flash_id."""
        self.happy.set_colors((0, 255, 128), strobe_cut=True, flash_id=1)
        with self.happy.lock:
            id1 = self.happy._flash_trigger_id

        # Second beat with identical color, NO intervening blackout, incremented flash_id
        self.happy.set_colors((0, 255, 128), strobe_cut=True, flash_id=2)
        with self.happy.lock:
            id2 = self.happy._flash_trigger_id

        self.assertGreater(id2, id1, "Consecutive beat with identical color failed to register edge trigger via flash_id")

    def test_happylighting_ambient_to_strobe_transition(self):
        """Verify transition from ambient glow to beat strobe triggers a flash pulse even with identical color."""
        # Ambient mode with color
        self.happy.set_colors((255, 80, 20), strobe_cut=False)
        with self.happy.lock:
            id1 = self.happy._flash_trigger_id

        # Beat strobe strikes with the same color
        self.happy.set_colors((255, 80, 20), strobe_cut=True)
        with self.happy.lock:
            id2 = self.happy._flash_trigger_id

        self.assertGreater(id2, id1, "Ambient to strobe transition failed to trigger beat strike")

    def test_dual_alternating_strobe_channel_isolation(self):
        """Verify DUAL_SCHEME_ALTERNATING sets the idle monitor to blackout and active monitor to flash."""
        from visualizer import DUAL_SCHEME_ALTERNATING
        self.vis.dual_scheme = DUAL_SCHEME_ALTERNATING

        # Beat 1: Side 0 (Left)
        self.vis.alternating_side = 1  # will become 0 on trigger_kick
        self.vis.trigger_kick()
        self.assertEqual(self.vis.alternating_side, 0)
        col_left, col_right, is_strobe = self.vis.get_peripheral_colors()
        self.assertTrue(is_strobe)
        self.assertGreater(max(col_left), 0)
        self.assertEqual(col_right, (0, 0, 0))

        # Beat 2: Side 1 (Right)
        self.vis.trigger_kick()
        self.assertEqual(self.vis.alternating_side, 1)
        col_left, col_right, is_strobe = self.vis.get_peripheral_colors()
        self.assertTrue(is_strobe)
        self.assertEqual(col_left, (0, 0, 0))
        self.assertGreater(max(col_right), 0)

    def test_burst_train_chopped_blackout_peripherals(self):
        """Verify peripherals chop to blackout during off-phases of multi-pulse burst trains."""
        self.vis.trigger_kick()
        # In flash phase
        col_left, col_right, is_strobe = self.vis.get_peripheral_colors()
        self.assertGreater(max(col_left), 0)

        # Force burst chop off-phase
        self.vis.burst_remaining = 3
        self.vis.burst_is_on = False
        col_left, col_right, is_strobe = self.vis.get_peripheral_colors()
        self.assertEqual(col_left, (0, 0, 0))
        self.assertEqual(col_right, (0, 0, 0))

    def test_contrast_mode_channel_alternation(self):
        """Verify contrast mode with two distinct saturated colors alternates active channel across beats."""
        self.happy._contrast_toggle = 0
        # Beat 1
        self.happy.set_colors((255, 0, 0), (0, 0, 255), strobe_cut=True, flash_id=10)
        with self.happy.lock:
            col1 = self.happy._target_color

        # Beat 2
        self.happy.set_colors((255, 0, 0), (0, 0, 255), strobe_cut=True, flash_id=11)
        with self.happy.lock:
            col2 = self.happy._target_color

        self.assertNotEqual(col1, col2)
        self.assertIn(col1, [(255, 0, 0), (0, 0, 255)])
        self.assertIn(col2, [(255, 0, 0), (0, 0, 255)])

    def test_govee_ble_packet_constructors(self):
        """Verify Govee BLE 20-byte packet structure and XOR checksum calculation."""
        from happylighting import make_govee_color_packet, make_govee_power_packet

        # 1. Color packet
        pkt_col = make_govee_color_packet(255, 120, 60)
        self.assertEqual(len(pkt_col), 20)
        self.assertEqual(pkt_col[0], 0x33)
        self.assertEqual(pkt_col[1], 0x05)
        self.assertEqual(pkt_col[2], 0x02)
        self.assertEqual(pkt_col[3], 255)
        self.assertEqual(pkt_col[4], 120)
        self.assertEqual(pkt_col[5], 60)
        # Verify XOR checksum
        cs = 0
        for b in pkt_col[:19]:
            cs ^= b
        self.assertEqual(pkt_col[19], cs)

        # 2. Power packet
        pkt_pwr = make_govee_power_packet(True)
        self.assertEqual(len(pkt_pwr), 20)
        self.assertEqual(pkt_pwr[0], 0x33)
        self.assertEqual(pkt_pwr[1], 0x01)
        self.assertEqual(pkt_pwr[2], 0x01)
        cs_pwr = 0
        for b in pkt_pwr[:19]:
            cs_pwr ^= b
        self.assertEqual(pkt_pwr[19], cs_pwr)

    def test_peripherals_active_on_soft_audio_with_agc(self):
        """Verify peripherals remain armed and responsive when raw_peak is low but energy is present."""
        audio_soft = {
            "total_level": 0.25,
            "bass_level": 0.30,
            "mid_level": 0.20,
            "high_level": 0.15,
            "raw_peak": 0.002,
            "is_kick": True,
            "is_snare": False,
            "is_hihat": False,
            "is_drop": False,
            "is_paused": False,
        }
        self.vis.update(0.016, audio_soft)
        self.assertFalse(self.vis.is_audio_silent)
        col_left, col_right, is_strobe = self.vis.get_peripheral_colors()
        self.assertTrue(is_strobe)
        self.assertGreater(max(col_left), 0)

    def test_audio_in_strobes_when_media_manager_is_paused(self):
        """Verify YouTube / Audio In strobing is never blocked by paused background media sessions."""
        # Audio from YouTube video
        youtube_audio = {
            "total_level": 0.45,
            "bass_level": 0.50,
            "mid_level": 0.35,
            "high_level": 0.20,
            "raw_peak": 0.25,
            "is_kick": True,
            "is_snare": False,
            "is_hihat": False,
            "is_drop": False,
            "is_paused": True,  # Simulates background Spotify being in paused state
        }
        self.vis.update(0.016, youtube_audio)
        self.assertFalse(self.vis.is_audio_silent, "Live YouTube audio should not be marked silent")
        self.assertEqual(self.vis.kick_intensity, 1.0)

        col_left, col_right, is_strobe = self.vis.get_peripheral_colors()
        self.assertTrue(is_strobe)
        self.assertGreater(max(col_left), 0, "Peripheral lights should strobe on live YouTube audio")
        self.assertGreater(max(col_right), 0)


if __name__ == "__main__":
    unittest.main()

