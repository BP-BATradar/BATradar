import numpy as np
from typing import Dict, List, Mapping, Optional, Tuple
from scipy import signal as scipy_signal
from config.config import SAMPLE_RATE, SPEED_OF_SOUND, USE_GCC_PHAT, CORRELATION_MAX_LAG, REFERENCE_MIC_INDEX, ARRAY_SIZE, MAX_TDOA


class TDOACalculator:
    def __init__(self, sample_rate: int = SAMPLE_RATE, reference_mic: int = REFERENCE_MIC_INDEX,
                 use_gcc_phat: bool = USE_GCC_PHAT, max_lag_seconds: float = None,
                 calibration_bias_seconds: Optional[Mapping[int, float]] = None,
                 apply_bandpass: bool = False, bandpass_freq: Tuple[float, float] = (200, 4000)):
        self.sample_rate = sample_rate
        self.reference_mic = reference_mic
        self.use_gcc_phat = use_gcc_phat
        self.max_lag_seconds = max_lag_seconds
        self.calibration_bias_seconds: Dict[int, float] = (
            dict(calibration_bias_seconds) if calibration_bias_seconds is not None else {}
        )
        self.apply_bandpass = apply_bandpass
        self.bandpass_freq = bandpass_freq
        self.last_correlation_peaks = []

    def set_calibration_bias(self, bias_seconds: Mapping[int, float]) -> None:
        self.calibration_bias_seconds = dict(bias_seconds)

    def clear_calibration_bias(self) -> None:
        self.calibration_bias_seconds = {}
    
    def apply_bandpass_filter(self, sig: np.ndarray, lowcut: float = None, highcut: float = None) -> np.ndarray:
        if lowcut is None or highcut is None:
            lowcut, highcut = self.bandpass_freq
        
        nyquist = self.sample_rate / 2.0
        low = lowcut / nyquist
        high = highcut / nyquist
        
        low = max(0.01, min(low, 0.99))
        high = max(0.01, min(high, 0.99))
        
        if low >= high:
            return sig
        
        sos = scipy_signal.butter(4, [low, high], btype='band', output='sos')
        filtered = scipy_signal.sosfilt(sos, sig)
        return filtered
    
    def gcc_phat(self, sig1: np.ndarray, sig2: np.ndarray) -> Tuple[float, float]:
        sig1 = sig1.flatten()
        sig2 = sig2.flatten()
        
        if self.apply_bandpass:
            sig1 = self.apply_bandpass_filter(sig1)
            sig2 = self.apply_bandpass_filter(sig2)

        n = len(sig1) + len(sig2) - 1
        n_fft = 1 << int(np.ceil(np.log2(n)))

        fft1 = np.fft.fft(sig1, n=n_fft)
        fft2 = np.fft.fft(sig2, n=n_fft)

        cross_spectrum = fft1 * np.conj(fft2)

        if self.use_gcc_phat:
            cross_spectrum = cross_spectrum / (np.abs(cross_spectrum) + 1e-10)

        correlation = np.fft.ifft(cross_spectrum).real

        if self.max_lag_seconds is not None:
            max_lag_samples = int(self.max_lag_seconds * self.sample_rate)
        else:
            max_lag_samples = int(MAX_TDOA * self.sample_rate * 1.5)
        max_lag = min(max_lag_samples, len(correlation) // 2)

        correlation = np.fft.fftshift(correlation)
        center = len(correlation) // 2

        search_start = max(0, center - max_lag)
        search_end = min(len(correlation), center + max_lag)
        search_region = correlation[search_start:search_end]

        peak_idx = int(np.argmax(search_region))
        lag_samples = peak_idx + search_start - center
        
        peak_value = search_region[peak_idx]
        mean_value = np.mean(np.abs(search_region))
        correlation_quality = peak_value / (mean_value + 1e-10) if mean_value > 0 else 0

        if 1 <= peak_idx < (len(search_region) - 1):
            y0 = search_region[peak_idx - 1]
            y1 = search_region[peak_idx]
            y2 = search_region[peak_idx + 1]
            denom = (y0 - 2 * y1 + y2)
            if abs(denom) > 1e-12:
                delta = 0.5 * (y0 - y2) / denom
                lag_samples = lag_samples + delta

        time_delay = lag_samples / self.sample_rate

        return time_delay, correlation_quality
    
    def calculate_tdoa(
        self,
        audio_signals: np.ndarray,
        bias_override: Optional[Mapping[int, float]] = None,
    ) -> np.ndarray:

        num_mics = audio_signals.shape[1]

        if num_mics < 2:
            raise ValueError("Need at least 2 microphones")

        ref_signal = audio_signals[:, self.reference_mic]

        tdoas = []
        self.last_correlation_peaks = []

        bias_map = dict(bias_override) if bias_override is not None else self.calibration_bias_seconds

        for i in range(num_mics):
            if i == self.reference_mic:
                continue

            time_delay, quality = self.gcc_phat(audio_signals[:, i], ref_signal)
            if bias_map:
                time_delay -= bias_map.get(i, 0.0)
            tdoas.append(time_delay)
            self.last_correlation_peaks.append(quality)

        return np.array(tdoas, dtype=float)

    def tdoa_to_distance_differences(self, tdoas: np.ndarray) -> np.ndarray:
        return tdoas * SPEED_OF_SOUND
    
    def get_correlation_quality(self) -> List[float]:
        return self.last_correlation_peaks
    
    def is_correlation_reliable(self, min_quality: float = 3.0) -> bool:
        if not self.last_correlation_peaks:
            return False
        return all(q >= min_quality for q in self.last_correlation_peaks)

    def __repr__(self):
        return f"TDOA Calculator: {self.sample_rate}Hz, ref mic #{self.reference_mic}, GCC-PHAT: {self.use_gcc_phat}"

