import sounddevice as sd
from scipy.io.wavfile import write
from datetime import datetime
import numpy as np

SAMPLE_RATE = 44100


def list_microphones():
    print("Available audio devices (indices shown by library):")
    print(sd.query_devices())


def record_multiple_devices(device_name_pairs, duration_seconds):
    """
    Record simultaneously from multiple devices.

    device_name_pairs: list of tuples (device_id:int, mic_name:str)
    duration_seconds: int|float total duration in seconds
    """
    buffers_per_device = []  # list of lists, each inner list accumulates callback blocks
    streams = []

    def make_callback(buffer_list):
        def _callback(indata, frames, time, status):
            if status:
                # Non-fatal stream status (XRuns, etc.) are printed for visibility
                print(f"Stream status: {status}")
            # Append a copy to avoid referencing the same memory
            buffer_list.append(indata.copy())
        return _callback

    # Create one InputStream per device
    for (device_id, _mic_name) in device_name_pairs:
        buf = []
        buffers_per_device.append(buf)
        stream = sd.InputStream(
            device=device_id,
            channels=1,
            samplerate=SAMPLE_RATE,
            dtype='float32',
            blocksize=1024,
            callback=make_callback(buf),
        )
        streams.append(stream)

    # Start all streams as close together as possible
    start_timestamp = datetime.now()
    for s in streams:
        s.start()

    # Let them run for the specified duration
    sd.sleep(int(duration_seconds * 1000))

    # Stop and close all streams
    for s in streams:
        s.stop()
        s.close()
    end_timestamp = datetime.now()

    # Write out files for each device
    for (idx, (device_id, mic_name)) in enumerate(device_name_pairs):
        if buffers_per_device[idx]:
            data = np.concatenate(buffers_per_device[idx], axis=0)
        else:
            data = np.empty((0, 1), dtype=np.float32)

        # Ensure correct shape for mono
        if data.ndim == 1:
            data = data.reshape(-1, 1)

        filename = f"output_{end_timestamp.strftime(f'{mic_name}_%Y-%m-%d_%H-%M-%S_%f')}.wav"
        write(filename, SAMPLE_RATE, data)
        print(f"Saved: {filename} (device {device_id}, samples {len(data)})")

    print(f"Total time recorded: {end_timestamp - start_timestamp}")


if __name__ == "__main__":
    # Show devices so the user can pick indices
    list_microphones()

    # Collect 4 devices and their names
    device_name_pairs = []
    for i in range(1, 5):
        name = str(input(f"Enter a name for microphone #{i}: ").strip())
        device_id = int(input(f"Enter the device ID to use for '{name}': ").strip())
        device_name_pairs.append((device_id, name))

    # Shared duration
    duration = float(input("Enter how many seconds you want to record: ").strip())

    # Perform simultaneous recording
    record_multiple_devices(device_name_pairs, duration)
