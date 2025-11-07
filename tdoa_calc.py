from core.microphone import Microphone
from core.tdoaPair import TdoaPair
from localization.gcc_phat import gcc_phat
from localization.multilateration import multilaterate_by_tdoa_pairs

def get_all_tdoa_of_chunk_index_by_gcc_phat(
    mic1: Microphone,
    mic2: Microphone,
    mic3: Microphone,
    mic4: Microphone,
    chunk_index: int = 0,
    debug: bool = False,
) -> TdoaPair | None:
    

    audio1 = mic1.get_audio().get_audio_signal(index = chunk_index)
    signal_mics = [mic2, mic3, mic4]
    tdoa_results = []

    for mic in signal_mics:
        audio2 = mic.get_audio().get_audio_signal(index=chunk_index)
        if audio2 is not None:
            # Compute TDoA using the compute_tdoa method
            tdoa, cc = gcc_phat(
                sig=audio1, refsig=audio2, fs=mic1.get_audio().get_sample_rate(), max_tau=None
            )

            tdoa_pair = TdoaPair(mic1=mic1, mic2=mic, tdoa=tdoa)

            tdoa_results.append(tdoa_pair)

            if debug:
                print(str(tdoa_pair))

    return tdoa_results

def approximate_sound_source(td_results):
    xs, xy = multilaterate_by_tdoa_pairs(td_results)
    return xs, xy
