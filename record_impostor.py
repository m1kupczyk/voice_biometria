"""
Nagrywanie głosów INNYCH osób (np. taty, domowników) jako "intruzów".

Po co: model intruzów (UBM) zna tylko obcych ludzi z internetowego datasetu,
nagranych innym mikrofonem. Nie potrafi więc odrzucić kogoś, kto mówi do
TWOJEGO mikrofonu w tym samym pokoju (np. członka rodziny o podobnym głosie).

Ten skrypt nagrywa głosy intruzów tym samym mikrofonem co logowanie i zapisuje
je do dataset/intruders/household/. Po przetrenowaniu model nauczy się, że te
głosy to NIE Ty, i zacznie je odrzucać.

Użycie:
    python record_impostor.py
"""

import os
import sys
import subprocess

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write

# Parametry IDENTYCZNE jak w app.py / enroll.py
FS = 16000
DURATION = 3
IMPOSTOR_DIR = "dataset/intruders/household"
TRAIN_SCRIPT = "train_model.py"

# Ile próbek intruza nagrać w tej sesji
IMPOSTOR_SAMPLES = 15


def next_index(folder):
    nums = []
    for f in os.listdir(folder):
        if f.startswith("imp_") and f.endswith(".wav"):
            try:
                nums.append(int(f.replace("imp_", "").replace(".wav", "")))
            except ValueError:
                pass
    return max(nums, default=0) + 1


def record_clip():
    """Nagrywa DURATION sekund tym samym sposobem co app.py (InputStream + bufor)."""
    frames = []

    def callback(indata, n, t, status):
        frames.append(indata.copy())

    with sd.InputStream(samplerate=FS, channels=1, callback=callback):
        sd.sleep(int(DURATION * 1000))

    if not frames:
        return np.zeros((FS, 1), dtype="float32")
    return np.concatenate(frames, axis=0)


def main():
    os.makedirs(IMPOSTOR_DIR, exist_ok=True)
    idx = next_index(IMPOSTOR_DIR)

    print("=" * 55)
    print(" NAGRYWANIE INTRUZA – głosy innych osób (NIE Ty)")
    print("=" * 55)
    print("Poproś inną osobę (np. tatę), żeby mówiła do mikrofonu.")
    print(f"Nagramy {IMPOSTOR_SAMPLES} próbek po {DURATION} s.")
    print("Najlepiej różne osoby z domu – im więcej, tym lepiej.\n")

    recorded = 0
    for i in range(IMPOSTOR_SAMPLES):
        print(f"[{i + 1}/{IMPOSTOR_SAMPLES}] Niech osoba powie dowolne zdanie.")
        input("    Wciśnij ENTER i niech zacznie mówić...")
        print("    🔴 Nagrywam...")

        audio = record_clip()
        peak = float(np.max(np.abs(audio)))

        if peak < 0.01:
            print("    ⚠️  Bardzo cicho! Próbka pominięta. Mów głośniej.\n")
            continue

        path = os.path.join(IMPOSTOR_DIR, f"imp_{idx}.wav")
        write(path, FS, audio)
        print(f"    ✅ Zapisano {os.path.basename(path)} (głośność: {peak:.2f})\n")
        idx += 1
        recorded += 1

    print(f"Nagrano {recorded} próbek intruza.\n")

    if recorded == 0:
        print("Nie nagrano żadnej próbki – trening pominięty.")
        sys.exit(1)

    print("=" * 55)
    print("Uruchamiam trening modelu...")
    print("=" * 55 + "\n")
    result = subprocess.run([sys.executable, TRAIN_SCRIPT])
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
