from typing import Tuple, List

import numpy as np
import sounddevice as sd

from config.config import SAMPLE_RATE, CHUNK_DURATION
from recording.multi_device_recorder import MultiDeviceRecorder


def list_microphones():
    print("=" * 70)
    print("Available microphones:")
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            print(f"[{i}] {device['name']} - Channels: {device['max_input_channels']}")
    print("=" * 70)


def select_microphones() -> Tuple[List[int], List[str]]:
    list_microphones()

    mic_indices = []
    mic_names = []

    print("\nPlease select 4 microphones by entering their device numbers:")
    mic_positions = ['bottom_left', 'bottom_right', 'top_left', 'top_right']

    for position in mic_positions:
        while True:
            try:
                idx = int(input(f"Enter device number for {position} microphone: "))
                device = sd.query_devices(idx)
                if device['max_input_channels'] == 0:
                    print(f"Error: Device {idx} can't record audio. Please choose another.")
                    continue
                mic_indices.append(idx)
                mic_names.append(device['name'])
                break
            except (ValueError, sd.PortAudioError):
                print("Invalid device number. Please try again.")

    return mic_indices, mic_names


def record_synchronized(mic_indices, duration=CHUNK_DURATION, sample_rate=SAMPLE_RATE, verbose=True):
    if len(mic_indices) != 4:
        raise ValueError("Exactly 4 microphones are required")

    num_samples = int(duration * sample_rate)

    if verbose:
        print(f"\n" + "="*70)
        print(f"MULTI-DEVICE RECORDING (no shared clock)")
        print(f"="*70)
        print(f"Duration: {duration} seconds")
        print(f"Sample rate: {sample_rate} Hz")
        print(f"Target samples per mic: {num_samples}")
        print(f"Recording from {len(mic_indices)} separate devices...")

    recorder = MultiDeviceRecorder(
        mic_indices=mic_indices,
        sample_rate=sample_rate,
        chunk_duration=duration,
        blocksize=256,
    )
    recorder.start()
    try:
        block = recorder.read_chunk(timeout=5.0)
    finally:
        recorder.stop()

    if block.shape[0] > num_samples:
        block = block[:num_samples, :]
    elif block.shape[0] < num_samples:
        pad = np.zeros((num_samples - block.shape[0], block.shape[1]), dtype=block.dtype)
        block = np.vstack([block, pad])

    aligned_recordings = [block[:, i].copy() for i in range(4)]

    return aligned_recordings

