import asyncio
import threading
import time
import queue
from datetime import datetime
from enum import Enum
from typing import Optional, AsyncGenerator, Dict, Any

from .classification.src.audio_server_rnn import stream_predict
from .localization_service import LocalizationService


class SystemState(Enum):
    MONITORING = "monitoring"
    LOCALIZING = "localizing"


class SystemManager:
    def __init__(
        self,
        model_path: str = "classification/models/rnn_model.joblib",
        device: Optional[int] = None,
        mic_label: str = "Main Mic",
        detection_threshold: float = 0.5,
        localization_cycles: int = 5,
        cycle_interval: float = 4.0,
        cooldown_seconds: float = 25.0,
    ):
        self.model_path = model_path
        self.device = device
        self.mic_label = mic_label
        self.detection_threshold = detection_threshold
        self.localization_cycles = localization_cycles
        self.cycle_interval = cycle_interval
        self.cooldown_seconds = cooldown_seconds
        
        self.state = SystemState.MONITORING
        self.stop_event = threading.Event()
        self.message_queue: queue.Queue[Dict[str, Any]] = queue.Queue()
        
        self.localization_service = LocalizationService()
        
        self._last_localization_time: float = 0
        self._manual_trigger = threading.Event()
        self._is_manual_localization = False
        
        self._latest_localization: Optional[Dict] = None
        
    def trigger_localization(self):
        self._manual_trigger.set()
        
    def _should_localize(self, prob_drone: float) -> bool:
        if self._manual_trigger.is_set():
            self._manual_trigger.clear()
            self._is_manual_localization = True
            return True
        
        if prob_drone < self.detection_threshold:
            return False
            
        now = time.time()
        if now - self._last_localization_time < self.cooldown_seconds:
            return False
        
        self._is_manual_localization = False
        return True
    
    def _run_classification(self):
        for msg in stream_predict(
            model_path=self.model_path,
            device=self.device,
            mic_label=self.mic_label,
            stop_event=self.stop_event,
        ):
            if self.stop_event.is_set():
                break
            
            event = {
                "type": "classification",
                "timestamp": msg["timestamp"],
                "prob_drone": msg["prob_drone"],
                "label": msg["label"],
            }
            self.message_queue.put(event)
            
            if self._should_localize(msg["prob_drone"]):
                self.message_queue.put({
                    "type": "localization_start",
                    "manual": self._is_manual_localization
                })
                break
    
    def _run_localization_sequence(self):
        self.state = SystemState.LOCALIZING
        self._last_localization_time = time.time()
        
        try:
            self.localization_service.ensure_microphones()
        except Exception as e:
            self.message_queue.put({
                "type": "localization_error",
                "error": f"Microphone init failed: {str(e)}"
            })
            return
        
        for cycle in range(self.localization_cycles):
            if self.stop_event.is_set():
                break
                
            cycle_start = time.time()
            
            try:
                result = self.localization_service.localize()
                self._latest_localization = result
                
                event = {
                    "type": "localization",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "cycle": cycle + 1,
                    "total_cycles": self.localization_cycles,
                    "azimuth": result["azimuth"],
                    "elevation": result["elevation"],
                    "position_x": result["position_x"],
                    "position_y": result["position_y"],
                    "distance": result["distance"],
                    "mic_distances": result["mic_distances"],
                    "tdoas": result["tdoas"],
                    "correlation_quality": result["correlation_quality"],
                }
                self.message_queue.put(event)
                
            except Exception as e:
                self.message_queue.put({
                    "type": "localization_error",
                    "cycle": cycle + 1,
                    "error": str(e)
                })
            
            elapsed = time.time() - cycle_start
            sleep_time = self.cycle_interval - elapsed
            if sleep_time > 0 and cycle < self.localization_cycles - 1:
                time.sleep(sleep_time)
        
        self.message_queue.put({
            "type": "localization_end",
            "manual": self._is_manual_localization
        })
        self._is_manual_localization = False
        self.state = SystemState.MONITORING
    
    def _main_loop(self):
        while not self.stop_event.is_set():
            self.stop_event.clear()
            
            self._run_classification()
            
            if self.stop_event.is_set():
                break
            
            self._run_localization_sequence()
    
    def start(self):
        self.stop_event.clear()
        self._thread = threading.Thread(target=self._main_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        self.stop_event.set()
        if hasattr(self, '_thread'):
            self._thread.join(timeout=5.0)
    
    async def event_stream(self) -> AsyncGenerator[Dict[str, Any], None]:
        while True:
            try:
                msg = self.message_queue.get(timeout=0.1)
                yield msg
            except queue.Empty:
                await asyncio.sleep(0.05)
                continue

