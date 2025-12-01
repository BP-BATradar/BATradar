import numpy as np
from typing import Dict, List, Optional, Tuple

from config.config import MIC_POSITIONS, MIC_ORDER, SAMPLE_RATE, CHUNK_DURATION
from recording.multi_device_recorder import MultiDeviceRecorder
from recording.record4_config import select_and_map_microphones, ensure_mic_configuration
from localization.tdoa import TDOACalculator
from localization.doa import DOACalculator
from localization.multilateration import MultilaterationCalculator


class LocalizationService:
    def __init__(self, sample_rate: int = SAMPLE_RATE, chunk_duration: float = CHUNK_DURATION):
        self.sample_rate = sample_rate
        self.chunk_duration = chunk_duration
        
        self.mic_positions_array = np.array([MIC_POSITIONS[name] for name in MIC_ORDER])
        
        self.tdoa_calc = TDOACalculator(sample_rate=sample_rate)
        self.doa_calc = DOACalculator(mic_positions=self.mic_positions_array)
        self.multilat_calc = MultilaterationCalculator(mic_positions=self.mic_positions_array)
        
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
        tdoas = self.tdoa_calc.calculate_tdoa(audio_block)
        quality = self.tdoa_calc.get_correlation_quality()
        
        direction_vector, azimuth, elevation = self.doa_calc.calculate_direction(tdoas)
        
        x, y, info = self.multilat_calc.calculate_position_2d(
            tdoas, 
            doa_azimuth_deg=azimuth,
            doa_weight=2.0,
            quality_weights=quality,
            enforce_inside=True
        )
        
        mic_distances = self._compute_mic_distances(x, y)
        
        array_center = np.mean(self.mic_positions_array[:, :2], axis=0)
        distance_from_center = np.sqrt((x - array_center[0])**2 + (y - array_center[1])**2)
        
        return {
            "tdoas": [float(t) for t in tdoas],
            "correlation_quality": [float(q) for q in quality],
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

