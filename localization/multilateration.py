import numpy as np
from scipy.optimize import least_squares, minimize
from typing import Tuple, Optional, List
from config.config import SPEED_OF_SOUND, REFERENCE_MIC_INDEX


class MultilaterationCalculator:
    def __init__(self, mic_positions: np.ndarray, reference_mic: int = REFERENCE_MIC_INDEX,
                 speed_of_sound: float = SPEED_OF_SOUND,
                 search_margin_factor: float = 3.0,
                 tdoa_unit: str = 'seconds',
                 sample_rate: Optional[float] = None):
        self.mic_positions = np.array(mic_positions)
        self.reference_mic = reference_mic
        self.speed_of_sound = speed_of_sound
        self.num_mics = len(mic_positions)
        self.search_margin_factor = float(search_margin_factor)
        self.tdoa_unit = str(tdoa_unit)
        self.sample_rate = sample_rate
        self.xy_min = np.min(self.mic_positions[:, :2], axis=0)
        self.xy_max = np.max(self.mic_positions[:, :2], axis=0)
        self.array_center = np.mean(self.mic_positions[:, :2], axis=0)
        radius = np.linalg.norm(self.mic_positions[:, :2] - self.array_center, axis=1)
        self.max_array_radius = float(np.max(radius)) if radius.size else 1.0
        if not np.isfinite(self.max_array_radius) or self.max_array_radius <= 0:
            self.max_array_radius = 1.0
        
        if self.num_mics < 3:
            raise ValueError("Need at least 3 mics for 2D positioning")
    
    def _align_tdoas(self, tdoas: np.ndarray) -> np.ndarray:
        other_mics = [i for i in range(self.num_mics) if i != self.reference_mic]
        
        if len(tdoas) == self.num_mics:
            tdoas = np.asarray(tdoas, dtype=float)
            tdoas_rel = tdoas - tdoas[self.reference_mic]
            tdoas_aligned = np.array([tdoas_rel[i] for i in other_mics], dtype=float)
        elif len(tdoas) == self.num_mics - 1:
            tdoas_aligned = np.asarray(tdoas, dtype=float)
        else:
            raise ValueError(
                f"tdoas length {len(tdoas)} does not match expected N ({self.num_mics}) or N-1"
            )
        
        if self.tdoa_unit == 'samples':
            if self.sample_rate is None or self.sample_rate <= 0:
                raise ValueError("sample_rate must be provided when tdoa_unit='samples'")
            tdoas_aligned = tdoas_aligned / float(self.sample_rate)
        
        return tdoas_aligned
    
    def calculate_position_2d(self, tdoas: np.ndarray, 
                             initial_guess: np.ndarray = None,
                             doa_azimuth_deg: Optional[float] = None,
                             doa_weight: float = 1.0,
                             enforce_inside: bool = False,
                             quality_weights: Optional[List[float]] = None) -> Tuple[float, float, dict]:
        
        ref_pos = self.mic_positions[self.reference_mic]
        other_mics = [i for i in range(self.num_mics) if i != self.reference_mic]
        other_positions = self.mic_positions[other_mics]
        
        tdoas_aligned = self._align_tdoas(tdoas)
        range_differences = tdoas_aligned * self.speed_of_sound
        
        if quality_weights is not None and len(quality_weights) == len(range_differences):
            weights = np.array(quality_weights)
            weights = weights / (np.sum(weights) + 1e-10)
        else:
            weights = np.ones(len(range_differences)) / len(range_differences)
        
        doa_unit_vec = None
        if doa_azimuth_deg is not None:
            doa_rad = np.radians(doa_azimuth_deg % 360.0)
            doa_unit_vec = np.array([np.cos(doa_rad), np.sin(doa_rad)])
        
        array_center = self.array_center
        max_radius = self.max_array_radius
        
        def residuals(pos):
            x, y = pos
            errors = []
            
            ref_dist = np.sqrt((x - ref_pos[0])**2 + (y - ref_pos[1])**2)
            
            for i, other_pos in enumerate(other_positions):
                other_dist = np.sqrt((x - other_pos[0])**2 + (y - other_pos[1])**2)
                predicted_diff = other_dist - ref_dist
                measured_diff = range_differences[i]
                errors.append(np.sqrt(weights[i]) * (predicted_diff - measured_diff))
            
            if doa_unit_vec is not None:
                rel_vec = np.array([x - array_center[0], y - array_center[1]])
                rel_norm = np.linalg.norm(rel_vec)
                if rel_norm > 1e-9:
                    rel_az = np.degrees(np.arctan2(rel_vec[1], rel_vec[0]))
                    if rel_az < 0:
                        rel_az += 360
                    az_diff = self._wrap_angle_difference(rel_az, doa_azimuth_deg)
                    doa_error = np.radians(az_diff) * max_radius * float(doa_weight)
                    errors.append(doa_error)
            
            return errors
        
        xy_min = self.xy_min
        xy_max = self.xy_max
        span = float(np.max(xy_max - xy_min))
        
        if enforce_inside:
            epsilon = 1e-3
            lower_bounds = (xy_min - epsilon).astype(float)
            upper_bounds = (xy_max + epsilon).astype(float)
        else:
            margin = self.search_margin_factor * (span if span > 0 else 1.0)
            lower_bounds = (xy_min - margin).astype(float)
            upper_bounds = (xy_max + margin).astype(float)
        
        if initial_guess is not None:
            initial_guess = np.asarray(initial_guess, dtype=float)
        elif doa_unit_vec is not None:
            # Use the DOA angle to pick a good starting point along that ray,
            # but still within the allowed search bounds.
            initial_guess = self._initial_guess_from_doa_2d(
                doa_unit_vec,
                lower_bounds,
                upper_bounds,
            )
        else:
            # Fall back to a coarse grid search over the array region.
            initial_guess = self._grid_search_initial_guess_2d(
                residuals, lower_bounds, upper_bounds, step=0.5
            )
        
        result = least_squares(
            residuals,
            initial_guess,
            method='trf',
            bounds=(lower_bounds, upper_bounds),
            loss='soft_l1',
        )
        
        x, y = result.x
        if enforce_inside:
            x = float(np.clip(x, xy_min[0], xy_max[0]))
            y = float(np.clip(y, xy_min[1], xy_max[1]))
        
        info = {
            'success': result.success,
            'cost': result.cost,
            'optimality': result.optimality,
            'num_iterations': result.nfev,
            'residuals': result.fun
        }
        
        return x, y, info
    
    def _initial_guess_from_doa_2d(self, doa_unit_vec: np.ndarray,
                                   lower_bounds: np.ndarray,
                                   upper_bounds: np.ndarray) -> np.ndarray:
        center = np.array(self.array_center, dtype=float)
        t_max = np.inf
        for axis in range(2):
            component = doa_unit_vec[axis]
            if abs(component) < 1e-9:
                continue
            bound = upper_bounds[axis] if component > 0 else lower_bounds[axis]
            t = (bound - center[axis]) / component
            if t > 0:
                t_max = min(t_max, t)
        if not np.isfinite(t_max) or t_max <= 0:
            t_max = np.max(upper_bounds - lower_bounds) * 0.5
        guess = center + doa_unit_vec * (0.7 * t_max)
        return np.clip(guess, lower_bounds, upper_bounds)
    
    def _grid_search_initial_guess_2d(self, residual_func, lower_bounds, upper_bounds, step=0.5):
        x_vals = np.arange(lower_bounds[0], upper_bounds[0] + step, step)
        y_vals = np.arange(lower_bounds[1], upper_bounds[1] + step, step)
        
        if len(x_vals) == 0: 
            x_vals = np.array([np.mean([lower_bounds[0], upper_bounds[0]])])
        if len(y_vals) == 0: 
            y_vals = np.array([np.mean([lower_bounds[1], upper_bounds[1]])])

        X, Y = np.meshgrid(x_vals, y_vals)
        positions = np.vstack([X.ravel(), Y.ravel()]).T
        
        best_pos = positions[0]
        min_cost = float('inf')
        
        for pos in positions:
            res = residual_func(pos)
            cost = np.sum(np.square(res))
            if cost < min_cost:
                min_cost = cost
                best_pos = pos
                
        return best_pos

    def calculate_position_3d(self, tdoas: np.ndarray, 
                             initial_guess: np.ndarray = None,
                             quality_weights: Optional[List[float]] = None) -> Tuple[float, float, float, dict]:
        
        ref_pos = self.mic_positions[self.reference_mic]
        other_mics = [i for i in range(self.num_mics) if i != self.reference_mic]
        other_positions = self.mic_positions[other_mics]
        
        tdoas_aligned = self._align_tdoas(tdoas)
        range_differences = tdoas_aligned * self.speed_of_sound
        
        if quality_weights is not None and len(quality_weights) == len(range_differences):
            weights = np.array(quality_weights)
            weights = weights / (np.sum(weights) + 1e-10)
        else:
            weights = np.ones(len(range_differences)) / len(range_differences)
        
        def residuals(pos):
            x, y, z = pos
            errors = []
            
            ref_dist = np.sqrt((x - ref_pos[0])**2 + (y - ref_pos[1])**2 + (z - ref_pos[2])**2)
            
            for i, other_pos in enumerate(other_positions):
                other_dist = np.sqrt((x - other_pos[0])**2 + (y - other_pos[1])**2 + (z - other_pos[2])**2)
                predicted_diff = other_dist - ref_dist
                measured_diff = range_differences[i]
                errors.append(np.sqrt(weights[i]) * (predicted_diff - measured_diff))
            
            return errors
        
        if initial_guess is None:
            initial_guess = np.mean(self.mic_positions, axis=0)
            if initial_guess[2] == 0:
                initial_guess[2] = 1.0
        
        xyz_min = np.min(self.mic_positions, axis=0)
        xyz_max = np.max(self.mic_positions, axis=0)
        span_xy = float(np.max(self.mic_positions[:, :2].max(axis=0) - self.mic_positions[:, :2].min(axis=0)))
        margin3d = self.search_margin_factor * (span_xy if span_xy > 0 else 1.0)
        lower_bounds_3d = (xyz_min - margin3d).astype(float)
        upper_bounds_3d = (xyz_max + margin3d).astype(float)
        
        upper_bounds_3d[2] = max(upper_bounds_3d[2], margin3d * 2)
        
        result = least_squares(
            residuals,
            initial_guess,
            method='trf',
            bounds=(lower_bounds_3d, upper_bounds_3d),
            loss='soft_l1'
        )
        
        x, y, z = result.x
        
        info = {
            'success': result.success,
            'cost': result.cost,
            'optimality': result.optimality,
            'num_iterations': result.nfev,
            'residuals': result.fun
        }
        
        return x, y, z, info
    
    def __repr__(self):
        return f"Multilateration Calculator: {self.num_mics} mics, reference mic #{self.reference_mic}"

    @staticmethod
    def _wrap_angle_difference(angle_a_deg: float, angle_b_deg: float) -> float:
        diff = (angle_a_deg - angle_b_deg + 180.0) % 360.0 - 180.0
        return diff

