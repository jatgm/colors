"""
Audio analysis and beat detection engine.
Uses FFT spectral flux and dynamic adaptive thresholding to detect kicks,
snares, frequency energy levels, and real-time BPM estimation.
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
    KICK_COOLDOWN,
    SNARE_COOLDOWN,
)


class BeatDetector:
    def __init__(self, sample_rate=SAMPLE_RATE, chunk_size=CHUNK_SIZE):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.freq_bin_width = sample_rate / chunk_size

        # Precompute frequency bin indices
        self.bass_bins = (
            max(1, int(BASS_FREQ_RANGE[0] / self.freq_bin_width)),
            max(2, int(BASS_FREQ_RANGE[1] / self.freq_bin_width)),
        )
        self.mid_bins = (
            int(MID_FREQ_RANGE[0] / self.freq_bin_width),
            int(MID_FREQ_RANGE[1] / self.freq_bin_width),
        )
        self.high_bins = (
            int(HIGH_FREQ_RANGE[0] / self.freq_bin_width),
            min(chunk_size // 2, int(HIGH_FREQ_RANGE[1] / self.freq_bin_width)),
        )

        # Hanning window for smooth FFT without spectral leakage
        self.window = np.hanning(chunk_size)

        # Rolling history buffers for adaptive dynamic thresholding (~1 sec history)
        history_len = 45
        self.bass_flux_history = deque(maxlen=history_len)
        self.high_flux_history = deque(maxlen=history_len)
        self.bass_energy_history = deque(maxlen=history_len)

        # Previous frame energies for spectral flux (positive onset derivative)
        self.prev_bass_energy = 0.0
        self.prev_high_energy = 0.0

        # Beat detection cooldowns
        self.last_kick_time = 0.0
        self.last_snare_time = 0.0

        # Sensitivity: higher = more sensitive (detects softer beats)
        # Default 1.3
        self.user_sensitivity = 1.3

        # Peak normalized levels for visualizer meters (0.0 to 1.0)
        self.bass_level = 0.0
        self.mid_level = 0.0
        self.high_level = 0.0
        self.total_level = 0.0

        # 24-band spectrum visualizer output
        self.num_spectrum_bars = 24
        self.spectrum_bars = np.zeros(self.num_spectrum_bars, dtype=np.float32)
        self._setup_spectrum_bands()

        # BPM tracking
        self.beat_timestamps = deque(maxlen=16)
        self.estimated_bpm = 0.0
        self.bpm_confidence = 0.0

        # Noise gate floor
        self.noise_floor = 0.003

    def _setup_spectrum_bands(self):
        """Set up logarithmically spaced frequency bin groups for visualizer bars."""
        # 30 Hz to 12000 Hz in log space
        log_freqs = np.logspace(np.log10(35), np.log10(11000), self.num_spectrum_bars + 1)
        self.band_ranges = []
        for i in range(self.num_spectrum_bars):
            low_b = max(1, int(log_freqs[i] / self.freq_bin_width))
            high_b = max(low_b + 1, int(log_freqs[i + 1] / self.freq_bin_width))
            self.band_ranges.append((low_b, high_b))

    def set_sensitivity(self, val):
        """Set user sensitivity (0.5 to 2.5, default ~1.3)."""
        self.user_sensitivity = max(0.5, min(2.5, float(val)))

    def process_audio(self, audio_data):
        """
        Process an incoming audio buffer.
        audio_data: numpy array of shape (N,) or (N, channels) with float values [-1.0, 1.0].
        Returns dict with detection flags and audio levels.
        """
        now = time.time()

        # Ensure mono
        if audio_data.ndim > 1:
            mono = np.mean(audio_data, axis=1)
        else:
            mono = audio_data

        # Length check / zero pad if needed
        if len(mono) != self.chunk_size:
            if len(mono) < self.chunk_size:
                mono = np.pad(mono, (0, self.chunk_size - len(mono)))
            else:
                mono = mono[:self.chunk_size]

        # Apply Hanning window & FFT
        windowed = mono * self.window
        fft_complex = np.fft.rfft(windowed)
        fft_mag = np.abs(fft_complex) / (self.chunk_size / 2)

        # 1. Band energies (RMS of magnitudes)
        bass_slice = fft_mag[self.bass_bins[0]:self.bass_bins[1]]
        mid_slice = fft_mag[self.mid_bins[0]:self.mid_bins[1]]
        high_slice = fft_mag[self.high_bins[0]:self.high_bins[1]]

        curr_bass = np.sqrt(np.mean(bass_slice**2)) if len(bass_slice) > 0 else 0.0
        curr_mid = np.sqrt(np.mean(mid_slice**2)) if len(mid_slice) > 0 else 0.0
        curr_high = np.sqrt(np.mean(high_slice**2)) if len(high_slice) > 0 else 0.0
        curr_total = np.sqrt(np.mean(fft_mag[1:]**2))

        # 2. Spectral Flux (rising edge onset)
        bass_flux = max(0.0, curr_bass - self.prev_bass_energy)
        high_flux = max(0.0, curr_high - self.prev_high_energy)

        self.prev_bass_energy = curr_bass
        self.prev_high_energy = curr_high

        self.bass_flux_history.append(bass_flux)
        self.high_flux_history.append(high_flux)
        self.bass_energy_history.append(curr_bass)

        # 3. Dynamic Threshold for Kick (Bass Beat)
        # Higher user_sensitivity -> lower threshold multiplier
        # user_sensitivity 1.3 -> mult ~1.35; user_sensitivity 2.0 -> mult ~0.9
        thresh_mult = 1.9 / max(0.1, self.user_sensitivity)

        is_kick_beat = False
        if len(self.bass_flux_history) >= 12:
            flux_mean = float(np.mean(self.bass_flux_history))
            flux_std = float(np.std(self.bass_flux_history))
            bass_mean = float(np.mean(self.bass_energy_history))

            dynamic_thresh = flux_mean + (thresh_mult * 0.7) * flux_std

            # Check:
            # 1. Bass flux exceeds dynamic threshold
            # 2. Current bass exceeds noise floor & average bass
            # 3. Cooldown time elapsed
            if (
                bass_flux > dynamic_thresh
                and curr_bass > self.noise_floor
                and curr_bass > (bass_mean * 1.05)
                and (now - self.last_kick_time >= KICK_COOLDOWN)
            ):
                is_kick_beat = True
                self.last_kick_time = now
                self._update_bpm(now)

        # 4. Dynamic Threshold for Snare / High Onset
        is_snare_beat = False
        if len(self.high_flux_history) >= 12:
            high_mean = float(np.mean(self.high_flux_history))
            high_std = float(np.std(self.high_flux_history))
            high_thresh = high_mean + (thresh_mult * 0.8) * high_std

            if (
                high_flux > high_thresh
                and curr_high > (self.noise_floor * 0.7)
                and (now - self.last_snare_time >= SNARE_COOLDOWN)
            ):
                is_snare_beat = True
                self.last_snare_time = now

        # 5. Smooth Visualizer Meters (Fast rise, smooth decay)
        rise_rate = 0.6
        decay_rate = 0.15

        self.bass_level = self._smooth_level(self.bass_level, curr_bass * 4.0, rise_rate, decay_rate)
        self.mid_level = self._smooth_level(self.mid_level, curr_mid * 5.0, rise_rate, decay_rate)
        self.high_level = self._smooth_level(self.high_level, curr_high * 8.0, rise_rate, decay_rate)
        self.total_level = self._smooth_level(self.total_level, curr_total * 4.5, rise_rate, decay_rate)

        # 6. Update 24-band Spectrum Visualizer Bars
        for i, (b_start, b_end) in enumerate(self.band_ranges):
            segment = fft_mag[b_start:b_end]
            if len(segment) > 0:
                band_energy = float(np.sqrt(np.mean(segment**2)))
                # Frequency weighting (boost highs visually)
                weight = 3.0 + (i * 0.45)
                target = min(1.0, band_energy * weight)
            else:
                target = 0.0

            # Smooth bar motion
            if target > self.spectrum_bars[i]:
                self.spectrum_bars[i] = target
            else:
                self.spectrum_bars[i] = max(0.0, self.spectrum_bars[i] * 0.88)

        return {
            "is_kick": is_kick_beat,
            "is_snare": is_snare_beat,
            "bass_level": min(1.0, self.bass_level),
            "mid_level": min(1.0, self.mid_level),
            "high_level": min(1.0, self.high_level),
            "total_level": min(1.0, self.total_level),
            "spectrum_bars": self.spectrum_bars,
            "bpm": self.estimated_bpm,
            "bpm_confidence": self.bpm_confidence,
        }

    def _smooth_level(self, current, target, rise_rate, decay_rate):
        """Smoothly interpolate levels for visual meters."""
        if target > current:
            return current + (target - current) * rise_rate
        else:
            return max(0.0, current - (current - target) * decay_rate)

    def _update_bpm(self, now):
        """Update real-time BPM estimation from recent beat intervals."""
        if len(self.beat_timestamps) > 0:
            last_t = self.beat_timestamps[-1]
            interval = now - last_t

            # Only accept intervals corresponding to 45 BPM - 220 BPM (0.27s - 1.33s)
            if 0.27 <= interval <= 1.33:
                self.beat_timestamps.append(now)
            elif interval > 2.0:
                # Long pause, reset history
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
                # Normalize double/half time to standard 70-175 range if needed
                if raw_bpm < 70 and raw_bpm * 2 <= 175:
                    raw_bpm *= 2
                elif raw_bpm > 180 and raw_bpm / 2 >= 70:
                    raw_bpm /= 2

                # Smooth with exponential moving average
                if self.estimated_bpm == 0.0:
                    self.estimated_bpm = raw_bpm
                else:
                    self.estimated_bpm = self.estimated_bpm * 0.75 + raw_bpm * 0.25

                # Confidence based on consistency of intervals
                std_interval = float(np.std(intervals))
                self.bpm_confidence = max(0.0, min(1.0, 1.0 - (std_interval / median_interval)))
