from pathlib import Path
from core.audio import Audio
from core.microphone import Microphone
from tdoa_calc import get_all_tdoa_of_chunk_index_by_gcc_phat
from localization.multilateration import multilaterate_by_tdoa_pairs

#Mic names and their corresponding WAV files
outdir = Path(__file__).parent / "output"
mic_names = ["bl","tl","br","tr"] 

#Assign wav files to mic names
mic_files = {}
for name in mic_names:
    matches = sorted(outdir.glob(f"{name}_sync.wav")) 
    if not matches:
        raise FileNotFoundError(f"No file for mic '{name}' in {outdir}")
    mic_files[name] = matches[-1]  # newest

# 2) Erzeuge Microphone-Instanzen mit bekannten Positionen (Meter)
m1 = Microphone(x=0.0, y=0.0, name="bl")
m2 = Microphone(x=0.0, y=1.0, name="tl")
m3 = Microphone(x=1.0, y=0.0, name="br")
m4 = Microphone(x=1.0, y=1.0, name="tr")

# 3) Lade Audios und setze sie
m1.set_audio(Audio(filepath=str(mic_files["bl"])))
m2.set_audio(Audio(filepath=str(mic_files["tl"])))
m3.set_audio(Audio(filepath=str(mic_files["br"])))
m4.set_audio(Audio(filepath=str(mic_files["tr"])))

# 4) Berechne TDoAs für z.B. chunk_index=0 (je nach chunking deiner Audio-Objekte)
tdoa_results = get_all_tdoa_of_chunk_index_by_gcc_phat(m1, m2, m3, m4, chunk_index=0, debug=True)

# 5) Multilateration
xs, ys = multilaterate_by_tdoa_pairs(tdoa_results)
print("Estimated source position:", xs, ys)