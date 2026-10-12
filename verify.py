import os
import librosa
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write
import joblib

# Ustawienia
FS = 16000  # Częstotliwość próbkowania
DURATION = 3  # Czas nagrywania (3 sekundy)
MODEL_DIR = "models"
TEMP_FILE = "temp_login.wav"

# --- SUWAK BEZPIECZEŃSTWA ---
# Zmień tę wartość, by utrudnić lub ułatwić logowanie
THRESHOLD_PERCENT = 70.0 

print("Ładowanie systemu bezpieczeństwa...")
user_gmm = joblib.load(os.path.join(MODEL_DIR, "user_model.gmm"))
ubm_gmm = joblib.load(os.path.join(MODEL_DIR, "ubm_model.gmm"))
print("System gotowy.\n")

def extract_features(file_path):
    audio, sample_rate = librosa.load(file_path, sr=16000)
    mfccs = librosa.feature.mfcc(y=audio, sr=sample_rate, n_mfcc=20)
    return mfccs.T

# --- INTERFEJS LOGOWANIA ---
input("Wciśnij ENTER, aby rozpocząć procedurę logowania...")
print("🔴 Nagrywanie... Powiedz swoje hasło!")

recording = sd.rec(int(DURATION * FS), samplerate=FS, channels=1)
sd.wait()
write(TEMP_FILE, FS, recording)

print("🟢 Koniec nagrywania. Trwa analiza biometryczna...\n")

# --- WERYFIKACJA ---
try:
    features = extract_features(TEMP_FILE)
    
    # 1. Obliczanie surowych punktów
    user_score = user_gmm.score(features)
    ubm_score = ubm_gmm.score(features)
    
    # 2. Przeliczanie na Procenty (Funkcja Sigmoidalna)
    delta = user_score - ubm_score
    # Funkcja exp() z biblioteki numpy załatwia całą matematykę
    probability = 1 / (1 + np.exp(-delta))
    match_percentage = probability * 100
    
    # 3. Wyświetlanie wyników
    print(f"-> Surowy wynik właściciela: {user_score:.2f}")
    print(f"-> Surowy wynik tła (UBM):   {ubm_score:.2f}")
    print(f"\n💡 PEWNOŚĆ SYSTEMU, ŻE TO TY: {match_percentage:.1f}%")
    
    # 4. Decyzja
    print("-" * 45)
    if match_percentage >= THRESHOLD_PERCENT:
        print(f"✅ DOSTĘP PRZYZNANY. (Wymagano {THRESHOLD_PERCENT}%)")
    else:
        print(f"❌ ODMOWA DOSTĘPU. (Wymagano {THRESHOLD_PERCENT}%)")
    print("-" * 45)
        
except Exception as e:
    print(f"Błąd podczas weryfikacji: {e}")
    
# Sprzątanie pliku tymczasowego
if os.path.exists(TEMP_FILE):
    os.remove(TEMP_FILE)