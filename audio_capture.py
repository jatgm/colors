import sys
# Set COM threading flags to COINIT_MULTITHREADED to prevent conflicts between soundcard and pycaw/comtypes
if not hasattr(sys, 'coinit_flags'):
    sys.coinit_flags = 0

import collections
import threading
import time
import numpy as np
import soundcard as sc
from config import SAMPLE_RATE, CHUNK_SIZE
from beat_detector import BeatDetector

PROCTAP_AVAILABLE = False
try:
    import proctap
    import pycaw.pycaw as pycaw
    import psutil
    PROCTAP_AVAILABLE = True
except (ImportError, Exception):
    pass

DEVICE_SPOTIFY = "[App: Spotify] Isolated Audio"


def find_spotify_audio_pid():
    """Locate the active Spotify process ID generating audio."""
    if not PROCTAP_AVAILABLE:
        return None
    spotify_pids = set()
    try:
        for p in psutil.process_iter(['pid', 'name']):
            try:
                if 'spotify' in p.info['name'].lower():
                    spotify_pids.add(p.info['pid'])
            except Exception:
                pass
    except Exception:
        pass

    if not spotify_pids:
        return None

    try:
        sessions = pycaw.AudioUtilities.GetAllSessions()
        for s in sessions:
            proc = s.Process
            if proc and proc.pid in spotify_pids:
                return proc.pid
    except Exception:
        pass

    return list(spotify_pids)[0] if spotify_pids else None


class AudioCaptureManager:
    def __init__(self):
        self.detector = BeatDetector(sample_rate=SAMPLE_RATE, chunk_size=CHUNK_SIZE)
        self.devices = []
        self.device_names = []
        self.current_device_index = 0
        self.current_device_name = "Default Output"
        self.user_selected_device = False

        self.running = False
        self.thread = None
        self.lock = threading.Lock()

        # Shared state written by audio thread, read by render loop
        self.latest_state = {
            "is_kick": False,
            "is_808": False,
            "is_snare": False,
            "is_hihat": False,
            "is_drop": False,
            "sub_bass_level": 0.0,
            "bass_level": 0.0,
            "mid_level": 0.0,
            "high_level": 0.0,
            "hihat_level": 0.0,
            "total_level": 0.0,
            "spectrum_bars": np.zeros(24, dtype=np.float32),
            "bpm": 0.0,
            "bpm_confidence": 0.0,
            "raw_waveform": np.zeros(CHUNK_SIZE, dtype=np.float32),
            "overdrive": True,
            "raw_peak": 0.0,
            "agc_gain": 1.0,
            "preamp_gain": 1.8,
            "chroma": np.zeros(12, dtype=np.float32),
            "pitch_idx": 0,
            "secondary_pitch_idx": 7,
            "pitch_name": "C",
            "pitch_confidence": 0.0,
            "is_chorus": False,
            "is_buildup": False,
            "is_verse": True,
            "section_name": "VERSE",
            "section_energy": 1.0,
        }

        # Demo / Test mode (generates 128 BPM synthetic beats)
        self.demo_mode = False
        self.demo_bpm = 128.0

        # Scan available audio devices
        self.refresh_devices()

    def refresh_devices(self):
        """Discover all loopback output devices and microphones, with System Audio prioritized."""
        self.devices = []
        self.device_names = []

        try:
            all_mics = sc.all_microphones(include_loopback=True)
            default_spk = sc.default_speaker()
            default_spk_name = default_spk.name if default_spk else ""

            default_mic = None
            try:
                default_mic = sc.default_microphone()
            except Exception:
                pass
            default_mic_name = default_mic.name if default_mic else ""

            default_loopback = None
            other_loopbacks = []
            physical_mics = []

            for mic in all_mics:
                name_lower = mic.name.lower()
                is_virtual = any(v in name_lower for v in ("blackhole", "loopback", "soundflower", "vb-cable", "virtual audio", "stereo mix"))
                if mic.isloopback or is_virtual:
                    if default_spk_name and (default_spk_name in mic.name or mic.name in default_spk_name):
                        default_loopback = mic
                    else:
                        other_loopbacks.append(mic)
                else:
                    if default_mic_name and (default_mic_name in mic.name or mic.name in default_mic_name):
                        physical_mics.insert(0, mic)
                    else:
                        physical_mics.append(mic)

            sorted_devices = []
            if default_loopback:
                sorted_devices.append(default_loopback)
            sorted_devices.extend(other_loopbacks)
            sorted_devices.extend(physical_mics)

            for d in sorted_devices:
                self.devices.append(d)
                name_lower = d.name.lower()
                is_virtual = any(v in name_lower for v in ("blackhole", "loopback", "soundflower", "vb-cable", "virtual audio", "stereo mix"))
                tag = "[System Audio]" if (d.isloopback or is_virtual) else "[Mic]"
                clean_name = d.name.replace("Loopback ", "")
                if len(clean_name) > 32:
                    clean_name = clean_name[:29] + "..."
                self.device_names.append(f"{tag} {clean_name}")

        except Exception:
            pass

        # Also provide Spotify Isolated Audio as an optional specialized device
        if PROCTAP_AVAILABLE:
            self.devices.append("spotify")
            self.device_names.append(DEVICE_SPOTIFY)

        if not self.devices:
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
            # Automatically default to Spotify Isolated Audio if Spotify process is running
            if PROCTAP_AVAILABLE and "spotify" in self.devices:
                sp_pid = find_spotify_audio_pid()
                if sp_pid is not None:
                    sp_idx = self.devices.index("spotify")
                    self.current_device_index = sp_idx
                    self.current_device_name = self.device_names[sp_idx]

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._capture_worker, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.5)
        self.thread = None

    def cycle_device(self):
        if not self.devices:
            return
        self.user_selected_device = True
        next_idx = (self.current_device_index + 1) % len(self.devices)
        self.switch_device(next_idx, manual=True)

    def switch_device(self, index, manual=False):
        if manual:
            self.user_selected_device = True
        if not self.devices or index >= len(self.devices) or index == self.current_device_index:
            return
        was_running = self.running
        self.stop()
        self.current_device_index = index
        self.current_device_name = self.device_names[index]
        if was_running:
            self.start()

    def select_device(self, dev_or_name, manual=False):
        """Select a capture device by device object, name string, or index."""
        if manual:
            self.user_selected_device = True
        if not self.devices:
            return False
        if isinstance(dev_or_name, int):
            if 0 <= dev_or_name < len(self.devices):
                if dev_or_name != self.current_device_index:
                    self.switch_device(dev_or_name, manual=manual)
                return True
            return False

        target_str = str(dev_or_name).lower()
        for idx, (dev, name) in enumerate(zip(self.devices, self.device_names)):
            if dev == dev_or_name or dev_or_name == name or target_str in str(dev).lower() or target_str in name.lower():
                if idx != self.current_device_index:
                    self.switch_device(idx, manual=manual)
                return True
        return False

    def auto_select_spotify(self):
        """Auto-switch to Spotify Isolated Audio if Spotify is active and user hasn't manually selected a device."""
        if getattr(self, "user_selected_device", False):
            return False
        if not PROCTAP_AVAILABLE or "spotify" not in self.devices:
            return False
        sp_pid = find_spotify_audio_pid()
        if sp_pid is not None:
            sp_idx = self.devices.index("spotify")
            if self.current_device_index != sp_idx:
                self.switch_device(sp_idx)
                return True
        return False

    def toggle_demo_mode(self):
        self.demo_mode = not self.demo_mode
        return self.demo_mode

    def set_sensitivity(self, val):
        self.detector.set_sensitivity(val)

    def get_sensitivity(self):
        return self.detector.user_sensitivity

    def set_preamp_gain(self, val):
        self.detector.set_preamp_gain(val)

    def get_preamp_gain(self):
        return self.detector.user_gain

    def set_overdrive(self, enabled):
        self.detector.set_overdrive(enabled)
        with self.lock:
            self.latest_state["overdrive"] = enabled

    def set_timeline_context(self, progress, duration=0.0, is_playing=True):
        """Provide Spotify/OS media timeline context to calibrate song section priors."""
        if hasattr(self, "detector") and self.detector:
            self.detector.set_timeline_context(progress, duration, is_playing)

    def get_latest_state(self):
        with self.lock:
            state = dict(self.latest_state)
            self.latest_state["is_kick"] = False
            self.latest_state["is_808"] = False
            self.latest_state["is_snare"] = False
            self.latest_state["is_hihat"] = False
            self.latest_state["is_drop"] = False
            return state

    def _reset_to_silence(self):
        """Immediately reset all audio levels and beat flags to blackout."""
        with self.lock:
            self.latest_state["is_kick"] = False
            self.latest_state["is_808"] = False
            self.latest_state["is_snare"] = False
            self.latest_state["is_hihat"] = False
            self.latest_state["is_drop"] = False
            self.latest_state["sub_bass_level"] = 0.0
            self.latest_state["bass_level"] = 0.0
            self.latest_state["mid_level"] = 0.0
            self.latest_state["high_level"] = 0.0
            self.latest_state["hihat_level"] = 0.0
            self.latest_state["total_level"] = 0.0
            self.latest_state["spectrum_bars"] = np.zeros(24, dtype=np.float32)
            self.latest_state["bpm"] = 0.0
            self.latest_state["bpm_confidence"] = 0.0
            self.latest_state["raw_waveform"] = np.zeros(CHUNK_SIZE, dtype=np.float32)
            self.latest_state["raw_peak"] = 0.0
            self.latest_state["chroma"] = np.zeros(12, dtype=np.float32)
            self.latest_state["pitch_idx"] = 0
            self.latest_state["secondary_pitch_idx"] = 7
            self.latest_state["pitch_name"] = "C"
            self.latest_state["pitch_confidence"] = 0.0
            self.latest_state["is_chorus"] = False
            self.latest_state["section_energy"] = 0.0

    def _capture_spotify_worker(self):
        """Capture isolated Spotify process audio via WASAPI process loopback."""
        audio_buffer = collections.deque(maxlen=SAMPLE_RATE * 2)
        last_data_time = [time.time()]

        def _on_audio(data, *args):
            if not data:
                return
            try:
                samples = np.frombuffer(data, dtype=np.float32)
                if len(samples) % 2 != 0:
                    return
                stereo = samples.reshape(-1, 2)
                mono = np.mean(stereo, axis=1)
                audio_buffer.extend(mono)
                last_data_time[0] = time.time()
            except Exception:
                pass

        while self.running and not self.demo_mode and self.devices and self.devices[self.current_device_index] == "spotify":
            pid = find_spotify_audio_pid()
            if not pid:
                self._reset_to_silence()
                time.sleep(0.5)
                continue

            try:
                cap = proctap.ProcessAudioCapture(pid, on_data=_on_audio)
                cap.start()
                last_data_time[0] = time.time()

                while self.running and not self.demo_mode and self.devices and self.devices[self.current_device_index] == "spotify":
                    now = time.time()
                    # If Spotify paused or stopped emitting data for > 0.35s, blackout
                    if now - last_data_time[0] > 0.35:
                        self._reset_to_silence()
                        audio_buffer.clear()
                        time.sleep(0.05)
                        # Check if process died
                        if not psutil.pid_exists(pid):
                            break
                        continue

                    # Process accumulated audio in CHUNK_SIZE pieces
                    processed_any = False
                    while len(audio_buffer) >= CHUNK_SIZE:
                        processed_any = True
                        chunk = np.array([audio_buffer.popleft() for _ in range(CHUNK_SIZE)], dtype=np.float32)
                        result = self.detector.process_audio(chunk)
                        result["raw_waveform"] = chunk

                        with self.lock:
                            if result["is_kick"]:
                                self.latest_state["is_kick"] = True
                            if result.get("is_808"):
                                self.latest_state["is_808"] = True
                            if result["is_snare"]:
                                self.latest_state["is_snare"] = True
                            if result["is_hihat"]:
                                self.latest_state["is_hihat"] = True
                            if result["is_drop"]:
                                self.latest_state["is_drop"] = True

                            self.latest_state["sub_bass_level"] = result.get("sub_bass_level", 0.0)
                            self.latest_state["bass_level"] = result["bass_level"]
                            self.latest_state["mid_level"] = result["mid_level"]
                            self.latest_state["high_level"] = result["high_level"]
                            self.latest_state["hihat_level"] = result["hihat_level"]
                            self.latest_state["total_level"] = result["total_level"]
                            self.latest_state["spectrum_bars"] = result["spectrum_bars"]
                            self.latest_state["bpm"] = result["bpm"]
                            self.latest_state["bpm_confidence"] = result["bpm_confidence"]
                            self.latest_state["raw_waveform"] = chunk
                            self.latest_state["raw_peak"] = result.get("raw_peak", 0.0)
                            self.latest_state["agc_gain"] = result.get("agc_gain", 1.0)
                            self.latest_state["preamp_gain"] = result.get("preamp_gain", 1.8)
                            self.latest_state["chroma"] = result.get("chroma", np.zeros(12, dtype=np.float32))
                            self.latest_state["pitch_idx"] = result.get("pitch_idx", 0)
                            self.latest_state["secondary_pitch_idx"] = result.get("secondary_pitch_idx", 7)
                            self.latest_state["pitch_name"] = result.get("pitch_name", "C")
                            self.latest_state["pitch_confidence"] = result.get("pitch_confidence", 0.0)
                            self.latest_state["is_chorus"] = result.get("is_chorus", False)
                            self.latest_state["is_buildup"] = result.get("is_buildup", False)
                            self.latest_state["is_verse"] = result.get("is_verse", True)
                            self.latest_state["section_name"] = result.get("section_name", "VERSE")
                            self.latest_state["section_energy"] = result.get("section_energy", 1.0)

                    if not processed_any:
                        time.sleep(0.005)

                try:
                    cap.stop()
                    cap.close()
                except Exception:
                    pass

            except Exception:
                self._reset_to_silence()
                time.sleep(0.5)

    def _capture_worker(self):
        device = self.devices[self.current_device_index] if self.devices else None

        # Dispatch to dedicated Spotify isolated capture worker
        if device == "spotify":
            self._capture_spotify_worker()
            return

        demo_t = 0.0
        last_demo_time = time.time()

        while self.running:
            if self.demo_mode or device is None:
                now = time.time()
                dt = now - last_demo_time
                last_demo_time = now
                demo_t += dt

                beat_interval = 60.0 / self.demo_bpm
                phase = (demo_t % beat_interval) / beat_interval

                t_arr = np.linspace(0, CHUNK_SIZE / SAMPLE_RATE, CHUNK_SIZE, endpoint=False)
                sim_audio = np.zeros(CHUNK_SIZE, dtype=np.float32)

                # Kick transient
                if phase < 0.15:
                    sim_audio += np.sin(2 * np.pi * 55 * t_arr) * np.exp(-phase * 15) * 0.75

                # Snare on beats 2 and 4
                beat_num = int((demo_t / beat_interval) % 4)
                if (beat_num == 1 or beat_num == 3) and phase < 0.12:
                    sim_audio += np.random.uniform(-0.4, 0.4, CHUNK_SIZE) * np.exp(-phase * 20)

                # Fast 16th-note hi-hat sizzle
                sixteenth_phase = (demo_t % (beat_interval / 4)) / (beat_interval / 4)
                if sixteenth_phase < 0.10:
                    sim_audio += np.random.uniform(-0.35, 0.35, CHUNK_SIZE) * np.sin(2 * np.pi * 10000 * t_arr)

                result = self.detector.process_audio(sim_audio)
                result["raw_waveform"] = sim_audio

                with self.lock:
                    if result["is_kick"]:
                        self.latest_state["is_kick"] = True
                    if result.get("is_808"):
                        self.latest_state["is_808"] = True
                    if result["is_snare"]:
                        self.latest_state["is_snare"] = True
                    if result["is_hihat"]:
                        self.latest_state["is_hihat"] = True
                    if result["is_drop"]:
                        self.latest_state["is_drop"] = True

                    self.latest_state["sub_bass_level"] = result.get("sub_bass_level", 0.0)
                    self.latest_state["bass_level"] = result["bass_level"]
                    self.latest_state["mid_level"] = result["mid_level"]
                    self.latest_state["high_level"] = result["high_level"]
                    self.latest_state["hihat_level"] = result["hihat_level"]
                    self.latest_state["total_level"] = result["total_level"]
                    self.latest_state["spectrum_bars"] = result["spectrum_bars"]
                    self.latest_state["bpm"] = self.demo_bpm
                    self.latest_state["bpm_confidence"] = 1.0
                    self.latest_state["raw_waveform"] = sim_audio
                    self.latest_state["raw_peak"] = result.get("raw_peak", 0.0)
                    self.latest_state["agc_gain"] = result.get("agc_gain", 1.0)
                    self.latest_state["preamp_gain"] = result.get("preamp_gain", 1.8)
                    self.latest_state["chroma"] = result.get("chroma", np.zeros(12, dtype=np.float32))
                    self.latest_state["pitch_idx"] = result.get("pitch_idx", 0)
                    self.latest_state["secondary_pitch_idx"] = result.get("secondary_pitch_idx", 7)
                    self.latest_state["pitch_name"] = result.get("pitch_name", "C")
                    self.latest_state["pitch_confidence"] = result.get("pitch_confidence", 0.0)
                    self.latest_state["is_chorus"] = result.get("is_chorus", False)
                    self.latest_state["is_buildup"] = result.get("is_buildup", False)
                    self.latest_state["is_verse"] = result.get("is_verse", True)
                    self.latest_state["section_name"] = result.get("section_name", "VERSE")
                    self.latest_state["section_energy"] = result.get("section_energy", 1.0)

                time.sleep(CHUNK_SIZE / SAMPLE_RATE * 0.85)
                continue

            try:
                with device.recorder(samplerate=SAMPLE_RATE, blocksize=CHUNK_SIZE) as recorder:
                    while self.running and not self.demo_mode:
                        data = recorder.record(numframes=CHUNK_SIZE)
                        if data is None or len(data) == 0:
                            time.sleep(0.01)
                            continue

                        if data.ndim > 1:
                            mono = np.mean(data, axis=1).astype(np.float32)
                        else:
                            mono = data.astype(np.float32)

                        result = self.detector.process_audio(mono)
                        result["raw_waveform"] = mono

                        with self.lock:
                            if result["is_kick"]:
                                self.latest_state["is_kick"] = True
                            if result.get("is_808"):
                                self.latest_state["is_808"] = True
                            if result["is_snare"]:
                                self.latest_state["is_snare"] = True
                            if result["is_hihat"]:
                                self.latest_state["is_hihat"] = True
                            if result["is_drop"]:
                                self.latest_state["is_drop"] = True

                            self.latest_state["sub_bass_level"] = result.get("sub_bass_level", 0.0)
                            self.latest_state["bass_level"] = result["bass_level"]
                            self.latest_state["mid_level"] = result["mid_level"]
                            self.latest_state["high_level"] = result["high_level"]
                            self.latest_state["hihat_level"] = result["hihat_level"]
                            self.latest_state["total_level"] = result["total_level"]
                            self.latest_state["spectrum_bars"] = result["spectrum_bars"]
                            self.latest_state["bpm"] = result["bpm"]
                            self.latest_state["bpm_confidence"] = result["bpm_confidence"]
                            self.latest_state["raw_waveform"] = mono
                            self.latest_state["raw_peak"] = result.get("raw_peak", 0.0)
                            self.latest_state["agc_gain"] = result.get("agc_gain", 1.0)
                            self.latest_state["preamp_gain"] = result.get("preamp_gain", 1.8)
                            self.latest_state["chroma"] = result.get("chroma", np.zeros(12, dtype=np.float32))
                            self.latest_state["pitch_idx"] = result.get("pitch_idx", 0)
                            self.latest_state["secondary_pitch_idx"] = result.get("secondary_pitch_idx", 7)
                            self.latest_state["pitch_name"] = result.get("pitch_name", "C")
                            self.latest_state["pitch_confidence"] = result.get("pitch_confidence", 0.0)
                            self.latest_state["is_chorus"] = result.get("is_chorus", False)
                            self.latest_state["is_buildup"] = result.get("is_buildup", False)
                            self.latest_state["is_verse"] = result.get("is_verse", True)
                            self.latest_state["section_name"] = result.get("section_name", "VERSE")
                            self.latest_state["section_energy"] = result.get("section_energy", 1.0)

            except Exception:
                time.sleep(0.2)
