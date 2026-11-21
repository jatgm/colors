"""
Audio analysis and beat detection engine.
Features Dynamic Automatic Gain Control (AGC) and Pre-Amp boosting to ensure
visualizer meters and beat detection are punchy and active across all volume levels.
"""

import time
from collections import deque
import numpy as np
from config import (
    SAMPLE_RATE,
    CHUNK_SIZE,
    BASS_FREQ_RANGE,
    MID_FREQ_RANGE,
    HIGH_FREQ_RANGE,
    HIHAT_FREQ_RANGE,
    KICK_COOLDOWN,
    SNARE_COOLDOWN,
    HIHAT_COOLDOWN,
    OVERDRIVE_KICK_COOLDOWN,
    OVERDRIVE_SNARE_COOLDOWN,
    OVERDRIVE_HIHAT_COOLDOWN,
    DEFAULT_PREAMP_GAIN,
    MIN_PREAMP_GAIN,
    MAX_PREAMP_GAIN,
)


class BeatDetector:
    def __init__(self, sample_rate=SAMPLE_RATE, chunk_size=CHUNK_SIZE):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.freq_bin_width = sample_rate / chunk_size

        # Precompute frequency bin indices
        # Bass bins 1 to 7 (~43Hz to 300Hz): kick fundamentals and punch
        self.sub_bass_bins = (
            max(1, int(25.0 / self.freq_bin_width)),
            max(2, int(115.0 / self.freq_bin_width)),
        )
        self.bass_bins = (
            max(1, int(BASS_FREQ_RANGE[0] / self.freq_bin_width)),
            max(4, int(BASS_FREQ_RANGE[1] / self.freq_bin_width)),
        )
        self.mid_bins = (
            int(MID_FREQ_RANGE[0] / self.freq_bin_width),
            int(MID_FREQ_RANGE[1] / self.freq_bin_width),
        )
        self.high_bins = (
            int(HIGH_FREQ_RANGE[0] / self.freq_bin_width),
            min(chunk_size // 2, int(HIGH_FREQ_RANGE[1] / self.freq_bin_width)),
        )
        self.hihat_bins = (
            int(HIHAT_FREQ_RANGE[0] / self.freq_bin_width),
            min(chunk_size // 2, int(HIHAT_FREQ_RANGE[1] / self.freq_bin_width)),
        )

        self.window = np.hanning(chunk_size)

        # Dynamic Automatic Gain Control (AGC) state
        self.rolling_peak = 0.05
        self.user_gain = DEFAULT_PREAMP_GAIN  # Pre-amp boost multiplier
        self.current_agc_gain = 1.0
        self.raw_input_peak = 0.0

        # Rolling history buffers for adaptive dynamic thresholding
        history_len = 35
        self.sub_flux_history = deque(maxlen=history_len)
        self.sub_energy_history = deque(maxlen=history_len)
        self.bass_flux_history = deque(maxlen=history_len)
        self.high_flux_history = deque(maxlen=history_len)
        self.hihat_flux_history = deque(maxlen=history_len)
        self.total_energy_history = deque(maxlen=history_len)
        self.bass_energy_history = deque(maxlen=history_len)

        # Previous frame energies for spectral flux
        self.prev_sub_bass_energy = 0.0
        self.prev_bass_energy = 0.0
        self.prev_high_energy = 0.0
        self.prev_hihat_energy = 0.0
        self.prev_total_energy = 0.0

        # Beat detection cooldowns
        self.last_kick_time = 0.0
        self.last_snare_time = 0.0
        self.last_hihat_time = 0.0

        # Overdrive / Crazy Mode toggle (Smart Rhythmic Mode default)
        self.overdrive_mode = False

        # Smart Rhythm Mode (PLL Grid & Transient Isolation) vs Classic Rapid Strobe (How it was before)
        self.smart_mode = True

        # Phase-Locked Loop (PLL) & Intelligent Rhythm Grid
        self.last_grid_anchor = 0.0
        self.beat_phase = 0.0
        self.is_on_grid_downbeat = False
        self.is_on_grid_backbeat = False

        # Transient attack vs sustain separation for 808s and heavy bass
        self.last_808_time = 0.0
        self.prev_hfc = 0.0
        self.hfc_history = deque(maxlen=history_len)

        # Sensitivity: higher = more sensitive
        self.user_sensitivity = 1.4

        # Peak normalized levels for visualizer meters
        self.sub_bass_level = 0.0
        self.bass_level = 0.0
        self.mid_level = 0.0
        self.high_level = 0.0
        self.hihat_level = 0.0
        self.total_level = 0.0

        # 24-band spectrum visualizer output
        self.num_spectrum_bars = 24
        self.spectrum_bars = np.zeros(self.num_spectrum_bars, dtype=np.float32)
        self._setup_spectrum_bands()

        # BPM tracking
        self.beat_timestamps = deque(maxlen=16)
        self.estimated_bpm = 0.0
        self.bpm_confidence = 0.0

        # Melody & 12-Semitone Pitch Chroma Tracking
        self.note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        self._setup_chroma_bins()
        self.chroma_vector = np.zeros(12, dtype=np.float32)
        self.dominant_pitch_idx = 0
        self.secondary_pitch_idx = 7
        self.pitch_confidence = 0.0

        # Macro Song Structure & Dynamic Section Tracking (Verse, Buildup, Chorus)
        self.macro_energy_history = deque(maxlen=220)   # ~5 seconds of recent energy
        self.long_energy_history = deque(maxlen=650)    # ~15 seconds long-term baseline
        self.high_energy_history = deque(maxlen=120)    # High-frequency trend for risers
        self.phrase_energy = 0.0                        # Normalized phrase moving average (~1.2s)
        self.long_energy = 0.0                          # Normalized macro moving average (~8.0s)
        self.smoothed_section_rms = 0.0                 # Exponentially smoothed RMS
        self.chorus_hold_frames = 0                     # Minimum sustain frames for chorus
        self.buildup_hold_frames = 0                    # Minimum sustain frames for buildup
        self.is_chorus = False
        self.is_buildup = False
        self.is_verse = True
        self.section_name = "VERSE"                     # "VERSE", "BUILDUP", or "CHORUS"
        self.section_energy = 0.0

        # Spotify / Media Timeline priors
        self.timeline_progress = None
        self.timeline_duration = 0.0
        self.timeline_is_playing = False

    def set_timeline_context(self, progress, duration=0.0, is_playing=True):
        """Calibrate song section recognition using Spotify/Windows Media timeline priors."""
        self.timeline_progress = float(progress) if progress is not None else None
        self.timeline_duration = float(duration) if duration is not None else 0.0
        self.timeline_is_playing = bool(is_playing)

    def _setup_chroma_bins(self):
        """Map FFT bins in 65Hz - 2100Hz range to 12 musical pitch classes (C to B)."""
        freqs = np.fft.rfftfreq(self.chunk_size, 1.0 / self.sample_rate)
        valid = np.where((freqs >= 65.0) & (freqs <= 2100.0))[0]
        self.chroma_valid_indices = valid
        if len(valid) > 0:
            midi_notes = 69.0 + 12.0 * np.log2(np.maximum(1.0, freqs[valid]) / 440.0)
            self.chroma_bin_pitch_classes = (np.round(midi_notes).astype(int) % 12).tolist()
        else:
            self.chroma_bin_pitch_classes = []

    def _setup_spectrum_bands(self):
        log_freqs = np.logspace(np.log10(30), np.log10(14000), self.num_spectrum_bars + 1)
        self.band_ranges = []
        for i in range(self.num_spectrum_bars):
            low_b = max(1, int(log_freqs[i] / self.freq_bin_width))
            high_b = max(low_b + 1, int(log_freqs[i + 1] / self.freq_bin_width))
            self.band_ranges.append((low_b, high_b))

    def set_sensitivity(self, val):
        self.user_sensitivity = max(0.5, min(3.5, float(val)))

    def set_preamp_gain(self, val):
        self.user_gain = max(MIN_PREAMP_GAIN, min(MAX_PREAMP_GAIN, float(val)))

    def set_overdrive(self, enabled):
        self.overdrive_mode = bool(enabled)

    def set_smart_mode(self, enabled):
        self.smart_mode = bool(enabled)

    def process_audio(self, audio_data):
        now = time.time()

        # Ensure mono float
        if audio_data.ndim > 1:
            mono = np.mean(audio_data, axis=1).astype(np.float32)
        else:
            mono = audio_data.astype(np.float32)

        if len(mono) != self.chunk_size:
            if len(mono) < self.chunk_size:
                mono = np.pad(mono, (0, self.chunk_size - len(mono)))
            else:
                mono = mono[:self.chunk_size]

        # 1. Measure raw input peak and RMS energy
        raw_peak = float(np.max(np.abs(mono)))
        raw_rms = float(np.sqrt(np.mean(mono**2)))
        self.raw_input_peak = raw_peak

        # Silence / Noise Floor Threshold:
        # Background microphone hiss, fan noise, or idle desktop audio loopback typically < 0.0045 RMS and < 0.020 Peak.
        is_silence = (raw_rms < 0.0045) and (raw_peak < 0.020)
        if is_silence:
            # Below noise floor: freeze AGC from inflating noise and decay visual meters to zero
            self.rolling_peak = max(0.010, self.rolling_peak * 0.995)
            self.current_agc_gain = min(15.0, 0.80 / self.rolling_peak) * self.user_gain

            self.bass_level = max(0.0, self.bass_level * 0.65)
            self.mid_level = max(0.0, self.mid_level * 0.65)
            self.high_level = max(0.0, self.high_level * 0.65)
            self.hihat_level = max(0.0, self.hihat_level * 0.65)
            self.total_level = max(0.0, self.total_level * 0.65)
            self.spectrum_bars *= 0.70

            self.prev_bass_energy = 0.0
            self.prev_high_energy = 0.0
            self.prev_hihat_energy = 0.0
            self.prev_total_energy = 0.0
            self.bass_flux_history.append(0.0)
            self.high_flux_history.append(0.0)
            self.hihat_flux_history.append(0.0)
            self.total_energy_history.append(0.0)
            self.bass_energy_history.append(0.0)

            return {
                "is_kick": False,
                "is_808": False,
                "is_snare": False,
                "is_hihat": False,
                "is_drop": False,
                "beat_phase": 0.0,
                "is_downbeat": False,
                "is_backbeat": False,
                "bass_level": min(1.0, float(self.bass_level)),
                "mid_level": min(1.0, float(self.mid_level)),
                "high_level": min(1.0, float(self.high_level)),
                "hihat_level": min(1.0, float(self.hihat_level)),
                "total_level": min(1.0, float(self.total_level)),
                "spectrum_bars": self.spectrum_bars,
                "bpm": float(self.estimated_bpm),
                "bpm_confidence": float(self.bpm_confidence),
                "overdrive": self.overdrive_mode,
                "raw_peak": float(self.raw_input_peak),
                "agc_gain": float(self.current_agc_gain),
                "preamp_gain": float(self.user_gain),
                "chroma": self.chroma_vector,
                "pitch_idx": int(self.dominant_pitch_idx),
                "pitch_name": self.note_names[self.dominant_pitch_idx],
                "pitch_confidence": 0.0,
                "is_chorus": False,
                "section_energy": 0.0,
            }

        # 2. Dynamic Automatic Gain Control (AGC)
        # Fast attack, slow release tracking
        if raw_peak > self.rolling_peak:
            self.rolling_peak = raw_peak * 0.85 + self.rolling_peak * 0.15
        else:
            self.rolling_peak = max(0.008, self.rolling_peak * 0.992)

        # Calculate automatic scaling factor (capped at 60x max gain)
        # Target peak is ~0.80 full scale
        auto_gain = min(60.0, 0.80 / max(0.008, self.rolling_peak))
        total_gain = auto_gain * self.user_gain
        self.current_agc_gain = total_gain

        # Normalize audio chunk using AGC gain
        norm_audio = np.clip(mono * total_gain, -1.2, 1.2)

        # 3. FFT Analysis on Normalized Audio
        windowed = norm_audio * self.window
        fft_complex = np.fft.rfft(windowed)
        fft_mag = np.abs(fft_complex) / (self.chunk_size / 2)

        # 4. Band Energies
        sub_slice = fft_mag[self.sub_bass_bins[0]:self.sub_bass_bins[1]]
        bass_slice = fft_mag[self.bass_bins[0]:self.bass_bins[1]]
        mid_slice = fft_mag[self.mid_bins[0]:self.mid_bins[1]]
        high_slice = fft_mag[self.high_bins[0]:self.high_bins[1]]
        hihat_slice = fft_mag[self.hihat_bins[0]:self.hihat_bins[1]]

        curr_sub_bass = float(np.sqrt(np.mean(sub_slice**2))) if len(sub_slice) > 0 else 0.0
        curr_bass = float(np.sqrt(np.mean(bass_slice**2))) if len(bass_slice) > 0 else 0.0
        curr_mid = float(np.sqrt(np.mean(mid_slice**2))) if len(mid_slice) > 0 else 0.0
        curr_high = float(np.sqrt(np.mean(high_slice**2))) if len(high_slice) > 0 else 0.0
        curr_hihat = float(np.sqrt(np.mean(hihat_slice**2))) if len(hihat_slice) > 0 else 0.0
        curr_total = float(np.sqrt(np.mean(fft_mag[1:]**2)))

        # 5. Spectral Flux (Attack / Rising Edge)
        sub_flux = max(0.0, curr_sub_bass - self.prev_sub_bass_energy)
        bass_flux = max(0.0, curr_bass - self.prev_bass_energy)
        high_flux = max(0.0, curr_high - self.prev_high_energy)
        hihat_flux = max(0.0, curr_hihat - self.prev_hihat_energy)
        total_flux = max(0.0, curr_total - self.prev_total_energy)

        self.prev_sub_bass_energy = curr_sub_bass
        self.prev_bass_energy = curr_bass
        self.prev_high_energy = curr_high
        self.prev_hihat_energy = curr_hihat
        self.prev_total_energy = curr_total

        self.sub_flux_history.append(sub_flux)
        self.sub_energy_history.append(curr_sub_bass)
        self.bass_flux_history.append(bass_flux)
        self.high_flux_history.append(high_flux)
        self.hihat_flux_history.append(hihat_flux)
        self.total_energy_history.append(curr_total)
        self.bass_energy_history.append(curr_bass)

        # Percussive High-Frequency Content (HFC) for transient crack extraction
        num_fft = len(fft_mag)
        weights = np.linspace(1.0, 8.0, num_fft, dtype=np.float32)
        hfc_val = float(np.sum(weights * (fft_mag ** 1.3))) / max(1.0, float(num_fft))
        hfc_flux = max(0.0, hfc_val - self.prev_hfc)
        self.prev_hfc = hfc_val
        self.hfc_history.append(hfc_flux)

        is_smart_active = bool(self.smart_mode and not self.overdrive_mode)

        # Phase-Locked Loop (PLL) & Intelligent Rhythm Grid Expectation
        if is_smart_active and self.estimated_bpm > 45.0 and self.bpm_confidence > 0.20:
            beat_period = 60.0 / self.estimated_bpm
            if self.last_grid_anchor == 0.0:
                self.last_grid_anchor = now
            dt_anchor = max(0.0, now - self.last_grid_anchor)
            phi = (dt_anchor / beat_period) % 1.0
            self.beat_phase = phi

            dist_downbeat = min(phi, 1.0 - phi)
            dist_backbeat = abs(phi - 0.5)
            dist_16th = min(abs(phi - 0.25), abs(phi - 0.75))
            dist_grid = min(dist_downbeat, dist_backbeat, dist_16th)

            self.is_on_grid_downbeat = (dist_downbeat < 0.12)
            self.is_on_grid_backbeat = (dist_backbeat < 0.10)

            if self.is_on_grid_downbeat:
                grid_mult = 0.85
            elif self.is_on_grid_backbeat:
                grid_mult = 0.92
            elif dist_16th < 0.08:
                grid_mult = 1.05
            else:
                dead_zone_ratio = min(1.0, (dist_grid - 0.08) / 0.12)
                grid_mult = 1.0 + 0.60 * dead_zone_ratio * self.bpm_confidence
        else:
            self.beat_phase = 0.0
            self.is_on_grid_downbeat = True
            self.is_on_grid_backbeat = True
            grid_mult = 1.0
            beat_period = 0.50

        # Cooldowns and Threshold multipliers based on Smart vs Classic / Overdrive
        if is_smart_active:
            if self.estimated_bpm > 45.0:
                k_cd = max(0.12, min(0.24, beat_period * 0.40))
                s_cd = max(0.10, min(0.20, beat_period * 0.36))
                h_cd = max(0.06, min(0.14, beat_period * 0.22))
            else:
                k_cd = 0.14
                s_cd = 0.11
                h_cd = 0.07
            base_mult = 1.50 / max(0.1, self.user_sensitivity)
            gate = 0.024
            sub_gate = 0.022
        elif self.overdrive_mode:
            k_cd = OVERDRIVE_KICK_COOLDOWN
            s_cd = OVERDRIVE_SNARE_COOLDOWN
            h_cd = OVERDRIVE_HIHAT_COOLDOWN
            base_mult = 1.05 / max(0.1, self.user_sensitivity)
            gate = 0.015
            sub_gate = 0.014
        else:
            # Classic Rapid Strobe (How it was before)
            k_cd = KICK_COOLDOWN
            s_cd = SNARE_COOLDOWN
            h_cd = HIHAT_COOLDOWN
            base_mult = 1.55 / max(0.1, self.user_sensitivity)
            gate = 0.025
            sub_gate = 0.022

        # 6. Dynamic Threshold for Kick (Punch) & 808 Sub-Bass
        is_kick_beat = False
        is_808 = False

        # 808 Attack Transient vs Sustain Resonance Separation (Smart Mode only)
        mean_hfc = float(np.mean(self.hfc_history)) if len(self.hfc_history) >= 4 else 0.0
        dynamic_thresh_estimate = float(np.mean(self.bass_flux_history)) if len(self.bass_flux_history) >= 4 else 0.02
        if is_smart_active and (now - self.last_808_time < 0.20):
            is_attack_transient = (bass_flux > dynamic_thresh_estimate * 1.35 or hfc_flux > mean_hfc * 1.4)
        else:
            is_attack_transient = True

        if len(self.bass_flux_history) >= 8:
            flux_mean = float(np.mean(self.bass_flux_history))
            flux_std = float(np.std(self.bass_flux_history))
            bass_mean = float(np.mean(self.bass_energy_history))

            dynamic_thresh = flux_mean + (base_mult * 0.55 * grid_mult) * flux_std

            if (
                bass_flux > dynamic_thresh
                and curr_bass > gate
                and curr_bass > (bass_mean * (1.02 if (self.overdrive_mode or not is_smart_active) else 1.05))
                and (now - self.last_kick_time >= k_cd)
                and is_attack_transient
            ):
                is_kick_beat = True

        # Specialized 808 Sub-Bass Impact (30Hz - 110Hz fundamental rumble)
        if len(self.sub_flux_history) >= 8:
            sub_mean = float(np.mean(self.sub_flux_history))
            sub_std = float(np.std(self.sub_flux_history))
            sub_thresh = sub_mean + (base_mult * 0.52 * grid_mult) * sub_std

            if (
                sub_flux > sub_thresh
                and curr_sub_bass > sub_gate
                and (now - self.last_kick_time >= k_cd)
                and is_attack_transient
            ):
                is_808 = True
                is_kick_beat = True
                self.last_808_time = now

        if is_kick_beat:
            self.last_kick_time = now
            self._update_bpm(now)
            if is_smart_active and self.estimated_bpm > 45.0 and self.bpm_confidence > 0.20:
                T_beat = 60.0 / self.estimated_bpm
                offset = (now - self.last_grid_anchor) % T_beat
                if offset < T_beat * 0.35:
                    self.last_grid_anchor = now - (offset * 0.25)
                elif offset > T_beat * 0.6:
                    self.last_grid_anchor = now - (offset * 0.25)
            else:
                self.last_grid_anchor = now

        # 7. Dynamic Threshold for Snare
        is_snare_beat = False
        if len(self.high_flux_history) >= 8:
            high_mean = float(np.mean(self.high_flux_history))
            high_std = float(np.std(self.high_flux_history))
            snare_grid_factor = 0.88 if (is_smart_active and self.is_on_grid_backbeat) else (1.0 if not is_smart_active else 1.15)
            high_thresh = high_mean + (base_mult * 0.65 * snare_grid_factor) * high_std

            is_pure_snare = (curr_sub_bass < 0.16 or curr_high > curr_sub_bass * 0.75) if is_smart_active else True
            if (
                high_flux > high_thresh
                and curr_high > 0.012
                and (now - self.last_snare_time >= s_cd)
                and is_pure_snare
            ):
                is_snare_beat = True
                self.last_snare_time = now

        # 8. Dynamic Threshold for Hi-Hats
        is_hihat_beat = False
        if len(self.hihat_flux_history) >= 8:
            hihat_mean = float(np.mean(self.hihat_flux_history))
            hihat_std = float(np.std(self.hihat_flux_history))
            hihat_thresh = hihat_mean + (base_mult * 0.70) * hihat_std

            if (
                hihat_flux > hihat_thresh
                and curr_hihat > 0.008
                and (now - self.last_hihat_time >= h_cd)
            ):
                is_hihat_beat = True
                self.last_hihat_time = now

        # 9. Heavy Drop Detection
        is_drop = False
        if len(self.total_energy_history) >= 10:
            avg_tot = float(np.mean(self.total_energy_history))
            if curr_total > avg_tot * 1.6 and curr_bass > 0.12:
                is_drop = True

        # 10. Perceptual Loudness Curve for Visual Meters (Power curve mapping)
        # Raw RMS energies map into punchy 0% - 100% meter heights
        target_sub = min(1.0, float((curr_sub_bass * 2.8) ** 0.55))
        target_bass = min(1.0, float((curr_bass * 2.6) ** 0.55))
        target_mid = min(1.0, float((curr_mid * 3.2) ** 0.60))
        target_high = min(1.0, float((curr_high * 4.0) ** 0.65))
        target_hihat = min(1.0, float((curr_hihat * 5.0) ** 0.70))
        target_total = min(1.0, float((curr_total * 2.8) ** 0.60))

        rise_rate = 0.80 if self.overdrive_mode else 0.70
        decay_rate = 0.18 if self.overdrive_mode else 0.14

        self.sub_bass_level = self._smooth_level(self.sub_bass_level, target_sub, rise_rate, decay_rate)
        self.bass_level = self._smooth_level(self.bass_level, target_bass, rise_rate, decay_rate)
        self.mid_level = self._smooth_level(self.mid_level, target_mid, rise_rate, decay_rate)
        self.high_level = self._smooth_level(self.high_level, target_high, rise_rate, decay_rate)
        self.hihat_level = self._smooth_level(self.hihat_level, target_hihat, rise_rate, decay_rate)
        self.total_level = self._smooth_level(self.total_level, target_total, rise_rate, decay_rate)

        # 11. 24-Band Spectrum Visualizer Bars
        for i, (b_start, b_end) in enumerate(self.band_ranges):
            segment = fft_mag[b_start:b_end]
            if len(segment) > 0:
                band_energy = float(np.sqrt(np.mean(segment**2)))
                weight = 2.4 + (i * 0.35)
                # Power curve for vibrant bar movement
                target = min(1.0, float((band_energy * weight) ** 0.65))
            else:
                target = 0.0

            if target > self.spectrum_bars[i]:
                self.spectrum_bars[i] = target
            else:
                self.spectrum_bars[i] = max(0.0, self.spectrum_bars[i] * 0.84)

        # 12. Melody & 12-Semitone Pitch Chroma Extraction
        raw_chroma = np.zeros(12, dtype=np.float32)
        if len(self.chroma_valid_indices) > 0 and len(self.chroma_bin_pitch_classes) > 0:
            for bin_idx, pitch_class in zip(self.chroma_valid_indices, self.chroma_bin_pitch_classes):
                if bin_idx < len(fft_mag):
                    raw_chroma[pitch_class] += fft_mag[bin_idx]

        chroma_sum = float(np.sum(raw_chroma))
        if chroma_sum > 0.001:
            norm_chroma = raw_chroma / chroma_sum
            # Instantaneous top pitch from current frame
            self.dominant_pitch_idx = int(np.argmax(norm_chroma))
            # Secondary harmonic pitch
            sorted_pitches = np.argsort(norm_chroma)[::-1]
            self.secondary_pitch_idx = int(sorted_pitches[1]) if len(sorted_pitches) > 1 else (self.dominant_pitch_idx + 7) % 12
            # Exponential smoothing on chroma vector
            self.chroma_vector = self.chroma_vector * 0.60 + norm_chroma * 0.40
            # Pitch confidence: ratio of top pitch over mean pitch
            mean_c = float(np.mean(norm_chroma))
            self.pitch_confidence = min(1.0, max(0.0, float((norm_chroma[self.dominant_pitch_idx] - mean_c) * 3.5)))
        else:
            self.chroma_vector *= 0.85
            self.pitch_confidence = 0.0
            self.secondary_pitch_idx = (self.dominant_pitch_idx + 7) % 12

        # 13. Intelligent Song Section Tracking (Verse, Buildup, Chorus)
        # Volume-independent, multi-measure phrase analysis with Schmitt-trigger hysteresis
        norm_rms = float(np.sqrt(np.mean(norm_audio**2)))

        if self.phrase_energy == 0.0:
            self.phrase_energy = curr_total
            self.long_energy = curr_total
            self.smoothed_section_rms = norm_rms
        else:
            # Phrase energy smooths over ~1.2s (~50 chunks)
            self.phrase_energy = self.phrase_energy * 0.96 + curr_total * 0.04
            # Long-term baseline smooths over ~8.0s (~350 chunks)
            self.long_energy = self.long_energy * 0.996 + curr_total * 0.004
            self.smoothed_section_rms = self.smoothed_section_rms * 0.94 + norm_rms * 0.06

        self.macro_energy_history.append(self.phrase_energy)
        self.long_energy_history.append(self.long_energy)
        self.high_energy_history.append(curr_high)

        energy_ratio = self.phrase_energy / max(0.01, self.long_energy)

        # High-frequency riser trend over recent ~30 frames (~0.7s)
        recent_high = list(self.high_energy_history)[-30:] if len(self.high_energy_history) >= 15 else []
        is_rising = False
        if len(recent_high) >= 15:
            first_half = float(np.mean(recent_high[:len(recent_high) // 2]))
            second_half = float(np.mean(recent_high[len(recent_high) // 2:]))
            is_rising = (second_half > first_half * 1.20) and (second_half > 0.025)

        # Timeline prior (when Spotify or OS media is reporting position/duration)
        in_chorus_zone = False
        in_buildup_zone = False
        if self.timeline_progress is not None and self.timeline_is_playing and self.timeline_duration > 25.0:
            p = self.timeline_progress
            in_chorus_zone = (0.28 <= p <= 0.46) or (0.64 <= p <= 0.88)
            in_buildup_zone = (0.22 <= p < 0.28) or (0.57 <= p < 0.64)

        # 1. Chorus Entry & Exit Hysteresis:
        # Requires true phrase-level energy surge, heavy sub-bass / wall-of-sound, or drop event
        # Prevents a single isolated kick in a verse from spuriously flipping to Chorus
        chorus_entry = (
            (energy_ratio > 1.20 and (curr_sub_bass > 0.06 or curr_total > 0.12))
            or (in_chorus_zone and energy_ratio > 1.08 and curr_total > 0.08)
            or (curr_total > 0.40 and curr_sub_bass > 0.12)
            or (raw_rms > 0.35 and curr_sub_bass > 0.10)
            or (is_drop and curr_total > 0.15)
        )
        chorus_exit = (energy_ratio < 0.92) or (curr_total < 0.03)

        # 2. Buildup Entry & Exit Hysteresis:
        buildup_entry = (not chorus_entry) and (
            (is_rising and curr_high > 0.02)
            or (in_buildup_zone and (is_rising or energy_ratio > 1.05))
        )

        # Update hold timers
        if self.chorus_hold_frames > 0:
            self.chorus_hold_frames -= 1
        if self.buildup_hold_frames > 0:
            self.buildup_hold_frames -= 1

        # State transition with hysteresis locking
        if chorus_entry:
            self.is_chorus = True
            self.is_buildup = False
            self.is_verse = False
            self.section_name = "CHORUS"
            self.chorus_hold_frames = 140   # Hold chorus for at least ~3.2 seconds
        elif self.is_chorus and self.chorus_hold_frames > 0:
            self.is_chorus = True
            self.is_buildup = False
            self.is_verse = False
            self.section_name = "CHORUS"
        elif buildup_entry:
            self.is_chorus = False
            self.is_buildup = True
            self.is_verse = False
            self.section_name = "BUILDUP"
            self.buildup_hold_frames = 80   # Hold buildup for at least ~1.8 seconds
        elif self.is_buildup and self.buildup_hold_frames > 0:
            self.is_chorus = False
            self.is_buildup = True
            self.is_verse = False
            self.section_name = "BUILDUP"
        else:
            self.is_chorus = False
            self.is_buildup = False
            self.is_verse = True
            self.section_name = "VERSE"

        # Continuous section energy scalar for dynamic modulation
        if self.is_chorus:
            self.section_energy = max(1.25, min(2.0, energy_ratio * 1.15))
        elif self.is_buildup:
            self.section_energy = max(1.05, min(1.4, energy_ratio * 1.05))
        else:
            self.section_energy = max(0.5, min(1.0, energy_ratio * 0.95))

        return {
            "is_kick": is_kick_beat,
            "is_808": is_808,
            "is_snare": is_snare_beat,
            "is_hihat": is_hihat_beat,
            "is_drop": is_drop,
            "beat_phase": float(self.beat_phase),
            "is_downbeat": bool(self.is_on_grid_downbeat),
            "is_backbeat": bool(self.is_on_grid_backbeat),
            "sub_bass_level": min(1.0, float(self.sub_bass_level)),
            "bass_level": min(1.0, float(self.bass_level)),
            "mid_level": min(1.0, float(self.mid_level)),
            "high_level": min(1.0, float(self.high_level)),
            "hihat_level": min(1.0, float(self.hihat_level)),
            "total_level": min(1.0, float(self.total_level)),
            "spectrum_bars": self.spectrum_bars,
            "bpm": float(self.estimated_bpm),
            "bpm_confidence": float(self.bpm_confidence),
            "overdrive": self.overdrive_mode,
            "raw_peak": float(self.raw_input_peak),
            "agc_gain": float(self.current_agc_gain),
            "preamp_gain": float(self.user_gain),
            "chroma": self.chroma_vector,
            "pitch_idx": int(self.dominant_pitch_idx),
            "secondary_pitch_idx": int(self.secondary_pitch_idx),
            "pitch_name": self.note_names[self.dominant_pitch_idx],
            "pitch_confidence": float(self.pitch_confidence),
            "is_chorus": self.is_chorus,
            "is_buildup": self.is_buildup,
            "is_verse": self.is_verse,
            "section_name": self.section_name,
            "section_energy": float(self.section_energy),
        }

    def _smooth_level(self, current, target, rise_rate, decay_rate):
        if target > current:
            return current + (target - current) * rise_rate
        else:
            return max(0.0, current - (current - target) * decay_rate)

    def _update_bpm(self, now):
        if len(self.beat_timestamps) > 0:
            last_t = self.beat_timestamps[-1]
            interval = now - last_t
            if 0.18 <= interval <= 1.50:
                self.beat_timestamps.append(now)
            elif interval > 2.0:
                self.beat_timestamps.clear()
                self.beat_timestamps.append(now)
                return
        else:
            self.beat_timestamps.append(now)

        if len(self.beat_timestamps) >= 4:
            intervals = [
                self.beat_timestamps[i] - self.beat_timestamps[i - 1]
                for i in range(1, len(self.beat_timestamps))
            ]
            median_interval = float(np.median(intervals))
            if median_interval > 0.01:
                raw_bpm = 60.0 / median_interval
                if raw_bpm < 70 and raw_bpm * 2 <= 180:
                    raw_bpm *= 2
                elif raw_bpm > 190 and raw_bpm / 2 >= 70:
                    raw_bpm /= 2

                if self.estimated_bpm == 0.0:
                    self.estimated_bpm = raw_bpm
                else:
                    self.estimated_bpm = self.estimated_bpm * 0.70 + raw_bpm * 0.30

                std_interval = float(np.std(intervals))
                self.bpm_confidence = max(0.0, min(1.0, 1.0 - (std_interval / median_interval)))
