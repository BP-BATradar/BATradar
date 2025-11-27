import threading
import time
from collections import deque
from typing import List, Optional

import numpy as np
import sounddevice as sd

from ..config.config import SAMPLE_RATE, CHUNK_DURATION


class MultiDeviceRecorder:
    def __init__(
        self,
        mic_indices: List[int],
        sample_rate: int = SAMPLE_RATE, 
        chunk_duration: float = CHUNK_DURATION, 
        blocksize: int = 256, 
        max_buffer_chunks: int = 10, 
    ) -> None:
        if len(mic_indices) != 4:
            raise ValueError("Exactly 4 microphones are required") 

        self.mic_indices = mic_indices
        self.sample_rate = int(sample_rate)
        self.chunk_duration = float(chunk_duration)
        self.chunk_size = int(round(self.sample_rate * self.chunk_duration))
        self.blocksize = int(blocksize)
        self.max_buffer_samples = max(1, max_buffer_chunks) * self.chunk_size

        self._buffers: List[deque[np.ndarray]] = [deque() for _ in range(4)]
        self._buffer_lengths: List[int] = [0, 0, 0, 0]

        self._lock = threading.Lock()
        self._data_available = threading.Condition(self._lock)
        self._streams: List[sd.InputStream] = []
        self._running = False
        self._stream_start_times: List[float] = []
        self._warmup_samples = int(0.5 * sample_rate)

    def start(self) -> None:
        if self._running:
            return
        
        self._streams = []
        self._stream_start_times = []
        self._running = True
        
        device_map = {}
        for logical_idx, device_idx in enumerate(self.mic_indices):
            if device_idx not in device_map:
                device_map[device_idx] = []
            device_map[device_idx].append(logical_idx)
            
        created_streams = []
        for device_idx, logical_indices in device_map.items():
            channels = len(logical_indices)
            cb = self._make_multichannel_callback(logical_indices)
            
            try:
                stream = sd.InputStream(
                    device=device_idx,
                    channels=channels,
                    samplerate=self.sample_rate,
                    callback=cb,
                    blocksize=self.blocksize,
                    dtype="float32",
                )
                created_streams.append(stream)
            except Exception as e:
                print(f"Error creating stream for device {device_idx}: {e}")
                self._running = False
                self.stop()
                raise
        
        start_time = time.time()
        for stream in created_streams:
            stream.start()
            self._stream_start_times.append(time.time())
            self._streams.append(stream)
        
        time.sleep(0.05)

    def _make_multichannel_callback(self, logical_indices: List[int]):
        def _cb(indata, frames, time_info, status):
            if status:
                pass
            
            with self._data_available:
                for channel_idx, logical_idx in enumerate(logical_indices):
                    if indata.ndim == 2:
                        chunk = indata[:, channel_idx]
                    else:
                        chunk = indata
                        
                    chunk = np.asarray(chunk, dtype=np.float32).copy().reshape(-1)
                    
                    self._buffers[logical_idx].append(chunk)
                    self._buffer_lengths[logical_idx] += chunk.size
                    
                    while self._buffer_lengths[logical_idx] > self.max_buffer_samples:
                        dropped = self._buffers[logical_idx].popleft()
                        self._buffer_lengths[logical_idx] -= dropped.size
                
                self._data_available.notify_all()
        return _cb

    def stop(self) -> None:
        if not self._running: 
            return
        for s in self._streams: 
            try:
                s.stop()
                s.close()
            except Exception:
                pass
        self._streams = []
        self._running = False

    def read_chunk(self, timeout: Optional[float] = None) -> np.ndarray:
        if not self._running:
            raise RuntimeError("Recorder is not running. Call start() first.")
        
        required_samples = self.chunk_size + self._warmup_samples
        
        with self._data_available:
            if not self._running:
                raise RuntimeError("Recorder is not running. Call start() first.")

            self._wait_for_min_samples_locked(required_samples, timeout)

            aligned = []
            for ch in range(4):
                data = self._popleft_samples_locked(ch, required_samples)
                if data.ndim > 1:
                    data = data.reshape(-1)
                
                aligned.append(data[self._warmup_samples:])

        block = np.column_stack(aligned)
        return block

    def _make_callback(self, ch_idx: int):
    
        def _cb(indata, frames, time_info, status):
            if status:
                pass
            with self._data_available:
                chunk = np.asarray(indata, dtype=np.float32).copy().reshape(-1)
                self._buffers[ch_idx].append(chunk)
                self._buffer_lengths[ch_idx] += chunk.size
                while self._buffer_lengths[ch_idx] > self.max_buffer_samples:
                    dropped = self._buffers[ch_idx].popleft()
                    self._buffer_lengths[ch_idx] -= dropped.size
                self._data_available.notify_all()
        return _cb

    def _wait_for_min_samples_locked(self, min_needed: int, timeout: Optional[float]) -> None:
        if min(self._buffer_lengths) >= min_needed:
            return
        remaining = None if timeout is None else timeout
        while min(self._buffer_lengths) < min_needed:
            if not self._data_available.wait(timeout=remaining):
                raise TimeoutError("Timed out waiting for audio data")

    def _popleft_samples_locked(self, ch: int, n: int) -> np.ndarray:
        out = np.empty(n, dtype=np.float32)
        write_idx = 0
        while write_idx < n:
            if not self._buffers[ch]:
                remaining = n - write_idx
                out[write_idx:] = 0.0
                self._buffer_lengths[ch] -= 0
                return out
            arr = self._buffers[ch][0]
            take = min(arr.size, n - write_idx)
            out[write_idx : write_idx + take] = arr[:take]
            if take == arr.size:
                self._buffers[ch].popleft()
            else:
                self._buffers[ch][0] = arr[take:]
            write_idx += take
            self._buffer_lengths[ch] -= take
        return out

