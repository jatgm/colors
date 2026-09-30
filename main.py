"""
Beat Strobe - Screen Color Strober Synced to Audio Beat
Supports multi-monitor borderless fullscreen and multi-computer
Bluetooth & Network synchronization (Host / Client).
"""

import sys
import time
import pygame
from config import (
    FPS_CAP,
    MIN_SENSITIVITY,
    MAX_SENSITIVITY,
    MIN_DECAY_RATE,
    MAX_DECAY_RATE,
)
from audio_capture import AudioCaptureManager
from visualizer import VisualizerEngine
from hud import HUD
from display_manager import DisplayManager
from sync_manager import SyncManager, ROLE_STANDALONE, ROLE_HOST, ROLE_CLIENT


class BeatStrobeApp:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("⚡ Beat Strobe - Dual Monitor & Bluetooth Sync")

        # Display manager for multi-monitor setup
        self.display_mgr = DisplayManager()
        self.screen, self.screen_w, self.screen_h, self.is_dual = self.display_mgr.apply_current_mode()

        initial_mon = self.display_mgr.monitors[0].rect if self.display_mgr.monitors else None

        # Core subsystems
        self.audio_mgr = AudioCaptureManager()
        self.visualizer = VisualizerEngine(self.screen_w, self.screen_h)
        self.hud = HUD(self.screen_w, self.screen_h)
        self.sync_mgr = SyncManager()

        if initial_mon:
            self.hud.set_active_monitor(initial_mon)

        self.clock = pygame.time.Clock()
        self.running = True
        self.last_click_time = 0.0

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

                        # Modal Close Handlers
                        if self.hud.show_sync_modal:
                            if event.key in (pygame.K_ESCAPE, pygame.K_n):
                                self.hud.show_sync_modal = False
                            continue

                        # Startup Warning Dialog Handling
                        if not self.hud.warning_dismissed:
                            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                                self.hud.warning_dismissed = True
                            elif event.key == pygame.K_s:
                                self.visualizer.safe_mode = True
                                self.hud.warning_dismissed = True
                            elif event.key == pygame.K_ESCAPE:
                                self.running = False
                            continue

                        # Main Keybindings
                        if event.key == pygame.K_ESCAPE:
                            self.running = False
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
                        elif event.key == pygame.K_t:
                            self.audio_mgr.toggle_demo_mode()
                        elif event.key == pygame.K_UP:
                            new_sens = min(MAX_SENSITIVITY, self.audio_mgr.get_sensitivity() + 0.1)
                            self.audio_mgr.set_sensitivity(new_sens)
                        elif event.key == pygame.K_DOWN:
                            new_sens = max(MIN_SENSITIVITY, self.audio_mgr.get_sensitivity() - 0.1)
                            self.audio_mgr.set_sensitivity(new_sens)
                        elif event.key == pygame.K_RIGHT:
                            self.visualizer.set_decay_rate(self.visualizer.decay_rate + 2.0)
                        elif event.key == pygame.K_LEFT:
                            self.visualizer.set_decay_rate(self.visualizer.decay_rate - 2.0)
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
                if self.sync_mgr.role == ROLE_CLIENT:
                    # Client mode: consume incoming packets from host
                    incoming_packets = self.sync_mgr.get_incoming_beats()
                    audio_state = self.audio_mgr.get_latest_state()

                    for pkt in incoming_packets:
                        if pkt.get("type") in ("BEAT", "STATE"):
                            if pkt.get("is_kick"):
                                self.visualizer.trigger_kick()
                                self.visualizer.kick_intensity = pkt.get("intensity", 1.0)
                            if pkt.get("is_snare"):
                                self.visualizer.trigger_snare()

                            # Sync colors and settings from Host
                            if "color" in pkt:
                                self.visualizer.current_color = tuple(pkt["color"])
                            if "secondary_color" in pkt:
                                self.visualizer.secondary_color = tuple(pkt["secondary_color"])
                            if "palette" in pkt:
                                self.visualizer.set_palette(pkt["palette"])
                            if "mode" in pkt:
                                self.visualizer.mode = pkt["mode"]
                            if "decay" in pkt:
                                self.visualizer.decay_rate = pkt["decay"]
                            if "safe" in pkt:
                                self.visualizer.safe_mode = pkt["safe"]
                            if "bpm" in pkt:
                                audio_state["bpm"] = pkt["bpm"]
                            if "bass_level" in pkt:
                                audio_state["bass_level"] = pkt["bass_level"]
                                audio_state["mid_level"] = pkt.get("mid_level", 0.0)
                                audio_state["high_level"] = pkt.get("high_level", 0.0)
                                audio_state["total_level"] = pkt.get("total_level", 0.0)

                else:
                    # Standalone or Host: capture local audio
                    audio_state = self.audio_mgr.get_latest_state()

                    # If Host, broadcast beats to connected clients over Bluetooth & Network
                    if self.sync_mgr.role == ROLE_HOST:
                        is_kick = audio_state.get("is_kick", False)
                        is_snare = audio_state.get("is_snare", False)

                        if is_kick or is_snare or (now - last_host_sync_time > 0.25):
                            last_host_sync_time = now
                            packet = {
                                "type": "BEAT" if (is_kick or is_snare) else "STATE",
                                "is_kick": is_kick,
                                "is_snare": is_snare,
                                "color": list(self.visualizer.current_color),
                                "secondary_color": list(self.visualizer.secondary_color),
                                "palette": self.visualizer.palette_name,
                                "mode": self.visualizer.mode,
                                "decay": self.visualizer.decay_rate,
                                "safe": self.visualizer.safe_mode,
                                "dual_side": self.visualizer.alternating_side,
                                "intensity": self.visualizer.kick_intensity if is_kick else 0.0,
                                "bpm": audio_state.get("bpm", 0.0),
                                "bass_level": audio_state.get("bass_level", 0.0),
                                "mid_level": audio_state.get("mid_level", 0.0),
                                "high_level": audio_state.get("high_level", 0.0),
                                "total_level": audio_state.get("total_level", 0.0),
                            }
                            self.sync_mgr.broadcast_beat(packet)

                # 3. Update physics & timers
                self.visualizer.update(dt, audio_state)
                self.hud.update(dt)

                # 4. Render strobe effects across monitors
                self.visualizer.render(
                    self.screen, audio_state, self.display_mgr.monitors, self.is_dual
                )

                # 5. Render HUD overlay
                self.hud.render(
                    self.screen,
                    self.audio_mgr,
                    self.visualizer,
                    self.display_mgr,
                    self.sync_mgr,
                    audio_state,
                    self.is_dual,
                )

                # 6. Display swap & frame cap
                pygame.display.flip()
                self.clock.tick(FPS_CAP)

        finally:
            self.audio_mgr.stop()
            self.sync_mgr.stop()
            pygame.quit()


if __name__ == "__main__":
    app = BeatStrobeApp()
    app.run()
