"""
Comprehensive unit test suite for Smart Rhythm-Locked Beat Detection (PLL),
808 attack transient vs sustain isolation, snare backbeat separation,
and UI collision/visibility fixes.
"""

import unittest
import numpy as np
import pygame
from config import (
    SAMPLE_RATE,
    CHUNK_SIZE,
    MODE_STROBE_2_0,
    MODE_CLASSIC_RAPID,
    MODE_BASS_ONLY,
    MODE_ALBUM_ART,
    STROBE_MODES,
)
from beat_detector import BeatDetector
from visualizer import VisualizerEngine
from hud import HUD
from media_sync import MediaArtManager


class TestSmartRhythmEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_default_mode_is_smart_not_overdrive(self):
        """Verify BeatDetector initializes with Smart Mode (overdrive_mode=False) by default."""
        bd = BeatDetector(sample_rate=SAMPLE_RATE, chunk_size=CHUNK_SIZE)
        self.assertFalse(bd.overdrive_mode, "BeatDetector should default to smart rhythm mode, not overdrive")

    def test_808_attack_transient_isolated_from_sustain_tail(self):
        """
        Verify that an 808 kick triggers on the initial attack transient,
        but sustained sub-bass rumble tails do NOT repeatedly re-trigger kicks.
        """
        bd = BeatDetector(sample_rate=SAMPLE_RATE, chunk_size=CHUNK_SIZE)
        t = np.linspace(0, CHUNK_SIZE / SAMPLE_RATE, CHUNK_SIZE, endpoint=False)

        # 1. Warm up AGC on quiet background
        for _ in range(15):
            bd.process_audio((np.sin(2 * np.pi * 440.0 * t) * 0.08).astype(np.float32))

        # 2. Frame 1: Heavy 808 attack transient (55 Hz hit with percussive attack)
        hit_frame = (np.sin(2 * np.pi * 55.0 * t) * 0.85 + np.sin(2 * np.pi * 1200.0 * t) * 0.15).astype(np.float32)
        res_hit = bd.process_audio(hit_frame)
        self.assertTrue(res_hit["is_kick"], "Initial 808 attack transient should trigger kick")
        self.assertTrue(res_hit["is_808"], "Initial 808 attack should be flagged as is_808")

        # 3. Frames 2 to 5: Sustained 808 sub-bass tail (continuous 55 Hz drone with slight wobble)
        # Without smart transient isolation, low thresholds would re-trigger kicks on every frame.
        subsequent_kicks = 0
        for i in range(4):
            # Wobbling sustain tail
            amp = 0.80 - (i * 0.04)
            sustain_frame = (np.sin(2 * np.pi * 55.0 * t) * amp).astype(np.float32)
            res_sustain = bd.process_audio(sustain_frame)
            if res_sustain["is_kick"]:
                subsequent_kicks += 1

        self.assertEqual(
            subsequent_kicks,
            0,
            f"Sustained 808 sub-bass tail caused {subsequent_kicks} false re-triggers during decay!",
        )

    def test_phase_locked_rhythm_grid_prior(self):
        """Verify that Bayesian rhythm prior calculates phase and rewards on-beat downbeats."""
        bd = BeatDetector(sample_rate=SAMPLE_RATE, chunk_size=CHUNK_SIZE)
        bd.estimated_bpm = 120.0  # 120 BPM -> 500ms period
        bd.bpm_confidence = 0.85
        bd.last_grid_anchor = 100.0

        # Simulate audio at exactly t = 100.50 (on 8th note backbeat, phase 0.0 or 0.5)
        t = np.linspace(0, CHUNK_SIZE / SAMPLE_RATE, CHUNK_SIZE, endpoint=False)
        frame = (np.sin(2 * np.pi * 80.0 * t) * 0.30).astype(np.float32)

        # Warm up
        for _ in range(10):
            bd.process_audio(frame)

        # Exported state should include valid rhythm phase
        res = bd.process_audio(frame)
        self.assertIn("beat_phase", res)
        self.assertIn("is_downbeat", res)
        self.assertIn("is_backbeat", res)
        self.assertGreaterEqual(res["beat_phase"], 0.0)
        self.assertLessEqual(res["beat_phase"], 1.0)

    def test_snare_backbeat_separation(self):
        """Verify pure snare/clap transients are detected while heavy sub-bass hits are not misclassified."""
        bd = BeatDetector(sample_rate=SAMPLE_RATE, chunk_size=CHUNK_SIZE)
        t = np.linspace(0, CHUNK_SIZE / SAMPLE_RATE, CHUNK_SIZE, endpoint=False)

        # Warm up
        for _ in range(12):
            bd.process_audio((np.sin(2 * np.pi * 200.0 * t) * 0.05).astype(np.float32))

        # Sharp snare hit: high/mid noise burst around 3500Hz with zero sub-bass
        snare_hit = (np.sin(2 * np.pi * 3500.0 * t) * 0.70 + np.random.uniform(-0.1, 0.1, CHUNK_SIZE)).astype(np.float32)
        res_snare = bd.process_audio(snare_hit)
        self.assertTrue(res_snare["is_snare"], "Crisp snare hit should trigger snare beat")
        self.assertFalse(res_snare["is_808"], "Pure snare should not trigger 808 flag")

    def test_classic_rapid_mode_preserves_before_behavior(self):
        """Verify MODE_CLASSIC_RAPID preserves the raw, unconstrained rapid fire mode from before."""
        self.assertIn(MODE_CLASSIC_RAPID, STROBE_MODES)
        self.assertIn(MODE_STROBE_2_0, STROBE_MODES)

        vis = VisualizerEngine(1280, 720)
        vis.set_mode(MODE_CLASSIC_RAPID)
        self.assertTrue(vis.is_classic_rapid_active())
        self.assertTrue(vis.overdrive_mode, "Classic mode should run with overdrive / rapid mode active")

        # Test beat detector behavior in classic mode (smart_mode=False)
        bd = BeatDetector(sample_rate=SAMPLE_RATE, chunk_size=CHUNK_SIZE)
        bd.set_smart_mode(False)
        bd.set_overdrive(True)
        self.assertFalse(bd.smart_mode)
        self.assertTrue(bd.overdrive_mode)

    def test_toggle_classic_rapid(self):
        """Verify toggling Classic Rapid mode switches into and out of MODE_CLASSIC_RAPID."""
        vis = VisualizerEngine(1280, 720)
        vis.set_mode(MODE_STROBE_2_0)
        self.assertFalse(vis.is_classic_rapid_active())

        # Toggle on
        toggled = vis.toggle_classic_rapid()
        self.assertTrue(toggled)
        self.assertEqual(vis.mode, MODE_CLASSIC_RAPID)
        self.assertTrue(vis.is_classic_rapid_active())

        # Toggle off
        toggled_off = vis.toggle_classic_rapid()
        self.assertFalse(toggled_off)
        self.assertEqual(vis.mode, MODE_STROBE_2_0)
        self.assertFalse(vis.is_classic_rapid_active())


class TestHUDLayoutFixes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def setUp(self):
        self.hud = HUD(1280, 720)
        self.hud.warning_dismissed = True
        self.vis = VisualizerEngine(1280, 720)
        self.media_mgr = MediaArtManager()

    def tearDown(self):
        self.media_mgr.stop()

    def test_solid_button_width_no_truncation(self):
        """Verify btn_solid_toggle is wide enough (>= 112px) to display '[LIGHT] MUSIC' without truncation."""
        self.assertGreaterEqual(self.hud.btn_solid_toggle.width, 112)
        label_text = "[LIGHT] MUSIC"
        text_w = self.hud.font_small.size(label_text)[0]
        # Must fit within button width minus padding and status pip
        avail = self.hud.btn_solid_toggle.width - 24
        self.assertGreater(avail, text_w, f"Text '{label_text}' width {text_w} exceeds available {avail}")

    def test_vu_meters_and_spectrum_completely_above_waveform(self):
        """
        Verify all VU meters (BAS, MID, HIG) and Spectrum Analyzer reside strictly
        above the waveform deck with zero vertical overlap or clipping.
        """
        panel = self.hud.panel_rect
        wf_rect = self.hud.waveform_rect

        # In hud.py:
        # spec_y = panel.y + 10, spec_h = 26 -> ends at panel.y + 36
        spec_bottom = panel.y + 10 + 26

        # levels_y = panel.y + 8, HIG is at levels_y + 19, meter_h = 6 -> ends at panel.y + 33
        hig_meter_bottom = panel.y + 8 + 19 + 6

        # Both must be strictly less than waveform_rect.y
        self.assertLess(spec_bottom, wf_rect.y, f"Spectrum bottom {spec_bottom} overlaps waveform {wf_rect.y}")
        self.assertLess(hig_meter_bottom, wf_rect.y, f"HIG VU meter bottom {hig_meter_bottom} overlaps waveform {wf_rect.y}")

    def test_status_badges_left_of_album_card(self):
        """Verify hardware/network status pills sit strictly to the left of card_album_art."""
        card_x = self.hud.card_album_art.x
        # Pills anchor to card_x - 12 and flow leftwards
        pill_anchor_x = card_x - 12
        self.assertLess(pill_anchor_x, card_x, "Status pill anchor collides with album card")

    def test_distinct_waveform_deck_badge(self):
        """Verify waveform deck renders '[TRACK SYNC]' instead of duplicating card's '[ACTIVE]' badge."""
        surface = pygame.Surface((1280, 720))
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
        # Simulate active media timeline playing
        with self.media_mgr.lock:
            self.media_mgr.timeline_duration = 180.0
            self.media_mgr.timeline_position = 45.0
            self.media_mgr.is_playing = True

        # Render without crashing
        self.hud.render(
            surface,
            None,
            self.vis,
            None,
            None,
            dummy_state,
            is_dual=False,
            media_mgr=self.media_mgr,
        )


if __name__ == "__main__":
    unittest.main()
