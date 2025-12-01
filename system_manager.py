import asyncio
import threading
import time
import queue
from datetime import datetime
from enum import Enum
from typing import Optional, AsyncGenerator, Dict, Any

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from classification.src.audio_server_rnn import stream_predict
from localization_service import LocalizationService


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
        self._manual_trigger = threading.Event()  # legacy, kept for compatibility
        self._is_manual_localization = False
        self._pause_for_manual = threading.Event()
        self._pending_manual_localization = threading.Event()
        self._localization_requested = False
        self._paused_for_manual = False
        
        self._latest_localization: Optional[Dict] = None
        
    def trigger_localization(self):
        # Called at GO (after countdown) to start a one-shot manual localization
        self._pending_manual_localization.set()

    def pause_for_manual(self):
        # Called on button click to stop the classification loop as soon as possible
        self._pause_for_manual.set()
        
    
    def _run_classification(self):
        for msg in stream_predict(
            model_path=self.model_path,
            device=self.device,
            mic_label=self.mic_label,
            stop_event=self.stop_event,
        ):
            if self.stop_event.is_set():
                break
            
            # Pause requested for manual localization: stop classification but do NOT
            # start localization yet. We wait for the GO signal.
            if self._pause_for_manual.is_set():
                self._pause_for_manual.clear()
                self._paused_for_manual = True
                return
            
            event = {
                "type": "classification",
                "timestamp": msg["timestamp"],
                "prob_drone": msg["prob_drone"],
                "label": msg["label"],
            }
            self.message_queue.put(event)
            
            if msg["prob_drone"] >= self.detection_threshold:
                now = time.time()
                if now - self._last_localization_time >= self.cooldown_seconds:
                    self._is_manual_localization = False
                    self._localization_requested = True
                    self.message_queue.put({
                        "type": "localization_start",
                        "manual": False
                    })
                    break
    
    def _run_localization_sequence(self, one_shot: bool = False):
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
        
        cycles = 1 if one_shot else self.localization_cycles
        
        for cycle in range(cycles):
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
            # Run classification only if we are not in a manual pause state
            if not self._paused_for_manual:
                try:
                    self._run_classification()
                except Exception as e:
                    print(f"Classification error: {e}")
                    self.message_queue.put({
                        "type": "classification",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "prob_drone": 0.0,
                        "label": "unknown",
                    })
                    time.sleep(2.0)
                    continue
            
            if self.stop_event.is_set():
                break

            # Manual one-shot localization requested (GO pressed)
            if self._pending_manual_localization.is_set():
                self._pending_manual_localization.clear()
                self._is_manual_localization = True
                self.message_queue.put({
                    "type": "localization_start",
                    "manual": True
                })
                try:
                    self._run_localization_sequence(one_shot=True)
                except Exception as e:
                    print(f"Localization sequence error (manual): {e}")
                    self.message_queue.put({
                        "type": "localization_error",
                        "error": str(e)
                    })
                    self.message_queue.put({
                        "type": "localization_end",
                        "manual": True
                    })
                finally:
                    # After manual localization, resume normal monitoring
                    self._paused_for_manual = False
                    self._is_manual_localization = False
                    self.state = SystemState.MONITORING
                continue

            # Automatic localization requested from classification
            if self._localization_requested:
                self._localization_requested = False
                self._is_manual_localization = False
                try:
                    self._run_localization_sequence(one_shot=False)
                except Exception as e:
                    print(f"Localization sequence error (auto): {e}")
                    self.message_queue.put({
                        "type": "localization_error",
                        "error": str(e)
                    })
                    self.message_queue.put({
                        "type": "localization_end",
                        "manual": False
                    })
                    self._is_manual_localization = False
                    self.state = SystemState.MONITORING
                continue

            # No localization requested; if paused for manual, just wait
            if self._paused_for_manual:
                time.sleep(0.1)
                continue
    
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
                msg = self.message_queue.get_nowait()
                yield msg
            except queue.Empty:
                await asyncio.sleep(0.1)
                continue

