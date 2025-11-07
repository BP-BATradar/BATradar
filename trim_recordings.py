#!/usr/bin/env python3
"""
Trim WAV recordings so they all start at a loud event (e.g. a clap).

Usage:
    python3 trim_recordings.py in1.wav in2.wav ...

Outputs trimmed files next to input files with suffix `_trim.wav`, or into
an output directory with `-o/--outdir`.

Options:
    --prepad-ms N      Include N ms of audio before the detected onset (default 50 ms)
    --remove-ms N      Remove N ms immediately after the detected onset (default 400 ms)
    --sync-clap         Synchronize multiple recordings by the detected clap (output suffix `_sync.wav`)
    --pad-to-same      Pad/truncate outputs so all have the same length
    -o, --outdir DIR   Output directory (default: same folder as inputs)
    -t, --threshold P  Percentile used to set energy threshold (default 95)

This script preserves sample rate and channel count. It requires numpy and
scipy (for resample_poly when needed and wav I/O).
"""
import argparse
import os
import sys
import numpy as np
import struct
from scipy import signal
from scipy.io import wavfile


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


def find_sound_onset(audio, sample_rate, threshold_percentile=95):
    """Detect onset index (sample) of the main loud event in audio.

    Works on mono or multi-channel arrays. If multi-channel, uses the first
    channel for detection but returns an index valid for all channels.
    """
    if audio.ndim > 1:
        sig = audio[:, 0]
    else:
        sig = audio

    window_size = int(0.01 * sample_rate)  # 10 ms
    hop_size = max(1, window_size // 2)

    # compute energy in sliding windows
    energy = []
    for i in range(0, len(sig) - window_size, hop_size):
        w = sig[i:i+window_size]
        energy.append(np.sum(w**2))

    energy = np.array(energy)
    if energy.size == 0:
        return 0

    threshold = np.percentile(energy, threshold_percentile)
    onset_windows = np.where(energy > threshold)[0]
    if onset_windows.size == 0:
        return 0

    onset_sample = onset_windows[0] * hop_size

    # refine onset by searching backward for a smaller threshold
    search_start = max(0, onset_sample - window_size)
    search_region = sig[search_start:onset_sample + window_size]
    if search_region.size == 0:
        return onset_sample

    threshold_fine = np.max(np.abs(search_region)) * 0.05
    fine = np.where(np.abs(search_region) > threshold_fine)[0]
    if fine.size > 0:
        onset_sample = search_start + fine[0]

    return int(onset_sample)


def float_to_int16(x):
    clipped = np.clip(x, -1.0, 1.0)
    return (clipped * 32767).astype(np.int16)


def trim_and_write(infile, outdir, prepad_ms=50, threshold=95, remove_ms=400):
    samples, sr = read_wav_manual(infile)
    onset = find_sound_onset(samples, sr, threshold_percentile=threshold)

    prepad_samples = int((prepad_ms / 1000.0) * sr)
    start = max(0, onset - prepad_samples)

    trimmed = samples[start:]

    # remove N ms immediately after the detected onset (to remove clap)
    if remove_ms and remove_ms > 0:
        remove_samples = int((remove_ms / 1000.0) * sr)
        event_idx = onset - start
        # clamp indices
        if event_idx < 0:
            event_idx = 0
        remove_end = min(trimmed.shape[0], event_idx + remove_samples)
        # concatenate before event and after removed region
        if trimmed.ndim == 1:
            trimmed = np.concatenate([trimmed[:event_idx], trimmed[remove_end:]], axis=0)
        else:
            trimmed = np.concatenate([trimmed[:event_idx, :], trimmed[remove_end:, :]], axis=0)

    base = os.path.basename(infile)
    name, ext = os.path.splitext(base)
    outname = os.path.join(outdir, f"{name}_trim{ext}")

    # If float array, convert to int16 for wavfile.write
    if trimmed.dtype == np.float32 or trimmed.dtype == np.float64:
        outdata = float_to_int16(trimmed)
    else:
        outdata = trimmed

    wavfile.write(outname, sr, outdata)
    return outname, onset, sr, trimmed.shape[0]


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


def main(argv=None):
    parser = argparse.ArgumentParser(description="Trim recordings so they start at a loud event (clap).")
    parser.add_argument('inputs', nargs='+', help='Input WAV files')
    parser.add_argument('-o', '--outdir', default=None, help='Output directory (default: same folder as input)')
    parser.add_argument('--prepad-ms', type=float, default=50.0, help='Milliseconds to keep before detected onset')
    parser.add_argument('--sync-clap', action='store_true', help='Synchronize inputs by detected clap (write _sync.wav outputs)')
    parser.add_argument('--pad-to-same', action='store_true', help='Pad/truncate outputs so all have same length')
    parser.add_argument('-t', '--threshold', type=float, default=95.0, help='Percentile for energy threshold')
    parser.add_argument('--remove-ms', type=float, default=400.0, help='Milliseconds to remove after detected onset when trimming (default 400)')

    args = parser.parse_args(argv)

    results = []
    # If sync requested, run multi-file synchronization and exit
    if args.sync_clap:
        outdir = args.outdir if args.outdir else os.path.dirname(os.path.abspath(args.inputs[0]))
        os.makedirs(outdir, exist_ok=True)
        sync_outputs = sync_and_write(args.inputs, outdir, prepad_ms=args.prepad_ms, threshold=args.threshold, remove_ms=args.remove_ms)
        sys.exit(0)

    for infile in args.inputs:
        if not os.path.isfile(infile):
            print(f"Warning: file not found: {infile}")
            continue

        outdir = args.outdir if args.outdir else os.path.dirname(os.path.abspath(infile))
        os.makedirs(outdir, exist_ok=True)

        outname, onset, sr, length = trim_and_write(infile, outdir, prepad_ms=args.prepad_ms, threshold=args.threshold, remove_ms=args.remove_ms)
        print(f"Wrote: {outname}  (onset sample {onset}, sr={sr}, frames_out={length})")
        results.append((outname, sr, length))

    if args.pad_to_same and results:
        # find max length and pad/truncate files to same number of samples
        max_len = max(r[2] for r in results)
        for outname, sr, length in results:
            data = wavfile.read(outname)[1]
            if data.shape[0] < max_len:
                # pad with zeros
                if data.ndim == 1:
                    pad = np.zeros((max_len - data.shape[0],), dtype=data.dtype)
                else:
                    pad = np.zeros((max_len - data.shape[0], data.shape[1]), dtype=data.dtype)
                new = np.concatenate([data, pad], axis=0)
                wavfile.write(outname, sr, new)
            elif data.shape[0] > max_len:
                new = data[:max_len]
                wavfile.write(outname, sr, new)
        print(f"Padded/truncated all outputs to {max_len} frames.")


if __name__ == '__main__':
    main()
