"""
Beat Strobe - Screen Color Strober Synced to Audio Beat
Supports seamless borderless fullscreen spanning across 2 monitors.
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


class BeatStrobeApp:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("⚡ Beat Strobe - Dual Monitor Audio Visualizer")

        # Initialize multi-monitor display manager
        self.display_mgr = DisplayManager()

        # Apply default display mode (Dual Monitor Span if 2+ monitors connected!)
        self.screen, self.screen_w, self.screen_h, self.is_dual = self.display_mgr.apply_current_mode()

        # Active monitor rect for initial HUD placement
        initial_mon = self.display_mgr.monitors[0].rect if self.display_mgr.monitors else None

        # Subsystems
        self.audio_mgr = AudioCaptureManager()
        self.visualizer = VisualizerEngine(self.screen_w, self.screen_h)
        self.hud = HUD(self.screen_w, self.screen_h)
        if initial_mon:
            self.hud.set_active_monitor(initial_mon)

        self.clock = pygame.time.Clock()
        self.running = True
        self.last_click_time = 0.0

    def on_display_mode_change(self):
        """Called when display mode is changed via hotkey or HUD button."""
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

                        # Warning dialog handling
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
                                self.on_display_mode_change,
                            )
                            if not consumed and is_double:
                                self.cycle_display_mode()

                    elif event.type == pygame.MOUSEBUTTONUP:
                        if event.button == 1:
                            self.hud.handle_mouse_up()

                    elif event.type == pygame.MOUSEMOTION:
                        self.hud.handle_mouse_motion(
                            event.pos, self.audio_mgr, self.visualizer, self.display_mgr
                        )

                # 2. Get latest audio detection state
                audio_state = self.audio_mgr.get_latest_state()

                # 3. Update physics & timers
                self.visualizer.update(dt, audio_state)
                self.hud.update(dt)

                # 4. Render strobe effects across monitors
                self.visualizer.render(
                    self.screen, audio_state, self.display_mgr.monitors, self.is_dual
                )

                # 5. Render HUD overlay anchored to active monitor
                self.hud.render(
                    self.screen,
                    self.audio_mgr,
                    self.visualizer,
                    self.display_mgr,
                    audio_state,
                    self.is_dual,
                )

                # 6. Display swap & frame cap
                pygame.display.flip()
                self.clock.tick(FPS_CAP)

        finally:
            self.audio_mgr.stop()
            pygame.quit()


if __name__ == "__main__":
    app = BeatStrobeApp()
    app.run()
