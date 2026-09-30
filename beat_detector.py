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
        self.bass_flux_history = deque(maxlen=history_len)
        self.high_flux_history = deque(maxlen=history_len)
        self.hihat_flux_history = deque(maxlen=history_len)
        self.total_energy_history = deque(maxlen=history_len)
        self.bass_energy_history = deque(maxlen=history_len)

        # Previous frame energies for spectral flux
        self.prev_bass_energy = 0.0
        self.prev_high_energy = 0.0
        self.prev_hihat_energy = 0.0
        self.prev_total_energy = 0.0

        # Beat detection cooldowns
        self.last_kick_time = 0.0
        self.last_snare_time = 0.0
        self.last_hihat_time = 0.0

        # Overdrive / Crazy Mode toggle
        self.overdrive_mode = True

        # Sensitivity: higher = more sensitive
        self.user_sensitivity = 1.4

        # Peak normalized levels for visualizer meters
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

        # 1. Measure raw input peak
        raw_peak = float(np.max(np.abs(mono)))
        self.raw_input_peak = raw_peak

        # 2. Dynamic Automatic Gain Control (AGC)
        # Fast attack, slow release tracking
        if raw_peak > self.rolling_peak:
            self.rolling_peak = raw_peak * 0.85 + self.rolling_peak * 0.15
        else:
            self.rolling_peak = max(0.003, self.rolling_peak * 0.992)

        # Calculate automatic scaling factor (capped at 60x max gain)
        # Target peak is ~0.80 full scale
        auto_gain = min(60.0, 0.80 / max(0.003, self.rolling_peak))
        total_gain = auto_gain * self.user_gain
        self.current_agc_gain = total_gain

        # Normalize audio chunk using AGC gain
        norm_audio = np.clip(mono * total_gain, -1.2, 1.2)

        # 3. FFT Analysis on Normalized Audio
        windowed = norm_audio * self.window
        fft_complex = np.fft.rfft(windowed)
        fft_mag = np.abs(fft_complex) / (self.chunk_size / 2)

        # 4. Band Energies
        bass_slice = fft_mag[self.bass_bins[0]:self.bass_bins[1]]
        mid_slice = fft_mag[self.mid_bins[0]:self.mid_bins[1]]
        high_slice = fft_mag[self.high_bins[0]:self.high_bins[1]]
        hihat_slice = fft_mag[self.hihat_bins[0]:self.hihat_bins[1]]

        curr_bass = float(np.sqrt(np.mean(bass_slice**2))) if len(bass_slice) > 0 else 0.0
        curr_mid = float(np.sqrt(np.mean(mid_slice**2))) if len(mid_slice) > 0 else 0.0
        curr_high = float(np.sqrt(np.mean(high_slice**2))) if len(high_slice) > 0 else 0.0
        curr_hihat = float(np.sqrt(np.mean(hihat_slice**2))) if len(hihat_slice) > 0 else 0.0
        curr_total = float(np.sqrt(np.mean(fft_mag[1:]**2)))

        # 5. Spectral Flux (Attack / Rising Edge)
        bass_flux = max(0.0, curr_bass - self.prev_bass_energy)
        high_flux = max(0.0, curr_high - self.prev_high_energy)
        hihat_flux = max(0.0, curr_hihat - self.prev_hihat_energy)
        total_flux = max(0.0, curr_total - self.prev_total_energy)

        self.prev_bass_energy = curr_bass
        self.prev_high_energy = curr_high
        self.prev_hihat_energy = curr_hihat
        self.prev_total_energy = curr_total

        self.bass_flux_history.append(bass_flux)
        self.high_flux_history.append(high_flux)
        self.hihat_flux_history.append(hihat_flux)
        self.total_energy_history.append(curr_total)
        self.bass_energy_history.append(curr_bass)

        # Cooldowns and Threshold multipliers based on Overdrive
        if self.overdrive_mode:
            k_cd = OVERDRIVE_KICK_COOLDOWN
            s_cd = OVERDRIVE_SNARE_COOLDOWN
            h_cd = OVERDRIVE_HIHAT_COOLDOWN
            base_mult = 1.05 / max(0.1, self.user_sensitivity)
        else:
            k_cd = KICK_COOLDOWN
            s_cd = SNARE_COOLDOWN
            h_cd = HIHAT_COOLDOWN
            base_mult = 1.55 / max(0.1, self.user_sensitivity)

        # 6. Dynamic Threshold for Kick (Bass)
        is_kick_beat = False
        if len(self.bass_flux_history) >= 8:
            flux_mean = float(np.mean(self.bass_flux_history))
            flux_std = float(np.std(self.bass_flux_history))
            bass_mean = float(np.mean(self.bass_energy_history))

            dynamic_thresh = flux_mean + (base_mult * 0.55) * flux_std
            # In normalized AGC space, floor is clean
            gate = 0.015 if self.overdrive_mode else 0.025

            if (
                bass_flux > dynamic_thresh
                and curr_bass > gate
                and curr_bass > (bass_mean * (1.02 if self.overdrive_mode else 1.06))
                and (now - self.last_kick_time >= k_cd)
            ):
                is_kick_beat = True
                self.last_kick_time = now
                self._update_bpm(now)

        # 7. Dynamic Threshold for Snare
        is_snare_beat = False
        if len(self.high_flux_history) >= 8:
            high_mean = float(np.mean(self.high_flux_history))
            high_std = float(np.std(self.high_flux_history))
            high_thresh = high_mean + (base_mult * 0.65) * high_std

            if (
                high_flux > high_thresh
                and curr_high > 0.012
                and (now - self.last_snare_time >= s_cd)
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
        target_bass = min(1.0, float((curr_bass * 2.6) ** 0.55))
        target_mid = min(1.0, float((curr_mid * 3.2) ** 0.60))
        target_high = min(1.0, float((curr_high * 4.0) ** 0.65))
        target_hihat = min(1.0, float((curr_hihat * 5.0) ** 0.70))
        target_total = min(1.0, float((curr_total * 2.8) ** 0.60))

        rise_rate = 0.80 if self.overdrive_mode else 0.70
        decay_rate = 0.18 if self.overdrive_mode else 0.14

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

        return {
            "is_kick": is_kick_beat,
            "is_snare": is_snare_beat,
            "is_hihat": is_hihat_beat,
            "is_drop": is_drop,
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
            if 0.22 <= interval <= 1.35:
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
