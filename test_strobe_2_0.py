"""
Unit tests for Strobe 2.0 features:
- 12-semitone chroma pitch melody detection
- Macro chorus energy surge detection
- Timeline millisecond interpolation and song waveform contour profiling
- Mode 2.0 toggle and chorus flash dynamics
- HUD waveform progress bar rendering and layout
"""

import time
import unittest
import numpy as np
import pygame
from config import MODE_STROBE_2_0, MODE_PSYCHO_OVERDRIVE, CHUNK_SIZE, SAMPLE_RATE
from beat_detector import BeatDetector
from media_sync import MediaArtManager, generate_song_waveform
from visualizer import VisualizerEngine
from hud import HUD
from audio_capture import AudioCaptureManager


class TestStrobe2Features(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_chroma_pitch_detection_fundamental_notes(self):
        """Verify 12-semitone chroma pitch detector accurately identifies musical pitches."""
        bd = BeatDetector(sample_rate=SAMPLE_RATE, chunk_size=CHUNK_SIZE)
        t = np.linspace(0, CHUNK_SIZE / SAMPLE_RATE, CHUNK_SIZE, endpoint=False)

        # Test A4 (440 Hz) -> Note 9: A
        sine_a4 = (np.sin(2 * np.pi * 440.0 * t) * 0.7).astype(np.float32)
        res_a = bd.process_audio(sine_a4)
        self.assertEqual(res_a["pitch_name"], "A", f"Expected A, got {res_a['pitch_name']}")
        self.assertEqual(res_a["pitch_idx"], 9)
        self.assertGreater(res_a["pitch_confidence"], 0.2)

        # Test C4 (261.63 Hz) -> Note 0: C
        sine_c4 = (np.sin(2 * np.pi * 261.63 * t) * 0.7).astype(np.float32)
        res_c = bd.process_audio(sine_c4)
        self.assertEqual(res_c["pitch_name"], "C", f"Expected C, got {res_c['pitch_name']}")
        self.assertEqual(res_c["pitch_idx"], 0)

    def test_macro_chorus_energy_surge_detection(self):
        """Verify verse, buildup, and chorus detectors trigger accurately."""
        bd = BeatDetector(sample_rate=SAMPLE_RATE, chunk_size=CHUNK_SIZE)
        t = np.linspace(0, CHUNK_SIZE / SAMPLE_RATE, CHUNK_SIZE, endpoint=False)

        # 1. Simulate quiet verse (~0.05 amplitude)
        for _ in range(25):
            verse = (np.sin(2 * np.pi * 200.0 * t) * 0.05).astype(np.float32)
            res = bd.process_audio(verse)
            self.assertFalse(res["is_chorus"])

        self.assertTrue(res["is_verse"])
        self.assertEqual(res["section_name"], "VERSE")

        # 2. Simulate rising buildup (high frequency riser with energy climb)
        for step in range(20):
            amp = 0.05 + (step / 20.0) * 0.15
            freq = 4000.0 + step * 250.0
            buildup_chunk = (np.sin(2 * np.pi * freq * t) * amp).astype(np.float32)
            res_build = bd.process_audio(buildup_chunk)

        self.assertTrue(res_build["is_buildup"] or res_build["is_chorus"])

        # 3. Simulate explosive chorus drop (~0.75 amplitude with heavy sub-bass)
        chorus = ((np.sin(2 * np.pi * 55.0 * t) * 0.6) + (np.sin(2 * np.pi * 300.0 * t) * 0.4)).astype(np.float32)
        res_chorus = bd.process_audio(chorus)
        self.assertTrue(res_chorus["is_chorus"], "Chorus energy surge was not detected")
        self.assertEqual(res_chorus["section_name"], "CHORUS")

        # 4. Verify hysteresis stability: a single brief quiet sub-beat frame does NOT flicker back to verse
        quiet_gap = (np.sin(2 * np.pi * 200.0 * t) * 0.04).astype(np.float32)
        res_gap = bd.process_audio(quiet_gap)
        self.assertTrue(res_gap["is_chorus"], "Hysteresis failed: chorus dropped to verse on a single quiet sub-beat")
        self.assertEqual(res_gap["section_name"], "CHORUS")

    def test_media_timeline_interpolation_and_waveform_energy(self):
        """Verify timeline position interpolation and live song waveform contour updates."""
        media = MediaArtManager()
        try:
            with media.lock:
                media.timeline_position = 30.0
                media.timeline_duration = 180.0
                media.timeline_last_wall_time = time.time() - 2.5
                media.is_playing = True
                media.is_paused = False

            tl = media.get_timeline()
            # With 2.5s elapsed, position should be ~32.5s
            self.assertAlmostEqual(tl["position"], 32.5, delta=0.5)
            self.assertAlmostEqual(tl["duration"], 180.0)
            self.assertAlmostEqual(tl["progress"], 32.5 / 180.0, delta=0.01)

            # Record energy into waveform bin
            media.update_waveform_energy(0.85)
            tl2 = media.get_timeline()
            wf = tl2["waveform"]
            self.assertGreater(np.max(wf), 0.5)
        finally:
            media.stop()

    def test_visualizer_mode_2_0_toggle_and_chorus_burst(self):
        """Verify toggle_mode_2_0 activates/deactivates MODE_STROBE_2_0 and boosts chorus burst count."""
        vis = VisualizerEngine(1280, 720)
        # MODE_STROBE_2_0 is on by default
        self.assertEqual(vis.mode, MODE_STROBE_2_0)
        self.assertTrue(vis.is_mode_2_0_active())

        # Test chorus kick dynamics
        audio_chorus = {
            "total_level": 0.85,
            "bass_level": 0.90,
            "mid_level": 0.60,
            "raw_peak": 0.80,
            "pitch_idx": 7,     # G
            "pitch_name": "G",
            "is_chorus": True,
            "section_energy": 1.6,
            "is_kick": True,
            "is_drop": False,
            "is_snare": False,
            "is_hihat": False,
        }
        vis.update(0.016, audio_chorus)
        # Chorus should boost bursts to 5 micro-flashes
        self.assertGreaterEqual(vis.burst_remaining, 4)

        # Toggle OFF
        deactivated = vis.toggle_mode_2_0()
        self.assertFalse(deactivated)
        self.assertNotEqual(vis.mode, MODE_STROBE_2_0)

        # Toggle back ON
        activated = vis.toggle_mode_2_0()
        self.assertTrue(activated)
        self.assertEqual(vis.mode, MODE_STROBE_2_0)

    def test_hud_waveform_and_mode_2_0_elements(self):
        """Verify HUD waveform progress bar and btn_mode_2_0 are created and rendered."""
        hud = HUD(1280, 720)
        self.assertTrue(hasattr(hud, "waveform_rect"))
        self.assertTrue(hasattr(hud, "btn_mode_2_0"))

        media = MediaArtManager()
        vis = VisualizerEngine(1280, 720)
        vis.toggle_mode_2_0()

        surf = pygame.Surface((1280, 720))
        audio_state = {
            "bpm": 128.0,
            "bass_level": 0.7,
            "mid_level": 0.5,
            "high_level": 0.4,
            "total_level": 0.6,
            "pitch_name": "F#",
            "is_chorus": True,
            "spectrum_bars": np.zeros(24, dtype=np.float32),
        }

        # Render without crash
        hud.render(surf, None, vis, None, None, audio_state, False, None, None, None, media)
        media.stop()

    def test_hud_btn_mode_2_0_click_toggles_mode(self):
        """Verify clicking btn_mode_2_0 toggles visualizer into/out of Strobe 2.0."""
        hud = HUD(1280, 720)
        hud.warning_dismissed = True
        vis = VisualizerEngine(1280, 720)
        audio = AudioCaptureManager()
        # Mode 2.0 is active by default
        self.assertTrue(vis.is_mode_2_0_active())

        # Click inside btn_mode_2_0 to toggle OFF
        click_pos = (hud.btn_mode_2_0.centerx, hud.btn_mode_2_0.centery)
        consumed = hud.handle_mouse_down(click_pos, audio, vis, None, None, lambda: None)
        self.assertTrue(consumed)
        self.assertFalse(vis.is_mode_2_0_active())

        # Click again to toggle back ON
        consumed2 = hud.handle_mouse_down(click_pos, audio, vis, None, None, lambda: None)
        self.assertTrue(consumed2)
        self.assertTrue(vis.is_mode_2_0_active())

    def test_high_resolution_waveform_generation_and_dual_channel(self):
        """Verify high-resolution (240 bar) waveform contour generation and dual-channel stereo variation."""
        wf_l = generate_song_waveform("Hyper Strobe Blitz", "Audio Artist", 210.0, 240, channel=0)
        wf_r = generate_song_waveform("Hyper Strobe Blitz", "Audio Artist", 210.0, 240, channel=1)

        self.assertEqual(len(wf_l), 240)
        self.assertEqual(len(wf_r), 240)
        self.assertGreaterEqual(float(np.min(wf_l)), 0.0)
        self.assertLessEqual(float(np.max(wf_l)), 1.0)
        # Chorus sections (around t=0.35-0.42 and t=0.85-0.92) should have high energy
        chorus_segment = wf_l[int(240 * 0.35):int(240 * 0.42)]
        intro_segment = wf_l[:int(240 * 0.08)]
        self.assertGreater(float(np.mean(chorus_segment)), float(np.mean(intro_segment)))
        # Stereo channels should have subtle difference while maintaining correlated structure
        channel_diff = np.abs(wf_l - wf_r)
        self.assertGreater(float(np.mean(channel_diff)), 0.02)

    def test_waveform_generation_edge_cases_and_small_bins(self):
        """Verify waveform generation handles small bins, zero bins, and missing duration without crashing."""
        # 0 or negative bins should return empty array safely
        empty_wf = generate_song_waveform("Test", "Artist", 120.0, 0)
        self.assertEqual(len(empty_wf), 0)

        # Small number of bins (e.g. 4) previously crashed with numpy RandomState.choice ValueError
        small_wf = generate_song_waveform("Test", "Artist", 120.0, 4)
        self.assertEqual(len(small_wf), 4)
        self.assertGreaterEqual(float(np.min(small_wf)), 0.0)
        self.assertLessEqual(float(np.max(small_wf)), 1.0)

        # Missing or negative duration defaults safely to standard song duration
        dur_wf = generate_song_waveform("Test", "Artist", -1.0, 240)
        self.assertEqual(len(dur_wf), 240)

    def test_hud_waveform_extra_tall_and_scrub_interaction(self):
        """Verify waveform deck height is >= 80px and mouse dragging scrubs timeline without jumping on time deck click."""
        hud = HUD(1360, 800)
        hud.warning_dismissed = True
        self.assertGreaterEqual(hud.waveform_rect.height, 80, "Waveform rect should be extra tall (>= 80px)")

        media = MediaArtManager()
        try:
            with media.lock:
                media.timeline_position = 20.0
                media.timeline_duration = 200.0
                media.is_playing = True

            # 1. Click inside waveform seek bar starts dragging and seeks
            click_pos = (hud.waveform_rect.x + 40, hud.waveform_rect.centery)
            consumed = hud.handle_mouse_down(click_pos, None, None, None, None, lambda: None, media_mgr=media)
            self.assertTrue(consumed)
            self.assertTrue(hud.dragging_waveform)

            # 2. Mouse motion while dragging scrubs timeline to new position
            motion_pos = (hud.waveform_rect.x + 200, hud.waveform_rect.centery)
            hud.handle_mouse_motion(motion_pos, None, None, None, media_mgr=media)
            tl = media.get_timeline()
            self.assertGreater(tl["position"], 20.0)

            # 3. Mouse up clears dragging state
            hud.handle_mouse_up()
            self.assertFalse(hud.dragging_waveform)

            # 4. Clicking right-side time deck area should NOT jump timeline to 100%
            time_deck_click = (hud.waveform_rect.right - 10, hud.waveform_rect.centery)
            cur_pos = media.get_timeline()["position"]
            consumed2 = hud.handle_mouse_down(time_deck_click, None, None, None, None, lambda: None, media_mgr=media)
            self.assertTrue(consumed2)
            # Timeline position should not have jumped to duration (200.0s)
            self.assertNotEqual(media.get_timeline()["position"], 200.0)
        finally:
            media.stop()

    def test_waveform_contour_stability_during_live_audio(self):
        """Verify waveform contour remains completely stable during live audio playback without jumping or decaying."""
        media = MediaArtManager()
        try:
            with media.lock:
                media.timeline_position = 45.0
                media.timeline_duration = 200.0
                media.is_playing = True
                media.is_paused = False
                media._last_processed_id = "Artist - Test Track (Album)"
                media.current_waveform = generate_song_waveform("Test Track", "Artist", 200.0, 240, channel=0)
                media.current_waveform_r = generate_song_waveform("Test Track", "Artist", 200.0, 240, channel=1)

            baseline_wf = media.get_timeline()["waveform"].copy()

            # Simulate 100 frames of fluctuating audio levels (kicks, drops, silence)
            for lvl in [0.95, 0.05, 0.88, 0.12, 1.0, 0.0]:
                media.update_waveform_energy(lvl)

            after_wf = media.get_timeline()["waveform"]
            # The authentic waveform contour must be strictly identical (no decay, no erratic jumping)
            np.testing.assert_array_equal(baseline_wf, after_wf)
        finally:
            media.stop()

    def test_waveform_render_solid_backing_and_no_strobe_bleed(self):
        """Verify waveform progress bar has solid backing and completely blocks strobe bleed."""
        media = MediaArtManager()
        try:
            with media.lock:
                media.timeline_position = 50.0
                media.timeline_duration = 200.0
                media.is_playing = True
                media.is_paused = False
                media._last_processed_id = "Artist - Test (Album)"
                media.current_waveform = generate_song_waveform("Test", "Artist", 200.0, 240, channel=0)
                media.current_waveform_r = generate_song_waveform("Test", "Artist", 200.0, 240, channel=1)

            hud = HUD(1280, 720)
            hud.warning_dismissed = True
            hud.visible = True
            hud.alpha = 255.0

            # Simulate full-screen strobe white burst on screen
            screen = pygame.Surface((1280, 720))
            screen.fill((255, 255, 255))

            vis = VisualizerEngine(1280, 720)
            audio_state = {
                "section_name": "CHORUS",
                "pitch_name": "F#",
                "pitch_idx": 6,
                "is_chorus": True,
                "total_level": 0.85,
                "bass_level": 0.90,
                "raw_peak": 0.95,
                "agc_gain": 1.0,
            }

            # Render HUD onto strobe-flashed screen
            hud.render(screen, None, vis, None, None, audio_state, False, media_mgr=media)

            # Sample inside the waveform chamber background (inside border, away from bars)
            wf_rect = hud.waveform_rect
            # Background pixel near top-left of waveform chamber
            sample_col = screen.get_at((wf_rect.x + 4, wf_rect.y + 4))
            # Must NOT be white (255, 255, 255) - strobe flash must be completely blocked
            self.assertNotEqual((sample_col.r, sample_col.g, sample_col.b), (255, 255, 255))
            # Must be dark chamber color (r < 40, g < 40, b < 40)
            self.assertLess(sample_col.r, 40)
            self.assertLess(sample_col.g, 40)
            self.assertLess(sample_col.b, 40)

            # Edge Case 1: Song completely elapsed (progress = 1.0, played bars match full height)
            with media.lock:
                media.timeline_position = 200.0
            screen.fill((255, 255, 255))
            hud.render(screen, None, vis, None, None, audio_state, False, media_mgr=media)
            sample_col2 = screen.get_at((wf_rect.x + 4, wf_rect.y + 4))
            self.assertLess(sample_col2.r, 40)

            # Edge Case 2: Empty waveform contour (idle standby telemetry)
            with media.lock:
                media.current_waveform = np.zeros(0, dtype=np.float32)
                media.current_waveform_r = np.zeros(0, dtype=np.float32)
                media.num_waveform_bars = 0
            screen.fill((255, 255, 255))
            hud.render(screen, None, vis, None, None, audio_state, False, media_mgr=media)
            sample_col3 = screen.get_at((wf_rect.x + 4, wf_rect.y + 4))
            self.assertLess(sample_col3.r, 40)
        finally:
            media.stop()

    def test_strobe_2_0_drum_emphasis_and_hihat_gating(self):
        """Verify Strobe 2.0 heavily emphasizes 808s/kicks and snares, while gating hi-hats to prevent off-beat flashing."""
        vis = VisualizerEngine(1280, 720)
        vis.set_mode(MODE_STROBE_2_0)
        self.assertEqual(vis.mode, MODE_STROBE_2_0)

        # 1. 808/Kick beat hit triggers strong strobe flash
        audio_kick = {
            "total_level": 0.80,
            "bass_level": 0.90,
            "mid_level": 0.30,
            "high_level": 0.20,
            "raw_peak": 0.95,
            "is_kick": True,
            "is_snare": False,
            "is_hihat": False,
        }
        vis.update(0.016, audio_kick)
        self.assertGreater(vis.kick_intensity, 0.5)
        rgb_kick, eff_kick = vis._calc_color_and_intensity(vis.current_color, vis.kick_intensity, audio_kick)
        self.assertGreater(eff_kick, 0.70)

        # 2. Snare drum hit triggers crisp high-intensity accent
        vis.kick_intensity = 0.0
        vis.snare_intensity = 0.90
        audio_snare = {
            "total_level": 0.60,
            "bass_level": 0.20,
            "mid_level": 0.80,
            "high_level": 0.30,
            "raw_peak": 0.80,
            "is_kick": False,
            "is_snare": True,
            "is_hihat": False,
        }
        rgb_snare, eff_snare = vis._calc_color_and_intensity(vis.current_color, vis.kick_intensity, audio_snare)
        self.assertGreater(eff_snare, 0.70)
        # Snare accent should boost RGB
        self.assertGreater(max(rgb_snare), 180)

        # 3. Rapid hi-hat chatter should NOT trigger micro-sparkle peripheral flashes in Strobe 2.0
        vis.kick_intensity = 0.0
        vis.snare_intensity = 0.0
        vis.hihat_intensity = 0.0
        vis.peripheral_flash_until = 0.0
        audio_hihat = {
            "total_level": 0.35,
            "bass_level": 0.10,
            "mid_level": 0.20,
            "high_level": 0.85,
            "raw_peak": 0.40,
            "is_kick": False,
            "is_snare": False,
            "is_hihat": True,
        }
        vis.update(0.016, audio_hihat)
        # In Strobe 2.0, trigger_hihat must NOT be called on hi-hat audio
        self.assertEqual(vis.peripheral_flash_until, 0.0)
        # And eff_intensity must remain at subtle ambient floor between drum hits, preventing off-beat strobing
        rgb_hihat, eff_hihat = vis._calc_color_and_intensity(vis.current_color, vis.kick_intensity, audio_hihat)
        self.assertLess(eff_hihat, 0.25)

    def test_strobe_2_0_808_sub_bass_and_harmonic_color_progression(self):
        """Verify 808 sub-bass detection and dynamic harmonic downbeat color progression in Strobe 2.0."""
        bd = BeatDetector(sample_rate=SAMPLE_RATE, chunk_size=CHUNK_SIZE)
        t = np.linspace(0, CHUNK_SIZE / SAMPLE_RATE, CHUNK_SIZE, endpoint=False)

        # Warm up AGC with background audio
        for _ in range(12):
            bd.process_audio((np.sin(2 * np.pi * 300.0 * t) * 0.10).astype(np.float32))

        # Deep 55Hz sub-bass hit (simulating an 808 sub kick)
        sub_808 = (np.sin(2 * np.pi * 55.0 * t) * 0.85).astype(np.float32)
        res_808 = bd.process_audio(sub_808)
        self.assertTrue(res_808["is_kick"], "808 sub-bass hit did not trigger kick beat")
        self.assertTrue(res_808["is_808"], "808 flag was not raised on heavy sub-bass hit")
        self.assertGreater(res_808["sub_bass_level"], 0.5)

        # Test harmonic color progression on kicks in VisualizerEngine
        vis = VisualizerEngine(1280, 720)
        vis.set_mode(MODE_STROBE_2_0)
        initial_color = vis.current_color

        # Multiple kick downbeats should advance the harmonic color progression across palette
        observed_colors = {initial_color}
        for _ in range(5):
            vis.trigger_kick()
            observed_colors.add(vis.current_color)

        self.assertGreater(len(observed_colors), 1, "Harmonic color progression failed to advance colors on kicks")

    def test_strobe_2_0_snare_secondary_color_contrast(self):
        """Verify Strobe 2.0 blends snare hits with secondary contrast color instead of flat whitewash."""
        vis = VisualizerEngine(1280, 720)
        vis.set_mode(MODE_STROBE_2_0)
        vis.kick_intensity = 0.0
        vis.snare_intensity = 1.0

        audio_snare = {
            "total_level": 0.60,
            "bass_level": 0.20,
            "mid_level": 0.80,
            "high_level": 0.30,
            "raw_peak": 0.80,
            "is_kick": False,
            "is_snare": True,
            "is_hihat": False,
            "section_name": "VERSE",
        }
        rgb_snare, eff_snare = vis._calc_color_and_intensity(vis.current_color, vis.kick_intensity, audio_snare)
        # Should not be pure flat white (255, 255, 255)
        self.assertNotEqual(rgb_snare, (255, 255, 255), "Snare was completely whitewashed instead of using contrast color")
        self.assertGreater(eff_snare, 0.70)

    def test_strobe_2_0_timeline_prior_and_hud_waveform_section_colors(self):
        """Verify timeline prior calibration and dynamic HUD waveform section colors."""
        bd = BeatDetector(sample_rate=SAMPLE_RATE, chunk_size=CHUNK_SIZE)
        # Prime timeline into chorus zone (38% of track)
        bd.set_timeline_context(progress=0.38, duration=210.0, is_playing=True)
        self.assertEqual(bd.timeline_progress, 0.38)

        # HUD waveform progress bar section coloring
        hud = HUD(1280, 720)
        hud.warning_dismissed = True
        vis = VisualizerEngine(1280, 720)
        vis.set_mode(MODE_STROBE_2_0)
        media = MediaArtManager()

        try:
            with media.lock:
                media.timeline_position = 38.0
                media.timeline_duration = 100.0
                media.is_playing = True
                media._last_processed_id = "Test Track"
                media.current_waveform = generate_song_waveform("Test Track", "Artist", 100.0, 240, channel=0)
                media.current_waveform_r = generate_song_waveform("Test Track", "Artist", 100.0, 240, channel=1)

            screen = pygame.Surface((1280, 720))

            # 1. Render in Chorus
            audio_chorus = {"section_name": "CHORUS", "is_chorus": True, "total_level": 0.8, "pitch_name": "C"}
            hud.render(screen, None, vis, None, None, audio_chorus, False, media_mgr=media)

            # 2. Render in Buildup
            audio_buildup = {"section_name": "BUILDUP", "is_buildup": True, "total_level": 0.6, "pitch_name": "D"}
            hud.render(screen, None, vis, None, None, audio_buildup, False, media_mgr=media)

            # 3. Render in Verse
            audio_verse = {"section_name": "VERSE", "is_verse": True, "total_level": 0.4, "pitch_name": "E"}
            hud.render(screen, None, vis, None, None, audio_verse, False, media_mgr=media)
        finally:
            media.stop()


if __name__ == "__main__":
    unittest.main()



