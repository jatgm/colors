"""
Audio capture engine using soundcard.
Supports WASAPI desktop audio loopback (Spotify, YouTube, Games, etc.)
and physical microphone input, with real-time thread-safe beat analysis.
"""

import threading
import time
import numpy as np
import soundcard as sc
from config import SAMPLE_RATE, CHUNK_SIZE
from beat_detector import BeatDetector


class AudioCaptureManager:
    def __init__(self):
        self.detector = BeatDetector(sample_rate=SAMPLE_RATE, chunk_size=CHUNK_SIZE)
        self.devices = []
        self.device_names = []
        self.current_device_index = 0
        self.current_device_name = "Default Output"

        self.running = False
        self.thread = None
        self.lock = threading.Lock()

        # Shared state written by audio thread, read by render loop
        self.latest_state = {
            "is_kick": False,
            "is_snare": False,
            "bass_level": 0.0,
            "mid_level": 0.0,
            "high_level": 0.0,
            "total_level": 0.0,
            "spectrum_bars": np.zeros(24, dtype=np.float32),
            "bpm": 0.0,
            "bpm_confidence": 0.0,
            "raw_waveform": np.zeros(CHUNK_SIZE, dtype=np.float32),
        }

        # Demo / Test mode (generates 128 BPM synthetic beats)
        self.demo_mode = False
        self.demo_bpm = 128.0

        # Scan available audio devices
        self.refresh_devices()

    def refresh_devices(self):
        """Discover all loopback output devices and microphones."""
        self.devices = []
        self.device_names = []

        try:
            # Query all microphones including loopback
            all_mics = sc.all_microphones(include_loopback=True)
            default_spk = sc.default_speaker()
            default_spk_name = default_spk.name if default_spk else ""

            # Prioritize default speaker loopback as index 0
            default_loopback = None
            other_loopbacks = []
            physical_mics = []

            for mic in all_mics:
                if mic.isloopback:
                    if default_spk_name and (default_spk_name in mic.name or mic.name in default_spk_name):
                        default_loopback = mic
                    else:
                        other_loopbacks.append(mic)
                else:
                    physical_mics.append(mic)

            # Order: Default Loopback first, then other loopbacks, then physical mics
            sorted_devices = []
            if default_loopback:
                sorted_devices.append(default_loopback)
            sorted_devices.extend(other_loopbacks)
            sorted_devices.extend(physical_mics)

            self.devices = sorted_devices
            for d in self.devices:
                tag = "[System Audio]" if d.isloopback else "[Mic]"
                # Clean up device name for display
                clean_name = d.name.replace("Loopback ", "")
                if len(clean_name) > 32:
                    clean_name = clean_name[:29] + "..."
                self.device_names.append(f"{tag} {clean_name}")

        except Exception as e:
            print(f"Error enumerating audio devices: {e}")

        if not self.devices:
            # Fallback if discovery failed
            try:
                def_spk = sc.default_speaker()
                loopback = sc.get_microphone(id=str(def_spk.name), include_loopback=True)
                self.devices = [loopback]
                self.device_names = ["[System Audio] Default Speaker"]
            except Exception:
                pass

        if self.devices:
            self.current_device_index = 0
            self.current_device_name = self.device_names[0]

    def start(self):
        """Start audio capture thread."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._capture_worker, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop audio capture thread."""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.5)
        self.thread = None

    def cycle_device(self):
        """Switch to the next available audio input/loopback device."""
        if not self.devices:
            return
        next_idx = (self.current_device_index + 1) % len(self.devices)
        self.switch_device(next_idx)

    def switch_device(self, index):
        """Switch to a specific device by index."""
        if not self.devices or index >= len(self.devices) or index == self.current_device_index:
            return
        was_running = self.running
        self.stop()
        self.current_device_index = index
        self.current_device_name = self.device_names[index]
        if was_running:
            self.start()

    def toggle_demo_mode(self):
        """Toggle synthetic demo beat generator."""
        self.demo_mode = not self.demo_mode
        return self.demo_mode

    def set_sensitivity(self, val):
        """Adjust beat detector sensitivity."""
        self.detector.set_sensitivity(val)

    def get_sensitivity(self):
        return self.detector.user_sensitivity

    def get_latest_state(self):
        """Thread-safe retrieval of latest audio state for the render loop."""
        with self.lock:
            # Return copy of state dictionary
            state = dict(self.latest_state)
            # Clear single-frame beat triggers on read so they only fire once
            self.latest_state["is_kick"] = False
            self.latest_state["is_snare"] = False
            return state

    def _capture_worker(self):
        """Worker thread for recording audio and running FFT analysis."""
        device = self.devices[self.current_device_index] if self.devices else None

        # Precompute demo synth signals if demo mode is used
        demo_t = 0.0
        last_demo_time = time.time()

        while self.running:
            if self.demo_mode or device is None:
                # Synthetic 128 BPM beat simulation
                now = time.time()
                dt = now - last_demo_time
                last_demo_time = now
                demo_t += dt

                beat_interval = 60.0 / self.demo_bpm
                phase = (demo_t % beat_interval) / beat_interval
                bar_phase = (demo_t % (beat_interval * 4)) / (beat_interval * 4)

                # Synthetic chunk with kick on every beat, snare on 2 and 4
                t_arr = np.linspace(0, CHUNK_SIZE / SAMPLE_RATE, CHUNK_SIZE, endpoint=False)
                sim_audio = np.zeros(CHUNK_SIZE, dtype=np.float32)

                # Kick transient
                if phase < 0.15:
                    sim_audio += np.sin(2 * np.pi * 55 * t_arr) * np.exp(-phase * 15) * 0.7
                # Snare transient on beats 2 and 4
                beat_num = int((demo_t / beat_interval) % 4)
                if (beat_num == 1 or beat_num == 3) and phase < 0.12:
                    sim_audio += np.random.uniform(-0.4, 0.4, CHUNK_SIZE) * np.exp(-phase * 20)

                result = self.detector.process_audio(sim_audio)
                result["raw_waveform"] = sim_audio

                with self.lock:
                    if result["is_kick"]:
                        self.latest_state["is_kick"] = True
                    if result["is_snare"]:
                        self.latest_state["is_snare"] = True
                    self.latest_state["bass_level"] = result["bass_level"]
                    self.latest_state["mid_level"] = result["mid_level"]
                    self.latest_state["high_level"] = result["high_level"]
                    self.latest_state["total_level"] = result["total_level"]
                    self.latest_state["spectrum_bars"] = result["spectrum_bars"]
                    self.latest_state["bpm"] = self.demo_bpm
                    self.latest_state["bpm_confidence"] = 1.0
                    self.latest_state["raw_waveform"] = sim_audio

                time.sleep(CHUNK_SIZE / SAMPLE_RATE * 0.9)
                continue

            try:
                with device.recorder(samplerate=SAMPLE_RATE, blocksize=CHUNK_SIZE) as recorder:
                    while self.running and not self.demo_mode:
                        data = recorder.record(numframes=CHUNK_SIZE)
                        if data is None or len(data) == 0:
                            time.sleep(0.01)
                            continue

                        # Convert to mono float32
                        if data.ndim > 1:
                            mono = np.mean(data, axis=1).astype(np.float32)
                        else:
                            mono = data.astype(np.float32)

                        # Process FFT and beat detection
                        result = self.detector.process_audio(mono)
                        result["raw_waveform"] = mono

                        with self.lock:
                            if result["is_kick"]:
                                self.latest_state["is_kick"] = True
                            if result["is_snare"]:
                                self.latest_state["is_snare"] = True
                            self.latest_state["bass_level"] = result["bass_level"]
                            self.latest_state["mid_level"] = result["mid_level"]
                            self.latest_state["high_level"] = result["high_level"]
                            self.latest_state["total_level"] = result["total_level"]
                            self.latest_state["spectrum_bars"] = result["spectrum_bars"]
                            self.latest_state["bpm"] = result["bpm"]
                            self.latest_state["bpm_confidence"] = result["bpm_confidence"]
                            self.latest_state["raw_waveform"] = mono

            except Exception as e:
                # Handle transient audio glitches or sleep and retry
                time.sleep(0.2)
