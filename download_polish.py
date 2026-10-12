"""
Pobiera polskie nagrania głosowe i zapisuje je jako "intruzów".

Po co: domyślny dataset intruzów to Chińczycy (CN-Celeb) i głównie Anglicy
(VoxCeleb). Przy biometrii MFCC głosy z tego samego języka są akustycznie
BLIŻSZE Twojemu, więc model tła (UBM) zbudowany na polskich głosach znacznie
lepiej odróżni Ciebie od innego Polaka (np. członka rodziny).

Źródło: Google FLEURS (split polski 'pl_pl') – darmowy, bez logowania,
wielu różnych mówców, nagrania już w 16 kHz.

Wymaga biblioteki 'datasets':
    pip install datasets soundfile

Użycie:
    python download_polish.py
"""

import os
import io
import soundfile as sf

OUT_DIR = "dataset/intruders/polish"
TARGET = 800  # ile polskich nagrań pobrać


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    try:
        from datasets import load_dataset, Audio
    except ImportError:
        print("Brak biblioteki 'datasets'. Zainstaluj ją poleceniem:")
        print("    pip install datasets soundfile")
        return

    print("Pobieram polskie nagrania z FLEURS (pl_pl)... to może chwilę potrwać.")
    ds = load_dataset("google/fleurs", "pl_pl", split="train", streaming=True)

    # WAŻNE: wyłączamy automatyczne dekodowanie audio (decode=False), żeby NIE
    # wymagać biblioteki 'torchcodec'. Surowe bajty dekodujemy sami przez soundfile.
    ds = ds.cast_column("audio", Audio(decode=False))

    n = 0
    skipped = 0
    for ex in ds:
        audio = ex["audio"]
        raw = audio.get("bytes")

        try:
            if raw is not None:
                data, sr = sf.read(io.BytesIO(raw))
            elif audio.get("path") and os.path.exists(audio["path"]):
                data, sr = sf.read(audio["path"])
            else:
                skipped += 1
                continue
        except Exception:
            skipped += 1
            continue

        out_path = os.path.join(OUT_DIR, f"pl_{n:04d}.wav")
        sf.write(out_path, data, sr)
        n += 1
        if n % 50 == 0:
            print(f"  pobrano {n}/{TARGET}")
        if n >= TARGET:
            break

    print(f"\nGotowe! Zapisano {n} polskich nagrań do {OUT_DIR} (pominięto {skipped}).")
    print("Teraz uruchom trening:  python train_model.py")


if __name__ == "__main__":
    main()
