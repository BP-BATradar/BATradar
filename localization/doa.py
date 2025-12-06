import numpy as np
from typing import Tuple, Optional, List
from config.config import SPEED_OF_SOUND, REFERENCE_MIC_INDEX


class DOACalculator:
    def __init__(self, mic_positions: np.ndarray, reference_mic: int = REFERENCE_MIC_INDEX):
        self.mic_positions = np.array(mic_positions)
        self.reference_mic = reference_mic
        self.num_mics = len(mic_positions)
        
        if self.num_mics < 3:
            raise ValueError("Need at least 3 mics to figure out direction") 
        
        self.array_center = np.mean(mic_positions[:, :2], axis=0)
        self.ref_pos = self.mic_positions[self.reference_mic]
        self.other_mics = [i for i in range(self.num_mics) if i != self.reference_mic]
        self.other_positions = self.mic_positions[self.other_mics]
        
        self.A = self.other_positions - self.ref_pos

    def calculate_direction(self, tdoas: np.ndarray) -> Tuple[np.ndarray, float, float]:
        range_differences = tdoas * SPEED_OF_SOUND

        b = range_differences
        
        propagation_vector, residuals, rank, s = np.linalg.lstsq(self.A, b, rcond=None)
        
        direction_vector = -propagation_vector

        norm = np.linalg.norm(direction_vector)
        if norm > 1e-10:
            direction_vector = direction_vector / norm
        else:
            direction_vector = np.array([0.0, 0.0, 1.0])

        azimuth, elevation = self.vector_to_angles(direction_vector)

        return direction_vector, azimuth, elevation
    
    def calculate_direction_robust(self, tdoas: np.ndarray, quality_weights: Optional[List[float]] = None) -> Tuple[np.ndarray, float, float]:
        range_differences = tdoas * SPEED_OF_SOUND
        
        if quality_weights is not None and len(quality_weights) == len(tdoas):
            weights = np.array(quality_weights)
            weights = weights / (np.sum(weights) + 1e-10)
            W = np.diag(np.sqrt(weights))
            
            A_w = W @ self.A
            b_w = W @ range_differences
            propagation_vector, _, _, _ = np.linalg.lstsq(A_w, b_w, rcond=None)
        else:
            propagation_vector, _, _, _ = np.linalg.lstsq(self.A, range_differences, rcond=None)
        
        direction_vector = -propagation_vector
        
        norm = np.linalg.norm(direction_vector)
        if norm > 1e-10:
            direction_vector = direction_vector / norm
        else:
            direction_vector = np.array([0.0, 0.0, 1.0])

        azimuth, elevation = self.vector_to_angles(direction_vector)
        return direction_vector, azimuth, elevation
    
    @staticmethod
    def vector_to_angles(direction_vector: np.ndarray) -> Tuple[float, float]:
        x, y, z = direction_vector

        azimuth = np.arctan2(y, x)
        azimuth_deg = np.degrees(azimuth)

        if azimuth_deg < 0:
            azimuth_deg += 360

        horizontal_distance = np.sqrt(x**2 + y**2)
        elevation = np.arctan2(z, horizontal_distance)
        elevation_deg = np.degrees(elevation)

        return azimuth_deg, elevation_deg

    @staticmethod
    def angles_to_vector(azimuth: float, elevation: float) -> np.ndarray:
        az_rad = np.radians(azimuth)
        el_rad = np.radians(elevation)

        x = np.cos(el_rad) * np.cos(az_rad)
        y = np.cos(el_rad) * np.sin(az_rad)
        z = np.sin(el_rad)

        return np.array([x, y, z])
    
    def __repr__(self):
        return f"DOA Calculator: {self.num_mics} mics, reference mic #{self.reference_mic}"

