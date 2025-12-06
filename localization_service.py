import numpy as np
from typing import Dict, List, Optional, Tuple

from config.config import (
    MIC_POSITIONS,
    MIC_ORDER,
    SAMPLE_RATE,
    CHUNK_DURATION,
    REFERENCE_MIC_INDEX,
)
from recording.multi_device_recorder import MultiDeviceRecorder
from recording.record4_config import select_and_map_microphones, ensure_mic_configuration
from localization.tdoa import TDOACalculator
from localization.doa import DOACalculator
from localization.multilateration import MultilaterationCalculator


def _find_sound_onset(audio: np.ndarray, sample_rate: int, threshold_percentile: float = 95.0) -> int:
    """
    Onset detection logic equivalent to TDOA/test/test_multilat.py::find_sound_onset.
    """
    window_size = int(0.01 * sample_rate)  # 10 ms
    if window_size <= 0:
        return 0
    hop_size = max(1, window_size // 2)

    if audio.ndim > 1:
        audio = audio.reshape(-1)

    if audio.size < window_size:
        return 0

    energy = []
    for i in range(0, audio.size - window_size, hop_size):
        window = audio[i : i + window_size]
        energy.append(np.sum(window**2))

    if not energy:
        return 0

    energy = np.asarray(energy, dtype=float)
    threshold = np.percentile(energy, threshold_percentile)
    onset_windows = np.where(energy > threshold)[0]

    if onset_windows.size == 0:
        return 0

    onset_sample = int(onset_windows[0] * hop_size)

    search_start = max(0, onset_sample - window_size)
    search_end = min(audio.size, onset_sample + window_size)
    search_region = audio[search_start:search_end]

    if search_region.size == 0:
        return onset_sample

    threshold_fine = float(np.max(np.abs(search_region)) * 0.05)
    fine_onset = np.where(np.abs(search_region) > threshold_fine)[0]

    if fine_onset.size > 0:
        onset_sample = int(search_start + fine_onset[0])

    return onset_sample


def _calculate_tdoas_from_onsets(audio_block: np.ndarray, sample_rate: int, reference_idx: int = 0) -> np.ndarray:
    """
    Equivalent to TDOA/test/test_multilat.py::calculate_tdoas_from_onsets,
    adapted for a (num_samples, num_mics) audio_block.
    """
    num_mics = audio_block.shape[1]
    onsets: List[int] = []

    for ch in range(num_mics):
        sig = audio_block[:, ch]
        onset = _find_sound_onset(sig, sample_rate)
        onsets.append(onset)

    ref_onset = onsets[reference_idx]
    tdoas_samples: List[int] = []
    for i, onset in enumerate(onsets):
        if i == reference_idx:
            continue
        tdoa = onset - ref_onset
        tdoas_samples.append(tdoa)

    tdoas_time = np.asarray(tdoas_samples, dtype=float) / float(sample_rate)
    return tdoas_time


class LocalizationService:
    def __init__(self, sample_rate: int = SAMPLE_RATE, chunk_duration: float = CHUNK_DURATION):
        self.sample_rate = sample_rate
        self.chunk_duration = chunk_duration
        
        # Build microphone position array in the configured processing order
        self.mic_positions_array = np.array(
            [MIC_POSITIONS[name] for name in MIC_ORDER],
            dtype=float,
        )
        
        # Use the simple GCC-PHAT TDOA calculator (same class used in test_multilat.py)
        self.tdoa_calc = TDOACalculator(
            sample_rate=self.sample_rate,
            reference_mic=REFERENCE_MIC_INDEX,
            apply_bandpass=False,
        )

        self.doa_calc = DOACalculator(
            mic_positions=self.mic_positions_array,
            reference_mic=REFERENCE_MIC_INDEX,
        )
        self.multilat_calc = MultilaterationCalculator(
            mic_positions=self.mic_positions_array,
            reference_mic=REFERENCE_MIC_INDEX,
        )
        
        self.mic_indices: Optional[List[int]] = None
        self.mic_names: Optional[List[str]] = None
        self.recorder: Optional[MultiDeviceRecorder] = None
        
    def initialize_microphones(self) -> Tuple[List[int], List[str]]:
        self.mic_indices, self.mic_names = select_and_map_microphones()
        return self.mic_indices, self.mic_names
    
    def ensure_microphones(self) -> bool:
        if self.mic_indices is None:
            self.initialize_microphones()
            return True
        
        new_indices, new_names, changed = ensure_mic_configuration(
            self.mic_indices, self.mic_names
        )
        if changed:
            self.mic_indices = new_indices
            self.mic_names = new_names
        return changed
    
    def record_chunk(self) -> np.ndarray:
        if self.mic_indices is None:
            self.initialize_microphones()
        
        recorder = MultiDeviceRecorder(
            mic_indices=self.mic_indices,
            sample_rate=self.sample_rate,
            chunk_duration=self.chunk_duration,
            blocksize=256,
        )
        recorder.start()
        try:
            block = recorder.read_chunk(timeout=5.0)
        finally:
            recorder.stop()
        
        return block
    
    def compute_localization(self, audio_block: np.ndarray) -> Dict:
        # Use onset-based TDOA, matching the default behavior of TDOA/test/test_multilat.py
        tdoas = _calculate_tdoas_from_onsets(audio_block, self.sample_rate, reference_idx=REFERENCE_MIC_INDEX)
        
        direction_vector, azimuth, elevation = self.doa_calc.calculate_direction(tdoas)
        
        # Match TDOA/test/test_multilat.py call signature: no quality_weights, default doa_weight
        x, y, info = self.multilat_calc.calculate_position_2d(
            tdoas,
            doa_azimuth_deg=azimuth,
            enforce_inside=True,
        )
        
        mic_distances = self._compute_mic_distances(x, y)
        
        array_center = np.mean(self.mic_positions_array[:, :2], axis=0)
        distance_from_center = np.sqrt((x - array_center[0])**2 + (y - array_center[1])**2)
        
        return {
            "tdoas": [float(t) for t in tdoas],
            "correlation_quality": [],
            "azimuth": float(azimuth),
            "elevation": float(elevation),
            "position_x": float(x),
            "position_y": float(y),
            "distance": float(distance_from_center),
            "mic_distances": mic_distances,
            "optimization_info": {
                "success": bool(info["success"]),
                "cost": float(info["cost"]),
            }
        }
    
    def _compute_mic_distances(self, x: float, y: float) -> Dict[str, float]:
        distances = {}
        for i, name in enumerate(MIC_ORDER):
            mic_pos = self.mic_positions_array[i]
            dist = np.sqrt((x - mic_pos[0])**2 + (y - mic_pos[1])**2)
            distances[name] = float(dist)
        return distances
    
    def localize(self) -> Dict:
        audio_block = self.record_chunk()
        return self.compute_localization(audio_block)

