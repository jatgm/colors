"""
Beat Strobe - Screen Color Strober Synced to Audio Beat
Supports multi-monitor borderless fullscreen, Extreme Crazy Overdrive,
and multi-computer Bluetooth & Network synchronization (Host / Client).
"""

import sys
import time
import numpy as np
import pygame
from config import (
    FPS_CAP,
    MIN_SENSITIVITY,
    MAX_SENSITIVITY,
    MIN_DECAY_RATE,
    MAX_DECAY_RATE,
    MIN_PREAMP_GAIN,
    MAX_PREAMP_GAIN,
)
from audio_capture import AudioCaptureManager
from visualizer import VisualizerEngine
from hud import HUD
from display_manager import DisplayManager
from sync_manager import SyncManager, ROLE_STANDALONE, ROLE_HOST, ROLE_CLIENT
from razer_chroma import RazerChromaManager


class BeatStrobeApp:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("⚡ Beat Strobe - Dual Monitor & Crazy Overdrive")

        # Display manager for multi-monitor setup
        self.display_mgr = DisplayManager()
        self.screen, self.screen_w, self.screen_h, self.is_dual = self.display_mgr.apply_current_mode()

        initial_mon = self.display_mgr.monitors[0].rect if self.display_mgr.monitors else None

        # Core subsystems
        self.audio_mgr = AudioCaptureManager()
        self.visualizer = VisualizerEngine(self.screen_w, self.screen_h)
        self.hud = HUD(self.screen_w, self.screen_h)
        self.sync_mgr = SyncManager()
        self.razer_mgr = RazerChromaManager()

        # Engage Crazy Overdrive Mode by default for maximum strobe intensity!
        self.audio_mgr.set_overdrive(True)
        self.visualizer.overdrive_mode = True

        if initial_mon:
            self.hud.set_active_monitor(initial_mon)

        self.clock = pygame.time.Clock()
        self.running = True
        self.last_click_time = 0.0

        # Synchronized audio state for Client HUD meters
        self.client_audio_state = {
            "is_kick": False,
            "is_snare": False,
            "is_hihat": False,
            "is_drop": False,
            "bass_level": 0.0,
            "mid_level": 0.0,
            "high_level": 0.0,
            "hihat_level": 0.0,
            "total_level": 0.0,
            "spectrum_bars": np.zeros(24, dtype=np.float32),
            "bpm": 0.0,
            "bpm_confidence": 1.0,
            "raw_waveform": np.zeros(1024, dtype=np.float32),
            "overdrive": True,
            "raw_peak": 0.0,
            "agc_gain": 1.0,
            "preamp_gain": 1.8,
        }
        self.client_last_sync_time = 0.0

    def on_display_mode_change(self):
        self.screen, self.screen_w, self.screen_h, self.is_dual = self.display_mgr.apply_current_mode()
        self.visualizer.resize(self.screen_w, self.screen_h)
        initial_mon = self.display_mgr.monitors[0].rect if self.display_mgr.monitors else None
        self.hud.resize(self.screen_w, self.screen_h, initial_mon)

    def cycle_display_mode(self):
        self.display_mgr.cycle_display_mode()
        self.on_display_mode_change()

    def run(self):
        """Main game and render loop."""
        self.audio_mgr.start()
        last_time = time.time()
        last_host_sync_time = 0.0

        try:
            while self.running:
                now = time.time()
                dt = min(0.1, max(0.001, now - last_time))
                last_time = now

                # 1. Process Event Queue
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                        break

                    elif event.type == pygame.VIDEORESIZE and self.display_mgr.current_mode == DisplayManager.MODE_WINDOWED:
                        self.screen_w = event.w
                        self.screen_h = event.h
                        self.visualizer.resize(event.w, event.h)
                        self.hud.resize(event.w, event.h)

                    elif event.type == pygame.KEYDOWN:
                        self.hud.notify_interaction()

                        # Text input in Sync Modal
                        if self.hud.handle_text_input(event, self.sync_mgr):
                            continue

                        # Modal Close Handlers
                        if self.hud.show_sync_modal:
                            if event.key in (pygame.K_ESCAPE, pygame.K_n):
                                self.hud.show_sync_modal = False
                                self.hud.entering_custom_host = False
                            continue

                        # Startup Warning Dialog Handling
                        if not self.hud.warning_dismissed:
                            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                                self.hud.warning_dismissed = True
                            elif event.key == pygame.K_s:
                                self.visualizer.safe_mode = True
                                self.visualizer.overdrive_mode = False
                                self.audio_mgr.set_overdrive(False)
                                self.hud.warning_dismissed = True
                            elif event.key == pygame.K_ESCAPE:
                                self.running = False
                            continue

                        # Main Keybindings
                        if event.key == pygame.K_ESCAPE:
                            self.running = False
                        elif event.key == pygame.K_x:
                            # Toggle Crazy Overdrive Mode!
                            self.visualizer.toggle_overdrive()
                            self.audio_mgr.set_overdrive(self.visualizer.overdrive_mode)
                        elif event.key == pygame.K_c:
                            # Toggle Razer Chroma Peripheral Lighting
                            self.razer_mgr.toggle_enabled()
                        elif event.key == pygame.K_n:
                            self.hud.toggle_sync_modal()
                        elif event.key in (pygame.K_f, pygame.K_F11) or (event.key == pygame.K_RETURN and (event.mod & pygame.KMOD_ALT)):
                            self.cycle_display_mode()
                        elif event.key in (pygame.K_b, pygame.K_2):
                            self.visualizer.cycle_dual_scheme()
                        elif event.key in (pygame.K_h, pygame.K_TAB):
                            self.hud.toggle_hud()
                        elif event.key == pygame.K_m:
                            self.visualizer.cycle_mode()
                        elif event.key == pygame.K_p:
                            self.visualizer.cycle_palette()
                        elif event.key == pygame.K_v:
                            self.visualizer.cycle_style()
                        elif event.key == pygame.K_d:
                            self.audio_mgr.cycle_device()
                        elif event.key == pygame.K_s:
                            self.visualizer.toggle_safe_mode()
                            self.audio_mgr.set_overdrive(self.visualizer.overdrive_mode)
                        elif event.key == pygame.K_t:
                            self.audio_mgr.toggle_demo_mode()
                        elif event.key == pygame.K_UP:
                            new_sens = min(MAX_SENSITIVITY, self.audio_mgr.get_sensitivity() + 0.1)
                            self.audio_mgr.set_sensitivity(new_sens)
                        elif event.key == pygame.K_DOWN:
                            new_sens = max(MIN_SENSITIVITY, self.audio_mgr.get_sensitivity() - 0.1)
                            self.audio_mgr.set_sensitivity(new_sens)
                        elif event.key in (pygame.K_RIGHTBRACKET, pygame.K_PAGEUP, pygame.K_EQUALS):
                            new_gain = min(MAX_PREAMP_GAIN, self.audio_mgr.get_preamp_gain() + 0.2)
                            self.audio_mgr.set_preamp_gain(new_gain)
                        elif event.key in (pygame.K_LEFTBRACKET, pygame.K_PAGEDOWN, pygame.K_MINUS):
                            new_gain = max(MIN_PREAMP_GAIN, self.audio_mgr.get_preamp_gain() - 0.2)
                            self.audio_mgr.set_preamp_gain(new_gain)
                        elif event.key == pygame.K_RIGHT:
                            self.visualizer.set_decay_rate(self.visualizer.decay_rate + 3.0)
                        elif event.key == pygame.K_LEFT:
                            self.visualizer.set_decay_rate(self.visualizer.decay_rate - 3.0)
                        elif event.key == pygame.K_SPACE:
                            self.visualizer.trigger_kick()

                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1:
                            now_click = time.time()
                            is_double = (now_click - self.last_click_time < 0.35)
                            self.last_click_time = now_click

                            consumed = self.hud.handle_mouse_down(
                                event.pos,
                                self.audio_mgr,
                                self.visualizer,
                                self.display_mgr,
                                self.sync_mgr,
                                self.on_display_mode_change,
                                self.razer_mgr,
                            )
                            if not consumed and is_double and not self.hud.show_sync_modal:
                                self.cycle_display_mode()

                    elif event.type == pygame.MOUSEBUTTONUP:
                        if event.button == 1:
                            self.hud.handle_mouse_up()

                    elif event.type == pygame.MOUSEMOTION:
                        self.hud.handle_mouse_motion(
                            event.pos, self.audio_mgr, self.visualizer, self.display_mgr
                        )

                # 2. Audio & Sync State Processing
                is_client = (self.sync_mgr.role == ROLE_CLIENT)
                is_host = (self.sync_mgr.role == ROLE_HOST)

                if is_client:
                    incoming_packets = self.sync_mgr.get_incoming_beats()

                    if incoming_packets:
                        self.client_last_sync_time = now

                        # Process beat trigger events
                        for pkt in incoming_packets:
                            if pkt.get("is_drop"):
                                self.visualizer.trigger_drop()
                            if pkt.get("is_kick"):
                                self.visualizer.trigger_kick()
                            if pkt.get("is_snare"):
                                self.visualizer.trigger_snare()
                            if pkt.get("is_hihat"):
                                self.visualizer.trigger_hihat()

                        # Apply newest full frame synchronization state from host
                        last_pkt = incoming_packets[-1]
                        self.visualizer.apply_sync_packet(last_pkt)

                        # Update client audio state for HUD rendering
                        self.client_audio_state["bpm"] = last_pkt.get("bpm", 0.0)
                        self.client_audio_state["bass_level"] = last_pkt.get("bass_level", 0.0)
                        self.client_audio_state["mid_level"] = last_pkt.get("mid_level", 0.0)
                        self.client_audio_state["high_level"] = last_pkt.get("high_level", 0.0)
                        self.client_audio_state["total_level"] = last_pkt.get("total_level", 0.0)
                        bars = last_pkt.get("spectrum_bars", [])
                        if bars:
                            self.client_audio_state["spectrum_bars"] = np.array(bars, dtype=np.float32)

                    else:
                        # Smooth decay fallback if stream paused or packet delayed
                        if now - self.client_last_sync_time > 0.035:
                            self.visualizer.update_client_fallback(dt)

                    audio_state = self.client_audio_state

                else:
                    audio_state = self.audio_mgr.get_latest_state()
                    self.visualizer.update(dt, audio_state)

                # 3. Update HUD timers
                self.hud.update(dt)

                # 4. Render strobe effects across monitors (exact synchronized match)
                self.visualizer.render(
                    self.screen, audio_state, self.display_mgr.monitors, self.is_dual, is_client_sync=is_client
                )

                # 5. Razer Chroma Peripheral Hardware Sync (Keyboard & Mouse)
                self.razer_mgr.set_colors(
                    self.visualizer.last_render_rgb_0,
                    self.visualizer.last_render_rgb_1,
                )

                # 6. Broadcast to connected clients (Host only)
                if is_host:
                    is_kick = audio_state.get("is_kick", False)
                    is_snare = audio_state.get("is_snare", False)
                    is_hihat = audio_state.get("is_hihat", False)
                    is_drop = audio_state.get("is_drop", False)
                    has_beat = bool(is_kick or is_snare or is_hihat or is_drop)

                    # Stream at 50 Hz OR immediately upon any beat event
                    if has_beat or (now - last_host_sync_time >= 0.020):
                        last_host_sync_time = now
                        packet = self.visualizer.get_sync_packet(audio_state, is_beat_event=has_beat)
                        self.sync_mgr.broadcast_beat(packet)

                # 7. Render HUD overlay
                self.hud.render(
                    self.screen,
                    self.audio_mgr,
                    self.visualizer,
                    self.display_mgr,
                    self.sync_mgr,
                    audio_state,
                    self.is_dual,
                    self.razer_mgr,
                )

                # 8. Display swap & frame cap
                pygame.display.flip()
                self.clock.tick(FPS_CAP)

        finally:
            self.razer_mgr.stop()
            self.audio_mgr.stop()
            self.sync_mgr.stop()
            pygame.quit()


if __name__ == "__main__":
    app = BeatStrobeApp()
    app.run()
