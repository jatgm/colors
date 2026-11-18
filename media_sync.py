"""
Native Windows Album Cover Art & Media Synchronization Manager.
Uses Windows Runtime (WinRT) GlobalSystemMediaTransportControlsSessionManager
to natively capture currently playing media metadata (Spotify, Apple Music,
Chrome, Edge, Tidal, etc.) and extract dominant vibrant color palettes from
the album cover artwork for real-time strobe and peripheral synchronization.
"""

import sys
import io
import time
import queue
import logging
import colorsys
import threading
import asyncio
import datetime
import hashlib
from typing import List, Tuple, Optional, Dict, Any
import numpy as np
import pygame

_LOGGER = logging.getLogger("MediaSync")

# Fallback default vibrant palette when no album art is available
DEFAULT_ALBUM_PALETTE: List[Tuple[int, int, int]] = [
    (0, 240, 255),    # Electric Cyan
    (255, 0, 128),    # Neon Magenta
    (157, 0, 255),    # Violet Flare
    (255, 230, 0),    # Sunburst Gold
    (0, 255, 170),    # Mint Neon
]


def generate_song_waveform(title: str, artist: str, duration: float, num_bars: int = 240, channel: int = 0) -> np.ndarray:
    """Generate an authentic structural musical amplitude contour for a track with rich harmonic dynamics."""
    if num_bars <= 0:
        return np.zeros(0, dtype=np.float32)

    seed_str = f"{artist.strip().lower()} - {title.strip().lower()}"
    seed = int(hashlib.md5(seed_str.encode("utf-8")).hexdigest()[:8], 16)
    rng = np.random.RandomState((seed + channel * 104729) & 0xFFFFFFFF)

    t = np.linspace(0.0, 1.0, num_bars, dtype=np.float32)

    # Use duration to calibrate musical pacing (default 210s if duration <= 0)
    eff_dur = duration if duration > 10.0 else 210.0
    bpm = 120.0 + (seed % 40) - 20.0  # Estimated track tempo 100-140 BPM
    total_beats = (eff_dur / 60.0) * bpm
    total_bars = total_beats / 4.0

    # Natural musical song architecture (Intro -> Verse 1 -> Pre-Chorus 1 -> Chorus 1 -> Verse 2 -> Pre-Chorus 2 -> Chorus 2 -> Bridge/Breakdown -> Climax Drop -> Outro)
    macro = (
        0.28 * np.sin(np.pi * t) +
        0.24 * np.sin(3.0 * np.pi * t + 0.3)**2 +
        0.22 * np.sin(6.0 * np.pi * t + 0.1)**2 +
        0.18 * np.sin(11.0 * np.pi * t)**2
    )

    # Sectional dynamics and surges
    ch1 = np.exp(-((t - 0.37) / 0.08)**2) * 0.35
    ch2 = np.exp(-((t - 0.68) / 0.07)**2) * 0.38
    climax = np.exp(-((t - 0.88) / 0.06)**2) * 0.42

    # Buildup risers leading into drops
    riser1 = np.clip((t - 0.24) / 0.06, 0.0, 1.0) * ((t >= 0.24) & (t < 0.30)) * 0.20
    riser2 = np.clip((t - 0.76) / 0.06, 0.0, 1.0) * ((t >= 0.76) & (t < 0.82)) * 0.25

    # Signature pre-drop micro-cuts (the 1-bar breath right before the beat drops)
    drop_cut1 = 1.0 - 0.65 * np.exp(-((t - 0.297) / 0.008)**2)
    drop_cut2 = 1.0 - 0.65 * np.exp(-((t - 0.617) / 0.008)**2)
    drop_cut3 = 1.0 - 0.70 * np.exp(-((t - 0.817) / 0.008)**2)

    arch = (macro + ch1 + ch2 + climax + riser1 + riser2) * drop_cut1 * drop_cut2 * drop_cut3

    # Phrasing cycles: 8-bar chord movement, 4-bar melodic phrasing, 1-bar rhythmic breathing
    cycles_8bar = max(4.0, total_bars / 8.0)
    cycles_4bar = cycles_8bar * 2.0
    cycles_1bar = cycles_4bar * 4.0

    phrase_8bar = 0.06 * np.sin(cycles_8bar * 2.0 * np.pi * t + rng.uniform(0, np.pi))
    phrase_4bar = 0.08 * np.sin(cycles_4bar * 2.0 * np.pi * t + rng.uniform(0, np.pi))
    phrase_1bar = 0.06 * np.cos(cycles_1bar * 2.0 * np.pi * t + rng.uniform(0, np.pi))

    # Beat-level transient attacks (rhythmic pulses across 4/4 meter with channel stereo phase variance)
    sub_bass = 0.07 * np.abs(np.sin(cycles_1bar * 4.0 * np.pi * t))**6
    stereo_phase = 0.18 * (1 if channel == 0 else -1)
    stereo_accent = 0.06 * np.sin(cycles_4bar * 4.0 * np.pi * t + stereo_phase)
    beats = 0.10 * np.abs(np.sin(cycles_1bar * 4.0 * np.pi * t + (channel * 0.16)))**8

    # Multi-layer acoustic fractal texture (organic recorded master sound dynamics)
    octave1 = rng.uniform(-0.06, 0.06, num_bars)
    raw_oct2 = rng.uniform(-0.08, 0.08, num_bars)
    octave2 = np.convolve(raw_oct2, [0.25, 0.5, 0.25], mode="same")
    octave3 = rng.uniform(0.08, 0.24, num_bars)
    texture = octave1 + octave2 + octave3

    # Transient percussion spikes (accents on snare/crash boundaries)
    num_spikes = min(num_bars, max(1, num_bars // 16))
    spikes = np.zeros(num_bars, dtype=np.float32)
    if num_spikes > 0:
        spike_indices = rng.choice(num_bars, size=num_spikes, replace=False)
        spikes[spike_indices] = rng.uniform(0.10, 0.25, len(spike_indices))

    wf = arch * 0.62 + phrase_8bar + phrase_4bar + phrase_1bar + sub_bass + stereo_accent + beats + texture + spikes
    wf = np.clip(wf, 0.10, 0.98).astype(np.float32)

    # Clean intro rise and outro decay
    fade_in = max(2, min(num_bars // 12, 16))
    fade_out = max(2, min(num_bars // 10, 20))
    if fade_in > 0:
        wf[:fade_in] *= np.linspace(0.20, 1.0, fade_in)
    if fade_out > 0:
        wf[-fade_out:] *= np.linspace(1.0, 0.12, fade_out)
    return wf


# Check if WinRT media control libraries are available
WINRT_AVAILABLE = False
try:
    if sys.platform == "win32":
        try:
            import winrt.windows.media.control as wmc
            import winrt.windows.storage.streams as streams
            WINRT_AVAILABLE = True
        except ImportError:
            try:
                import winsdk.windows.media.control as wmc
                import winsdk.windows.storage.streams as streams
                WINRT_AVAILABLE = True
            except ImportError:
                pass
except ImportError:
    pass

if not WINRT_AVAILABLE:
    _LOGGER.warning("Neither winrt nor winsdk media control libraries available. Install via 'pip install winrt-Windows.Media.Control'")


def extract_cover_palette(image_bytes: bytes, num_colors: int = 5) -> List[Tuple[int, int, int]]:
    """Extract a vibrant, high-contrast strobe-optimized color palette from raw image bytes.
    
    Filters out muddy/dark background noise, detects dominant single-hue distributions
    (e.g. albums predominantly colored like Frank Ocean's Channel Orange or Weezer's Blue Album)
    to generate authentic tonal and dynamic strobe variations of that dominant hue,
    and isolates distinct colors across multi-colored artwork without synthesizing
    unrepresented hues.
    """
    if not image_bytes:
        return list(DEFAULT_ALBUM_PALETTE)

    try:
        surf = pygame.image.load(io.BytesIO(image_bytes))
    except Exception:
        try:
            surf = pygame.image.load(io.BytesIO(image_bytes), "image.tga")
        except Exception as e:
            _LOGGER.debug("Error loading image for palette extraction: %s", e)
            return list(DEFAULT_ALBUM_PALETTE)

    try:
        small = pygame.transform.smoothscale(surf, (48, 48))
        arr = pygame.surfarray.array3d(small).reshape(-1, 3)
    except Exception as e:
        _LOGGER.debug("Error transforming surface for palette extraction: %s", e)
        return list(DEFAULT_ALBUM_PALETTE)

    hsv_list = []
    total_sat = 0.0
    for r, g, b in arr:
        rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
        h, s, v = colorsys.rgb_to_hsv(rf, gf, bf)
        hsv_list.append((h, s, v, (int(r), int(g), int(b))))
        total_sat += s

    if not hsv_list:
        return list(DEFAULT_ALBUM_PALETTE)

    avg_sat = total_sat / len(hsv_list)

    # 1. Monochrome / grayscale album artwork (e.g. vintage or black-and-white covers)
    if avg_sat < 0.10:
        sorted_by_v = sorted(hsv_list, key=lambda x: x[2])
        palette = []
        for frac in (0.95, 0.70, 0.50, 0.30, 0.15):
            idx = int(len(sorted_by_v) * frac)
            idx = min(len(sorted_by_v) - 1, max(0, idx))
            r, g, b = sorted_by_v[idx][3]
            boost = max(1.0, 120.0 / max(r, g, b, 1)) if max(r, g, b) < 60 else 1.0
            col = (min(255, int(r * boost)), min(255, int(g * boost)), min(255, int(b * boost)))
            palette.append(col)
        return palette[:num_colors]

    # Filter out near-black background pixels (v < 0.12)
    valid_pixels = [p for p in hsv_list if p[2] >= 0.12]
    if not valid_pixels:
        return list(DEFAULT_ALBUM_PALETTE)

    # Separate colored pixels from neutral/white/gray pixels
    colored_pixels = [p for p in valid_pixels if p[1] >= 0.18]
    if len(colored_pixels) < len(valid_pixels) * 0.05:
        colored_pixels = valid_pixels

    # Group colored pixels into 24 angular hue bins
    num_bins = 24
    bins: Dict[int, list] = {}
    for h, s, v, rgb in colored_pixels:
        bin_idx = int(h * num_bins) % num_bins
        if bin_idx not in bins:
            bins[bin_idx] = []
        # Score favors vivid, well-lit colors over dull/washed-out tones
        score = (s ** 0.8) * (v ** 0.6)
        bins[bin_idx].append((score, h, s, v, rgb))

    bin_scores = {b_idx: sum(x[0] for x in items) for b_idx, items in bins.items()}
    total_score = sum(bin_scores.values()) or 1.0

    sorted_bins = sorted(bins.items(), key=lambda item: bin_scores[item[0]], reverse=True)
    if not sorted_bins:
        return list(DEFAULT_ALBUM_PALETTE)

    # Dominant hue detection: find top bin and measure cluster coverage within +-29 degrees
    top_bin_idx, top_items = sorted_bins[0]
    top_items.sort(key=lambda x: -x[0])
    dom_best_score, dom_h, dom_s, dom_v, dom_rgb = top_items[0]

    cluster_score = 0.0
    for b_idx, items in sorted_bins:
        items.sort(key=lambda x: -x[0])
        bh = items[0][1]
        diff = abs(bh - dom_h)
        diff = min(diff, 1.0 - diff)
        if diff <= 0.08:
            cluster_score += bin_scores[b_idx]

    dominant_ratio = cluster_score / total_score

    # Identify genuine secondary distinct hues in artwork (diff > 0.08, >= 5% total score)
    secondary_hues = []
    for b_idx, items in sorted_bins[1:]:
        items.sort(key=lambda x: -x[0])
        cand_score, ch, cs, cv, crgb = items[0]
        diff = abs(ch - dom_h)
        diff = min(diff, 1.0 - diff)
        if diff > 0.08 and (bin_scores[b_idx] / total_score) >= 0.05:
            if all(min(abs(ch - sh[0]), 1.0 - abs(ch - sh[0])) > 0.08 for sh in secondary_hues):
                secondary_hues.append((ch, cs, cv, bin_scores[b_idx]))

    # Helper to generate rich, strobe-optimized tonal variations of a base dominant hue
    def make_dominant_variants(bh: float, bs: float, bv: float, count: int) -> List[Tuple[int, int, int]]:
        variants = []
        # 1. Primary punch: core vibrant hue
        s1 = min(1.0, max(0.85, bs * 1.25))
        v1 = min(1.0, max(0.85, bv * 1.20))
        r1, g1, b1 = colorsys.hsv_to_rgb(bh, s1, v1)
        variants.append((int(r1 * 255), int(g1 * 255), int(b1 * 255)))

        if count > 1:
            # 2. Electric flash highlight (high luminance, slightly warmer/lighter)
            h2 = (bh + 0.018) % 1.0
            s2 = max(0.60, min(0.80, bs * 0.85))
            r2, g2, b2 = colorsys.hsv_to_rgb(h2, s2, 1.0)
            variants.append((int(r2 * 255), int(g2 * 255), int(b2 * 255)))

        if count > 2:
            # 3. Deep sub-bass impact (hyper-saturated, punchy deep tone)
            h3 = (bh - 0.022) % 1.0
            v3 = min(0.92, max(0.70, bv * 0.88))
            r3, g3, b3 = colorsys.hsv_to_rgb(h3, 1.0, v3)
            variants.append((int(r3 * 255), int(g3 * 255), int(b3 * 255)))

        if count > 3:
            # 4. Pure neon chroma
            h4 = (bh + 0.008) % 1.0
            r4, g4, b4 = colorsys.hsv_to_rgb(h4, 1.0, 1.0)
            variants.append((int(r4 * 255), int(g4 * 255), int(b4 * 255)))

        if count > 4:
            # 5. Warm radiant amber / golden tint
            h5 = (bh - 0.010) % 1.0
            r5, g5, b5 = colorsys.hsv_to_rgb(h5, min(1.0, max(0.75, bs * 1.05)), 0.95)
            variants.append((int(r5 * 255), int(g5 * 255), int(b5 * 255)))

        if count > 5:
            for extra_i in range(5, count):
                h_extra = (bh + (extra_i - 2) * 0.015) % 1.0
                r_ex, g_ex, b_ex = colorsys.hsv_to_rgb(h_extra, 0.90, 0.95)
                variants.append((int(r_ex * 255), int(g_ex * 255), int(b_ex * 255)))

        return variants[:count]

    # CASE A: Dominant single-color artwork (>= 50% cluster or no strong secondary hues)
    if dominant_ratio >= 0.50 or not secondary_hues:
        if len(secondary_hues) >= 2 and num_colors >= 5:
            # 3 dominant variations (majority!), plus 2 genuine secondary accents
            palette = make_dominant_variants(dom_h, dom_s, dom_v, num_colors - 2)
            for sec_h, sec_s, sec_v, _ in secondary_hues[:2]:
                rf, gf, bf = colorsys.hsv_to_rgb(sec_h, min(1.0, max(0.60, sec_s * 1.30)), min(1.0, max(0.80, sec_v * 1.20)))
                palette.append((int(rf * 255), int(gf * 255), int(bf * 255)))
        elif len(secondary_hues) == 1 and num_colors >= 5:
            # 4 dominant variations (80% majority!), plus 1 genuine secondary accent
            palette = make_dominant_variants(dom_h, dom_s, dom_v, num_colors - 1)
            sec_h, sec_s, sec_v, _ = secondary_hues[0]
            rf, gf, bf = colorsys.hsv_to_rgb(sec_h, min(1.0, max(0.60, sec_s * 1.30)), min(1.0, max(0.80, sec_v * 1.20)))
            palette.append((int(rf * 255), int(gf * 255), int(bf * 255)))
        else:
            # Overwhelmingly single-toned (e.g. Channel Orange): 100% rich variations of the dominant hue
            palette = make_dominant_variants(dom_h, dom_s, dom_v, num_colors)

        return palette[:num_colors]

    # CASE B: Truly multi-colored artwork (no single hue has >= 50% dominance)
    selected_hues = []
    palette = []
    for b_idx, items in sorted_bins:
        items.sort(key=lambda x: -x[0])
        cand_score, h, s, v, rgb = items[0]
        too_close = any(min(abs(h - sh), 1.0 - abs(h - sh)) < 0.08 for sh in selected_hues)
        if too_close:
            continue
        s_boost = min(1.0, max(0.48, s * 1.35))
        v_boost = min(1.0, max(0.75, v * 1.25))
        rf, gf, bf = colorsys.hsv_to_rgb(h, s_boost, v_boost)
        palette.append((int(rf * 255), int(gf * 255), int(bf * 255)))
        selected_hues.append(h)
        if len(palette) >= num_colors:
            break

    # If fewer than num_colors distinct hues were found, fill with tonal variations of the existing artwork colors
    # without synthesizing unrepresented hues
    if len(palette) < num_colors:
        needed = num_colors - len(palette)
        extra = make_dominant_variants(dom_h, dom_s, dom_v, needed + 1)
        for col in extra:
            if col not in palette:
                palette.append(col)
            if len(palette) >= num_colors:
                break

    return palette[:num_colors] if palette else list(DEFAULT_ALBUM_PALETTE)


class MediaArtManager:
    """Natively tracks Windows media playback and album art thumbnail streams.
    
    Runs an asynchronous event/poll loop in a dedicated background worker thread,
    decodes cover art thumbnails, extracts vibrant palettes, and provides
    thread-safe access to cover art surfaces and metadata for the visualizer,
    HUD, and hardware peripherals.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.running = True

        # Current playback state
        self.title = ""
        self.artist = ""
        self.album = ""
        self.has_art = False
        self.is_paused = False
        self.is_playing = False
        self.status = "Initializing..."
        self.current_palette: List[Tuple[int, int, int]] = list(DEFAULT_ALBUM_PALETTE)
        self.thumbnail_bytes: Optional[bytes] = None
        self.thumbnail_surface: Optional[pygame.Surface] = None
        self.hud_thumbnail: Optional[pygame.Surface] = None  # 40x40 scaled with border

        # Track version counter to notify visualizer of changes
        self.update_count = 0
        self._last_processed_id = ""

        # Timeline and Waveform progress tracking
        self.timeline_position = 0.0
        self.timeline_duration = 0.0
        self.timeline_last_wall_time = time.time()
        self.num_waveform_bars = 240
        # Cached waveform amplitude contour per track_id: Dict[track_id, np.ndarray]
        self._waveform_cache: Dict[str, np.ndarray] = {}
        self._waveform_cache_r: Dict[str, np.ndarray] = {}
        self.current_waveform = np.zeros(self.num_waveform_bars, dtype=np.float32)
        self.current_waveform_r = np.zeros(self.num_waveform_bars, dtype=np.float32)
        self._seek_queue: queue.Queue = queue.Queue()

        # Worker thread
        self._thread = threading.Thread(target=self._worker_thread_main, daemon=True, name="MediaArtWorker")
        self._thread.start()

    def stop(self):
        self.running = False

    def get_palette(self) -> List[Tuple[int, int, int]]:
        with self.lock:
            return list(self.current_palette)

    def get_info(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "title": self.title,
                "artist": self.artist,
                "album": self.album,
                "has_art": self.has_art,
                "is_paused": getattr(self, "is_paused", False),
                "is_playing": getattr(self, "is_playing", False),
                "status": self.status,
                "update_count": self.update_count,
            }

    def get_timeline(self) -> Dict[str, Any]:
        """Return millisecond-interpolated timeline progress and full-song waveform contour."""
        with self.lock:
            pos = self.timeline_position
            dur = self.timeline_duration
            is_playing = self.is_playing and not self.is_paused
            if is_playing and dur > 0:
                elapsed = max(0.0, time.time() - self.timeline_last_wall_time)
                pos = min(dur, pos + elapsed)

            progress = (pos / dur) if dur > 0 else 0.0
            return {
                "position": pos,
                "duration": dur,
                "progress": min(1.0, max(0.0, progress)),
                "waveform": self.current_waveform.copy(),
                "waveform_r": self.current_waveform_r.copy(),
                "num_bars": self.num_waveform_bars,
                "is_playing": is_playing,
                "is_paused": self.is_paused,
            }

    def seek(self, progress: float):
        """Seek timeline playback progress (0.0 to 1.0)."""
        with self.lock:
            if self.timeline_duration > 0:
                self.timeline_position = max(0.0, min(self.timeline_duration, progress * self.timeline_duration))
                self.timeline_last_wall_time = time.time()
                try:
                    self._seek_queue.put_nowait(self.timeline_position)
                except Exception:
                    pass

    def update_waveform_energy(self, current_energy: float):
        """Record real-time audio amplitude into the current song's timeline position bin."""
        with self.lock:
            dur = self.timeline_duration
            if dur <= 0:
                return
            pos = self.timeline_position
            if self.is_playing and not self.is_paused:
                elapsed = max(0.0, time.time() - self.timeline_last_wall_time)
                pos = min(dur, pos + elapsed)
            bin_idx = int((pos / dur) * (self.num_waveform_bars - 1))
            bin_idx = min(self.num_waveform_bars - 1, max(0, bin_idx))
            
            # If an authentic song contour is already established, do not mutate or decay it
            # so the waveform progress bar remains a stable, non-flashing structural map
            if self._last_processed_id:
                return

            # Smoothly blend energy into bin when building fallback contour
            current_val = self.current_waveform[bin_idx]
            energy_val = min(1.0, float(current_energy))
            self.current_waveform[bin_idx] = max(current_val, energy_val)
            
            current_val_r = self.current_waveform_r[bin_idx]
            self.current_waveform_r[bin_idx] = max(current_val_r, min(1.0, energy_val * 0.96))

            # Light spatial diffusion to adjacent bins for organic acoustic contouring
            if bin_idx > 0:
                self.current_waveform[bin_idx - 1] = max(self.current_waveform[bin_idx - 1], energy_val * 0.65)
                self.current_waveform_r[bin_idx - 1] = max(self.current_waveform_r[bin_idx - 1], energy_val * 0.62)
            if bin_idx < self.num_waveform_bars - 1:
                self.current_waveform[bin_idx + 1] = max(self.current_waveform[bin_idx + 1], energy_val * 0.65)
                self.current_waveform_r[bin_idx + 1] = max(self.current_waveform_r[bin_idx + 1], energy_val * 0.62)

    def get_hud_thumbnail(self) -> Optional[pygame.Surface]:
        with self.lock:
            return self.hud_thumbnail

    def _worker_thread_main(self):
        """Worker thread entry point running an asyncio event loop."""
        if not WINRT_AVAILABLE:
            with self.lock:
                self.status = "WinRT Media Control unavailable"
            return

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._async_loop())
        except Exception as e:
            _LOGGER.debug("Media worker thread encountered error: %s", e)
        finally:
            loop.close()

    async def _async_loop(self):
        """Asynchronous monitoring loop using Windows Runtime SessionManager."""
        try:
            session_mgr = await wmc.GlobalSystemMediaTransportControlsSessionManager.request_async()
        except Exception as e:
            with self.lock:
                self.status = f"SessionManager init failed: {e}"
            return

        with self.lock:
            self.status = "Listening for media..."

        loop = asyncio.get_running_loop()
        change_event = asyncio.Event()

        def _trigger_change(sender=None, args=None):
            try:
                loop.call_soon_threadsafe(change_event.set)
            except Exception:
                pass

        try:
            session_mgr.add_current_session_changed(_trigger_change)
        except Exception:
            pass

        try:
            session_mgr.add_sessions_changed(_trigger_change)
        except Exception:
            pass

        current_session = None

        while self.running:
            try:
                # 1. Fetch current active media session (prioritize Spotify if present)
                session = None
                try:
                    all_sessions = session_mgr.get_sessions()
                    # Check for Spotify session first
                    for s in all_sessions:
                        try:
                            aumid = (s.source_app_user_model_id or "").lower()
                            if "spotify" in aumid:
                                session = s
                                break
                        except Exception:
                            pass

                    # If no Spotify session found, check for any playing session
                    if not session:
                        for s in all_sessions:
                            try:
                                pi = s.get_playback_info()
                                if pi and int(pi.playback_status) == 4:  # PLAYING
                                    session = s
                                    break
                            except Exception:
                                pass

                    # Fallback to current session or first available
                    if not session:
                        session = session_mgr.get_current_session()
                    if not session and len(all_sessions) > 0:
                        session = all_sessions[0]
                except Exception:
                    session = session_mgr.get_current_session()

                if session != current_session:
                    current_session = session
                    if current_session:
                        try:
                            current_session.add_media_properties_changed(_trigger_change)
                        except Exception:
                            pass
                        try:
                            current_session.add_playback_info_changed(_trigger_change)
                        except Exception:
                            pass

                if current_session and hasattr(self, "_seek_queue") and not self._seek_queue.empty():
                    try:
                        while not self._seek_queue.empty():
                            seek_pos_sec = self._seek_queue.get_nowait()
                            if hasattr(current_session, "try_change_playback_position_async"):
                                ticks = int(seek_pos_sec * 10_000_000)
                                await current_session.try_change_playback_position_async(ticks)
                    except Exception:
                        pass

                if not current_session:
                    with self.lock:
                        if self.title or self.has_art or self.status != "No active media playback":
                            self.title = ""
                            self.artist = ""
                            self.album = ""
                            self.has_art = False
                            self.is_paused = False
                            self.is_playing = False
                            self.thumbnail_surface = None
                            self.hud_thumbnail = None
                            self.status = "No active media playback"
                            self._last_processed_id = ""
                            self.update_count += 1
                else:
                    await self._process_session(current_session)

            except Exception as e:
                _LOGGER.debug("Error during media session poll: %s", e)

            # Wait for song change event or poll every 0.4s for live timeline synchronization
            try:
                await asyncio.wait_for(change_event.wait(), timeout=0.4)
                change_event.clear()
            except asyncio.TimeoutError:
                pass

    async def _process_session(self, session):
        """Extract media properties and cover artwork from active session."""
        try:
            props = await session.try_get_media_properties_async()
            if not props:
                return

            title = str(props.title or "").strip()
            artist = str(props.artist or "").strip()
            album = str(props.album_title or "").strip()
            track_id = f"{artist} - {title} ({album})"

            # Query playback info (Playing vs Paused vs Stopped)
            is_paused = False
            is_playing = True
            try:
                playback_info = session.get_playback_info()
                if playback_info:
                    status_val = int(playback_info.playback_status)
                    # 4 = Playing, 5 = Paused, 3 = Stopped
                    is_playing = (status_val == 4)
                    is_paused = (status_val == 5)
            except Exception:
                pass

            # Query timeline properties (position, duration, end_time, last_updated_time)
            cur_pos = 0.0
            cur_dur = 0.0
            timeline_updated_wall_time = time.time()
            try:
                timeline = session.get_timeline_properties()
                if timeline:
                    if hasattr(timeline, "end_time") and timeline.end_time:
                        cur_dur = float(timeline.end_time.total_seconds())
                    if hasattr(timeline, "position") and timeline.position:
                        raw_pos = float(timeline.position.total_seconds())
                        cur_pos = raw_pos
                        # High-precision OS time extrapolation:
                        # Windows only updates `position` every few seconds, but provides `last_updated_time` (UTC).
                        if hasattr(timeline, "last_updated_time") and timeline.last_updated_time:
                            lut = timeline.last_updated_time
                            try:
                                now_utc = datetime.datetime.now(datetime.timezone.utc)
                                delta_sec = (now_utc - lut).total_seconds()
                                if is_playing and not is_paused and 0 <= delta_sec < 60:
                                    cur_pos = raw_pos + delta_sec
                            except Exception:
                                pass
            except Exception:
                pass

            status_str = f"Paused: {title}" if (is_paused and title) else (f"Playing: {title}" if title else "Ready")

            # Update playback status and timeline on same track if status changed
            with self.lock:
                status_changed = (self.is_paused != is_paused) or (self.is_playing != is_playing)
                if cur_dur > 0:
                    self.timeline_position = cur_pos
                    self.timeline_duration = cur_dur
                    self.timeline_last_wall_time = time.time()
                if status_changed and self._last_processed_id == track_id:
                    self.is_paused = is_paused
                    self.is_playing = is_playing
                    self.status = status_str

            # If track changed or thumbnail not yet extracted for current track
            track_changed = (track_id != self._last_processed_id)
            if track_changed:
                with self.lock:
                    # Switch waveform contour to cached or generate authentic contour
                    if track_id in self._waveform_cache:
                        self.current_waveform = self._waveform_cache[track_id].copy()
                        self.current_waveform_r = self._waveform_cache_r.get(track_id, self.current_waveform).copy()
                    else:
                        self.current_waveform = generate_song_waveform(title, artist, cur_dur, self.num_waveform_bars, channel=0)
                        self.current_waveform_r = generate_song_waveform(title, artist, cur_dur, self.num_waveform_bars, channel=1)
                        self._waveform_cache[track_id] = self.current_waveform
                        self._waveform_cache_r[track_id] = self.current_waveform_r
                    if cur_dur > 0:
                        self.timeline_position = cur_pos
                        self.timeline_duration = cur_dur
                        self.timeline_last_wall_time = time.time()

            need_art = (not self.has_art and props.thumbnail is not None)

            if track_changed or need_art:
                self._last_processed_id = track_id

                thumb_bytes = None
                if props.thumbnail:
                    stream = None
                    reader = None
                    try:
                        stream = await props.thumbnail.open_read_async()
                        if stream and stream.size > 0:
                            reader = streams.DataReader(stream)
                            await reader.load_async(stream.size)
                            ba = bytearray(stream.size)
                            reader.read_bytes(ba)
                            thumb_bytes = bytes(ba)
                    except Exception as e:
                        _LOGGER.debug("Could not read thumbnail stream: %s", e)
                    finally:
                        if reader:
                            try:
                                reader.close()
                            except Exception:
                                pass
                        if stream:
                            try:
                                stream.close()
                            except Exception:
                                pass

                # Process thumbnail and extract palette
                if thumb_bytes:
                    palette = extract_cover_palette(thumb_bytes, num_colors=5)
                    hud_thumb = None
                    try:
                        surf = pygame.image.load(io.BytesIO(thumb_bytes))
                        # Scale to 40x40 for crisp HUD rendering with 1px border
                        scaled = pygame.transform.smoothscale(surf, (38, 38))
                        hud_thumb = pygame.Surface((40, 40), pygame.SRCALPHA)
                        hud_thumb.fill((0, 0, 0, 0))
                        pygame.draw.rect(hud_thumb, (40, 45, 60), (0, 0, 40, 40), border_radius=5)
                        hud_thumb.blit(scaled, (1, 1))
                        pygame.draw.rect(hud_thumb, palette[0], (0, 0, 40, 40), width=1, border_radius=5)
                    except Exception as e:
                        _LOGGER.debug("Error rendering HUD thumbnail surface: %s", e)

                    with self.lock:
                        self.title = title
                        self.artist = artist
                        self.album = album
                        self.has_art = True
                        self.is_paused = is_paused
                        self.is_playing = is_playing
                        self.status = status_str
                        self.current_palette = palette
                        self.thumbnail_bytes = thumb_bytes
                        self.hud_thumbnail = hud_thumb
                        self.update_count += 1
                else:
                    # Media without cover art thumbnail (e.g. video streams or untagged files)
                    if track_changed:
                        with self.lock:
                            self.title = title
                            self.artist = artist
                            self.album = album
                            self.has_art = False
                            self.is_paused = is_paused
                            self.is_playing = is_playing
                            self.status = status_str
                            self.thumbnail_bytes = None
                            self.hud_thumbnail = None
                            # Keep existing or default palette
                            self.update_count += 1

        except Exception as e:
            _LOGGER.debug("Error processing session properties: %s", e)

