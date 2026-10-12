"""
Rejestracja głosu (enrollment) tym samym torem nagrywania co logowanie w app.py.

Po co: model najlepiej rozpoznaje Cię wtedy, gdy próbki treningowe są nagrane
TYM SAMYM mikrofonem i w ten sam sposób co logowanie. Ten skrypt nagrywa
kilka próbek przez sounddevice (16 kHz, mono) – identycznie jak aplikacja –
zapisuje je do dataset/user/ i na końcu uruchamia trening.

Użycie:
    python enroll.py
"""

import os
import sys
import subprocess

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write

# Parametry IDENTYCZNE jak w app.py – to klucz do dobrego dopasowania
FS = 16000
DURATION = 3
USER_DIR = "dataset/user"
TRAIN_SCRIPT = "train_model.py"

# Ile próbek nagrać w tej sesji (więcej = wyższe i stabilniejsze wyniki na żywo)
ENROLL_SAMPLES = 30

# Frazy podpowiadane przy nagrywaniu (możesz mówić własne)
PHRASES = [
    "Mój głos jest moim hasłem dostępu do systemu",
    "Autoryzacja głosowa to nowoczesna biometria",
    "Bezpieczeństwo systemów komputerowych jest ważne",
    "System rozpoznaje mnie po unikalnych cechach głosu",
    "Weryfikacja tożsamości na podstawie głosu",
    "Logowanie biometryczne zastępuje tradycyjne hasła",
    "Każdy człowiek ma niepowtarzalny głos",
    "Otwórz drzwi do laboratorium informatycznego",
    "Czerwony samochód jedzie szybko przez miasto",
    "Zielona trawa rośnie wiosną na łące",
    "Siedem mostów stoi nad szeroką rzeką",
    "Słońce świeci jasno nad wysokimi górami",
    "Programowanie w Pythonie sprawia mi radość",
    "Kryptografia chroni dane przesyłane w sieci",
    "Mój projekt dotyczy biometrii głosowej",
]


def next_index(folder):
    nums = []
    for f in os.listdir(folder):
        if f.startswith("sample_") and f.endswith(".wav"):
            try:
                nums.append(int(f.replace("sample_", "").replace(".wav", "")))
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
    os.makedirs(USER_DIR, exist_ok=True)

    print("=" * 55)
    print(" REJESTRACJA GŁOSU – nagrywanie próbek treningowych")
    print("=" * 55)

    idx = next_index(USER_DIR)

    print(f"Nagramy {ENROLL_SAMPLES} próbek po {DURATION} s.")
    print("Mów normalnym głosem, tak jak potem przy logowaniu.\n")

    recorded = 0
    for i in range(ENROLL_SAMPLES):
        phrase = PHRASES[i % len(PHRASES)]
        print(f"[{i + 1}/{ENROLL_SAMPLES}] Powiedz: \u201e{phrase}\u201d")
        input("    Wciśnij ENTER i od razu zacznij mówić...")
        print("    🔴 Nagrywam...")

        audio = record_clip()
        peak = float(np.max(np.abs(audio)))

        if peak < 0.01:
            print("    ⚠️  Bardzo cicho! Mikrofon prawie nic nie nagrał – ta próbka pominięta.")
            print("        Sprawdź uprawnienia mikrofonu i mów głośniej.\n")
            continue

        path = os.path.join(USER_DIR, f"sample_{idx}.wav")
        write(path, FS, audio)
        print(f"    ✅ Zapisano {os.path.basename(path)} (głośność szczytowa: {peak:.2f})\n")
        idx += 1
        recorded += 1

    print(f"Nagrano {recorded} poprawnych próbek.\n")

    if recorded == 0:
        print("Nie nagrano żadnej próbki – trening pominięty. Sprawdź mikrofon.")
        sys.exit(1)

    print("=" * 55)
    print("Uruchamiam trening modelu...")
    print("=" * 55 + "\n")
    result = subprocess.run([sys.executable, TRAIN_SCRIPT])
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
