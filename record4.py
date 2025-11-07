import sounddevice as sd
from scipy.io.wavfile import write
from datetime import datetime
import numpy as np
import os
import struct
from scipy import signal
from scipy.io import wavfile

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

        # Directory of the current script
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # Create output directory if it doesn't exist
        output_dir = os.path.join(script_dir, "output")
        os.makedirs(output_dir, exist_ok=True)

        # Save with timestamp and microphone name (convert floats to int16 for compatibility)
        filename = f"{output_dir}/{mic_name}_sync.wav"
        # convert float32 [-1,1] to int16 PCM
        if data.dtype == np.float32 or data.dtype == np.float64:
            outdata = float_to_int16(data)
        else:
            outdata = data
        write(filename, SAMPLE_RATE, outdata)
        print(f"Saved: {filename} (device {device_id}, samples {len(data)})")

    print(f"Total time recorded: {end_timestamp - start_timestamp}")


def sync_and_write(infiles, outdir, prepad_ms=50, threshold=95, remove_ms=0):
    """Align multiple recordings so the clap peak appears at prepad_ms.

    Steps:
    - find global peak (max absolute sample) in each file (peak index)
    - compute desired peak index = prepad_ms in samples
    - trim or pad front of each file so its peak moves to desired index
    - optionally remove remove_ms milliseconds starting at the desired peak
    - pad ends so all outputs have same length
    """
    records = []
    sr_set = set()
    for infile in infiles:
        samples, sr = read_wav_manual(infile)
        # determine clap as the global peak (max absolute across channels)
        if samples.ndim > 1:
            abs_env = np.max(np.abs(samples), axis=1)
        else:
            abs_env = np.abs(samples)
        peak_idx = int(np.argmax(abs_env))
        records.append({'infile': infile, 'samples': samples, 'sr': sr, 'peak': peak_idx})
        sr_set.add(sr)

    if len(sr_set) != 1:
        print("Warning: input files have different sample rates. Results may be incorrect.")

    sr = records[0]['sr']
    desired_peak = int((prepad_ms / 1000.0) * sr)

    aligned = []
    for rec in records:
        samples = rec['samples']
        peak = rec['peak']
        infile = rec['infile']

        shift = peak - desired_peak
        if shift >= 0:
            # trim beginning by shift samples so peak moves to desired_peak
            out = samples[shift:]
        else:
            # pad front with zeros
            pad_len = -shift
            if samples.ndim == 1:
                pad = np.zeros((pad_len,), dtype=samples.dtype)
            else:
                pad = np.zeros((pad_len, samples.shape[1]), dtype=samples.dtype)
            out = np.concatenate([pad, samples], axis=0)

        aligned.append({'infile': infile, 'out': out})

    # Optionally remove the clap region starting at desired_peak in every file
    if remove_ms and remove_ms > 0:
        remove_samples = int((remove_ms / 1000.0) * sr)
        for a in aligned:
            out = a['out']
            event_idx = desired_peak
            remove_end = min(out.shape[0], event_idx + remove_samples)
            if out.ndim == 1:
                out = np.concatenate([out[:event_idx], out[remove_end:]], axis=0)
            else:
                out = np.concatenate([out[:event_idx, :], out[remove_end:, :]], axis=0)
            a['out'] = out

    # Make all outputs same length by padding ends to the max length
    max_len = max(a['out'].shape[0] for a in aligned)
    outputs = []
    for a in aligned:
        out = a['out']
        if out.shape[0] < max_len:
            if out.ndim == 1:
                pad_end = np.zeros((max_len - out.shape[0],), dtype=out.dtype)
            else:
                pad_end = np.zeros((max_len - out.shape[0], out.shape[1]), dtype=out.dtype)
            out = np.concatenate([out, pad_end], axis=0)

        base = os.path.basename(a['infile'])
        name, ext = os.path.splitext(base)
        outname = os.path.join(outdir, f"{name}_sync{ext}")

        if out.dtype == np.float32 or out.dtype == np.float64:
            outdata = float_to_int16(out)
        else:
            outdata = out

        wavfile.write(outname, sr, outdata)
        outputs.append((outname, out.shape[0]))
        print(f"Wrote: {outname}  (desired_peak {desired_peak})")

    return outputs

def float_to_int16(x):
    clipped = np.clip(x, -1.0, 1.0)
    return (clipped * 32767).astype(np.int16)

def read_wav_manual(filename):
    """Read WAV file similar to `test_tdoa.py` handling float32 and int16.
    Returns (samples, sample_rate). Channels preserved.
    """
    with open(filename, 'rb') as f:
        f.read(4)  # RIFF
        f.read(4)  # file size
        f.read(4)  # WAVE
        audio_format = None
        channels = 1
        sample_rate = None
        bits_per_sample = None
        data = None

        while True:
            chunk_id = f.read(4)
            if not chunk_id:
                break
            chunk_size = struct.unpack('<I', f.read(4))[0]

            if chunk_id == b'fmt ':
                fmt_data = f.read(chunk_size)
                audio_format = struct.unpack('<H', fmt_data[0:2])[0]
                channels = struct.unpack('<H', fmt_data[2:4])[0]
                sample_rate = struct.unpack('<I', fmt_data[4:8])[0]
                bits_per_sample = struct.unpack('<H', fmt_data[14:16])[0]
            elif chunk_id == b'data':
                data = f.read(chunk_size)
                break
            else:
                f.read(chunk_size)

        if data is None:
            raise RuntimeError(f"No data chunk found in {filename}")

        if audio_format == 3 and bits_per_sample == 32:
            samples = np.frombuffer(data, dtype=np.float32)
        elif audio_format == 1 and bits_per_sample == 16:
            samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            # Fallback to scipy read
            sr, s = wavfile.read(filename)
            if s.dtype == np.int16:
                s = s.astype(np.float32) / 32768.0
            return s, sr

        if channels > 1:
            samples = samples.reshape(-1, channels)

        return samples, sample_rate

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

    # Build full paths to the recorded files and sync them
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "output")
    # recorded filenames use the pattern {mic_name}_sync.wav
    infiles = [os.path.join(output_dir, f"{name}_sync.wav") for (_id, name) in device_name_pairs]

    # verify files exist (print warnings if not)
    missing = [p for p in infiles if not os.path.exists(p)]
    if missing:
        print("Warning: some recorded files are missing:")
        for m in missing:
            print("  ", m)
    else:
        sync_and_write(infiles, output_dir)


