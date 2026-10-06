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
from typing import List, Tuple, Optional, Dict, Any
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
    
    Filters out muddy/dark background noise, groups colors into fine hue bins,
    boosts saturation and luminance for physical RGB LEDs and screen strobes,
    and enforces angular hue distance to ensure maximum contrast between beats.
    """
    if not image_bytes:
        return list(DEFAULT_ALBUM_PALETTE)

    try:
        surf = pygame.image.load(io.BytesIO(image_bytes))
        small = pygame.transform.smoothscale(surf, (48, 48))
        arr = pygame.surfarray.array3d(small).reshape(-1, 3)
    except Exception as e:
        _LOGGER.debug("Error loading image for palette extraction: %s", e)
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

    # 2. Color artwork: group pixels into 24 angular hue bins
    num_bins = 24
    bins: Dict[int, list] = {}
    for h, s, v, rgb in hsv_list:
        if v < 0.12:  # Skip muddy near-black pixels
            continue
        bin_idx = int(h * num_bins) % num_bins
        if bin_idx not in bins:
            bins[bin_idx] = []
        # Score favors vivid, well-lit colors over dull/washed-out tones
        score = (s ** 0.8) * (v ** 0.6)
        bins[bin_idx].append((score, h, s, v, rgb))

    sorted_bins = sorted(bins.items(), key=lambda item: sum(x[0] for x in item[1]), reverse=True)

    selected_hues = []
    palette: List[Tuple[int, int, int]] = []

    # First pass: Pick top-scoring colors from bins that are spaced apart in hue (>= 29 degrees)
    for b_idx, items in sorted_bins:
        items.sort(key=lambda x: -x[0])
        best_score, h, s, v, rgb = items[0]

        # Enforce minimum hue distance for maximum beat contrast
        too_close = False
        for sh in selected_hues:
            diff = abs(h - sh)
            diff = min(diff, 1.0 - diff)
            if diff < 0.08:
                too_close = True
                break
        if too_close:
            continue

        # Boost saturation and luminance for punchy RGB LEDs and screen strobes
        s_boost = min(1.0, max(0.48, s * 1.35))
        v_boost = min(1.0, max(0.75, v * 1.25))
        rf, gf, bf = colorsys.hsv_to_rgb(h, s_boost, v_boost)
        col = (int(rf * 255), int(gf * 255), int(bf * 255))
        palette.append(col)
        selected_hues.append(h)
        if len(palette) >= num_colors:
            break

    # Second pass: If fewer than requested colors, fill from remaining bins
    if len(palette) < num_colors:
        for b_idx, items in sorted_bins:
            items.sort(key=lambda x: -x[0])
            best_score, h, s, v, rgb = items[0]
            s_boost = min(1.0, max(0.42, s * 1.30))
            v_boost = min(1.0, max(0.70, v * 1.20))
            rf, gf, bf = colorsys.hsv_to_rgb(h, s_boost, v_boost)
            col = (int(rf * 255), int(gf * 255), int(bf * 255))
            if col not in palette:
                palette.append(col)
            if len(palette) >= num_colors:
                break

    # Third pass: If artwork was single-toned (monochrome hue), generate harmonic contrast
    if len(palette) < num_colors and palette:
        bh = selected_hues[0] if selected_hues else 0.5
        for shift in [0.5, 0.12, -0.12, 0.28, -0.28]:
            nh = (bh + shift) % 1.0
            rf, gf, bf = colorsys.hsv_to_rgb(nh, 0.90, 0.95)
            col = (int(rf * 255), int(gf * 255), int(bf * 255))
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
                # 1. Fetch current active media session (or active session from all sessions)
                session = session_mgr.get_current_session()
                if not session:
                    try:
                        all_sessions = session_mgr.get_sessions()
                        for s in all_sessions:
                            try:
                                pi = s.get_playback_info()
                                if pi and int(pi.playback_status) == 4:  # PLAYING
                                    session = s
                                    break
                            except Exception:
                                pass
                        if not session and len(all_sessions) > 0:
                            session = all_sessions[0]
                    except Exception:
                        pass

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

            # Wait for song change event or poll every 1.0s
            try:
                await asyncio.wait_for(change_event.wait(), timeout=1.0)
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

            status_str = f"Paused: {title}" if (is_paused and title) else (f"Playing: {title}" if title else "Ready")

            # Update playback status on same track if status changed
            with self.lock:
                status_changed = (self.is_paused != is_paused) or (self.is_playing != is_playing)
                if status_changed and self._last_processed_id == track_id:
                    self.is_paused = is_paused
                    self.is_playing = is_playing
                    self.status = status_str

            # If track changed or thumbnail not yet extracted for current track
            track_changed = (track_id != self._last_processed_id)
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

