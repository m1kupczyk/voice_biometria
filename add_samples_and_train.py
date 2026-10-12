"""
Konwersja nowych próbek głosu M4A → WAV i automatyczne przetrenowanie modelu.

Jak używać:
  1. Wrzuć nagrane pliki .m4a do folderu  dataset/user/
  2. Uruchom ten skrypt:   python add_samples_and_train.py
  3. Skrypt sam skonwertuje pliki, ponumeruje je i odpali trening.
"""

import os
import subprocess
import sys

USER_DIR = "dataset/user"
TRAIN_SCRIPT = "train_model.py"


def find_next_index(folder):
    """Zwraca kolejny wolny numer sample_N.wav w podanym folderze."""
    existing = []
    for f in os.listdir(folder):
        if f.startswith("sample_") and f.endswith(".wav"):
            try:
                existing.append(int(f.replace("sample_", "").replace(".wav", "")))
            except ValueError:
                pass
    return max(existing, default=0) + 1


def convert_m4a_to_wav(m4a_path, wav_path):
    """Konwertuje jeden plik M4A → WAV 16 kHz mono za pomocą afconvert (macOS)."""
    cmd = ["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", m4a_path, wav_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())


def main():
    os.makedirs(USER_DIR, exist_ok=True)

    # Szukaj wszystkich .m4a w dataset/user (bez podfolderów – wprost tam wrzucasz pliki)
    m4a_files = sorted(
        f for f in os.listdir(USER_DIR)
        if f.lower().endswith(".m4a")
    )

    if not m4a_files:
        print("Nie znaleziono żadnych plików .m4a w folderze dataset/user/")
        print("Wrzuć nagrania .m4a do tego folderu i uruchom skrypt ponownie.")
        sys.exit(0)

    print(f"Znaleziono {len(m4a_files)} plików .m4a do konwersji.\n")

    next_idx = find_next_index(USER_DIR)
    converted = 0
    errors = 0

    for m4a_file in m4a_files:
        m4a_path = os.path.join(USER_DIR, m4a_file)
        wav_name = f"sample_{next_idx}.wav"
        wav_path = os.path.join(USER_DIR, wav_name)

        try:
            convert_m4a_to_wav(m4a_path, wav_path)
            os.remove(m4a_path)
            print(f"  ✅  {m4a_file}  →  {wav_name}")
            next_idx += 1
            converted += 1
        except Exception as e:
            print(f"  ❌  {m4a_file}  –  błąd: {e}")
            errors += 1

    print(f"\nKonwersja zakończona: {converted} plików OK, {errors} błędów.")

    # Policz łączną liczbę próbek użytkownika
    total_wav = sum(1 for f in os.listdir(USER_DIR) if f.endswith(".wav"))
    print(f"Łącznie próbek w dataset/user: {total_wav}\n")

    if converted == 0:
        print("Brak nowo przekonwertowanych plików – trening pominięty.")
        sys.exit(0)

    # Uruchom trening
    print("=" * 50)
    print("Uruchamiam trening modelu (train_model.py)...")
    print("=" * 50 + "\n")

    train_result = subprocess.run([sys.executable, TRAIN_SCRIPT])
    sys.exit(train_result.returncode)


if __name__ == "__main__":
    main()
