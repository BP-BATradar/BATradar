from pathlib import Path
from core.audio import Audio
from core.microphone import Microphone
from tdoa_calc import get_all_tdoa_of_chunk_index_by_gcc_phat
from multilateration import multilaterate_by_tdoa_pairs

#Mic names and their corresponding WAV files
outdir = Path(__file__).parent / "output"
mic_names = ["bl","tl","br","tr"] 

#Assign wav files to mic names
mic_files = {}
for name in mic_names:
    matches = sorted(outdir.glob(f"{name}.wav")) 
    if not matches:
        raise FileNotFoundError(f"No file for mic '{name}' in {outdir}")
    mic_files[name] = matches[-1]

m1 = Microphone(x=0.0, y=0.0, name="bl")
m2 = Microphone(x=0.0, y=3.0, name="tl")
m3 = Microphone(x=3.0, y=0.0, name="br")
m4 = Microphone(x=3.0, y=3.0, name="tr")

m1.set_audio(Audio(filepath=str(mic_files["bl"])))
m2.set_audio(Audio(filepath=str(mic_files["tl"])))
m3.set_audio(Audio(filepath=str(mic_files["br"])))
m4.set_audio(Audio(filepath=str(mic_files["tr"])))

tdoa_results = get_all_tdoa_of_chunk_index_by_gcc_phat(m1, m2, m3, m4, chunk_index=0, debug=True)

xs, ys = multilaterate_by_tdoa_pairs(tdoa_results)
print("Estimated source position:", xs, ys)