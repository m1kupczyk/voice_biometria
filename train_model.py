import os
import random
import numpy as np
from sklearn.mixture import GaussianMixture
import joblib

import security  # wspólna ekstrakcja cech (identyczna jak w app.py i evaluate.py)

# Foldery z danymi
USER_DIR = "dataset/user"
INTRUDER_DIR = "dataset/intruders"
MODEL_DIR = "models"

# Ile ramek chcemy zebrać od intruzów.
# Przy ~500 ramkach na plik wystarczy ~1000 losowych plików.
# Wczytanie wszystkich 39 000+ trwałoby kilka godzin — bez żadnego zysku dla GMM.
MAX_SAMPLES = 500_000
FRAMES_PER_FILE_EST = 500
MAX_INTRUDER_FILES = MAX_SAMPLES // FRAMES_PER_FILE_EST  # ~1000 plików

os.makedirs(MODEL_DIR, exist_ok=True)


def collect_audio_files(folder):
    """Zwraca listę ścieżek do wszystkich .wav/.flac w folderze (rekurencyjnie)."""
    paths = []
    for root, _, files in os.walk(folder):
        for f in files:
            if f.endswith((".wav", ".flac")):
                paths.append(os.path.join(root, f))
    return paths


def load_features(file_paths, label=""):
    """Wczytuje MFCC z podanych plików i łączy je w jedną macierz."""
    features_list = []
    total = len(file_paths)
    for i, path in enumerate(file_paths, 1):
        try:
            features_list.append(security.extract_mfcc_from_file(path))
            if i % 100 == 0 or i == total:
                print(f"  [{i}/{total}] wczytano")
        except Exception as e:
            print(f"  Pominięto {os.path.basename(path)}: {e}")
    return np.vstack(features_list) if features_list else np.array([])


print("--- ETAP 1: Przygotowanie danych ---")

# Próbki użytkownika – wczytujemy wszystkie (jest ich mało)
user_files = collect_audio_files(USER_DIR)
print(f"Próbki użytkownika: {len(user_files)} plików")
user_features = load_features(user_files)
print(f"Dane użytkownika gotowe: {len(user_features)} ramek.\n")

# Próbki intruzów – losujemy tylko tyle plików, ile potrzeba
all_intruder_files = collect_audio_files(INTRUDER_DIR)
print(f"Plików intruzów dostępnych: {len(all_intruder_files)}")

# WAŻNE: intruzi "priorytetowi" MUSZĄ trafić do treningu zawsze, inaczej
# utonęliby w losowaniu z 39 000 plików. To są:
#   - household/ : domownicy nagrani TWOIM mikrofonem (np. tata),
#   - polish/    : polskie głosy (akustycznie bliższe Tobie niż obcokrajowcy).
# Dzięki nim model uczy się odróżniać Ciebie od podobnych, polskich głosów.
PRIORITY_SUBDIRS = ["household", "polish"]
priority_files = []
for sub in PRIORITY_SUBDIRS:
    d = os.path.join(INTRUDER_DIR, sub)
    if os.path.isdir(d):
        files = collect_audio_files(d)
        if files:
            print(f"Intruzi priorytetowi z '{sub}': {len(files)} plików (zawsze w treningu)")
            priority_files.extend(files)

priority_set = set(priority_files)
other_files = [f for f in all_intruder_files if f not in priority_set]

# Resztę do limitu dobieramy losowo z dużego datasetu (dla różnorodności)
remaining = max(0, MAX_INTRUDER_FILES - len(priority_files))
if len(other_files) > remaining:
    other_selected = random.sample(other_files, remaining)
    print(f"Losowo dobieram {remaining} plików z dużego datasetu.")
else:
    other_selected = other_files

selected = priority_files + other_selected
print(f"Wczytuję {len(selected)} plików intruzów...")
intruder_features = load_features(selected)
print(f"Dane intruzów gotowe: {len(intruder_features)} ramek.\n")

print("--- ETAP 2: Trenowanie modeli ---")

print("Trenowanie modelu użytkownika...")
user_gmm = GaussianMixture(n_components=16, covariance_type='diag',
                           max_iter=200, random_state=42, reg_covar=1e-3)
user_gmm.fit(user_features)

print("Trenowanie modelu tła (intruzów)...")
ubm_gmm = GaussianMixture(n_components=16, covariance_type='diag',
                          max_iter=200, random_state=42, reg_covar=1e-3)
ubm_gmm.fit(intruder_features)

print("\n--- ETAP 3: Zapisywanie modeli na dysk ---")
joblib.dump(user_gmm, os.path.join(MODEL_DIR, "user_model.gmm"))
joblib.dump(ubm_gmm, os.path.join(MODEL_DIR, "ubm_model.gmm"))

print("✅ Sukces! Modele zostały wygenerowane i zapisane w folderze 'models'.")
