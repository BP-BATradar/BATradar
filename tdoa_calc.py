from core.microphone import Microphone
from core.tdoaPair import TdoaPair
from localization.gcc_phat import gcc_phat
import numpy as np
from typing import List


def get_all_tdoa_of_chunk_index_by_gcc_phat(
    mic1: Microphone,
    mic2: Microphone,
    mic3: Microphone,
    mic4: Microphone,
    chunk_index: int = 0,
    debug: bool = False,
) -> List[TdoaPair]:
    """
    Compute pairwise TDoAs between mic1 and the other three microphones using GCC-PHAT.

    Note: this function assumes all microphones have audio objects set and share the same
    sample rate. The GCC-PHAT call must receive the correct `fs` (sample rate) parameter
    so the returned tau is in seconds.
    """

    audio1 = mic1.get_audio().get_audio_signal(index=chunk_index)
    signal_mics = [mic2, mic3, mic4]
    tdoa_results: List[TdoaPair] = []

    # reference sample rate (from mic1)
    sr_ref = mic1.get_audio().get_sample_rate()

    for mic in signal_mics:
        audio2 = mic.get_audio().get_audio_signal(index=chunk_index)
        if audio2 is None:
            continue

        # ensure numpy arrays
        sig1 = np.asarray(audio1)
        sig2 = np.asarray(audio2)

        # trim to same length (GCC-PHAT can work with different lengths but trimming keeps things stable)
        min_len = min(sig1.shape[0], sig2.shape[0])
        if sig1.shape[0] != min_len:
            sig1 = sig1[:min_len]
        if sig2.shape[0] != min_len:
            sig2 = sig2[:min_len]

        # check sample rates
        sr_other = mic.get_audio().get_sample_rate()
        if sr_other != sr_ref:
            raise ValueError(f"Sample rate mismatch between {mic1.get_name()} ({sr_ref}) and {mic.get_name()} ({sr_other}). Resample before computing TDoA.")

        # Compute TDoA using GCC-PHAT. Use sig=audio1 and refsig=audio2 so that
        # the returned tau corresponds to (t1 - t2). That matches the multilateration
        # convention used later where distance difference = (dist1 - dist2) = tau * c.
        tdoa, cc = gcc_phat(sig=sig1, refsig=sig2, fs=sr_ref, max_tau=None)

        tdoa_pair = TdoaPair(mic1=mic1, mic2=mic, tdoa=tdoa)
        tdoa_results.append(tdoa_pair)

        if debug:
            print(str(tdoa_pair))

    return tdoa_results
