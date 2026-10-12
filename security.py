"""
Moduł bezpieczeństwa dla systemu biometrii głosowej.

Zawiera mechanizmy wymagane w kontekście "Bezpieczeństwa systemów komputerowych":
  1. Logowanie zdarzeń (audyt) -> logs/access_log.csv
  2. Licznik prób + blokada czasowa (ochrona przed atakiem brute-force)
  3. Prosty test anty-spoofingowy (liveness) + wyzwanie losową frazą (challenge-response)
"""

import os
import csv
import time
import json
import random
import hashlib
import secrets
from datetime import datetime

import numpy as np
import librosa

# --- KONFIGURACJA ---
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "access_log.csv")

# Ile nieudanych prób z rzędu, zanim system się zablokuje
MAX_ATTEMPTS = 3
# Na ile sekund blokujemy logowanie po przekroczeniu limitu prób
LOCKOUT_SECONDS = 30

# Losowe frazy do wyzwania (challenge-response). Użytkownik widzi inną za każdym razem,
# co utrudnia przygotowanie wcześniejszego nagrania (atak typu replay).
RANDOM_PHRASES = [
    "Czerwony samochód jedzie szybko",
    "Zielona trawa rośnie wiosną",
    "Siedem mostów nad rzeką",
    "Mój głos jest moim hasłem",
    "Słońce świeci nad górami",
    "Trzy koty śpią na kanapie",
    "Otwórz drzwi do laboratorium",
    "Bezpieczeństwo to podstawa systemu",
]


def get_random_phrase():
    """Zwraca losową frazę do wypowiedzenia przez użytkownika."""
    return random.choice(RANDOM_PHRASES)


# =====================================================================
# 0. WSPÓLNA EKSTRAKCJA CECH (MFCC + normalizacja)
# =====================================================================
# WAŻNE: ta sama funkcja jest używana przy TRENINGU (train_model.py),
# LOGOWANIU (app.py) i EWALUACJI (evaluate.py). Dzięki temu cechy są
# liczone identycznie wszędzie – inaczej model nie rozpozna użytkownika.
N_MFCC = 20


def extract_mfcc(audio, sr=16000):
    """
    Liczy MFCC z normalizacją odporną na różnice mikrofonu/głośności:
      1) przycięcie ciszy (pauzy i cisza nie psują wyniku – stabilniejsze % na żywo),
      2) normalizacja amplitudy (głośność nagrania przestaje mieć znaczenie),
      3) CMVN (Cepstral Mean-Variance Normalization) – usuwa wpływ kanału/mikrofonu.
    Zwraca macierz [liczba_ramek x N_MFCC].
    """
    audio = np.asarray(audio, dtype=np.float32).flatten()

    # 1) przytnij ciszę z początku/końca – liczą się tylko fragmenty z mową.
    # To eliminuje skoki wyniku, gdy nagranie łapie pauzę albo opóźniony start.
    try:
        trimmed, _ = librosa.effects.trim(audio, top_db=25)
        if trimmed.size >= int(0.3 * sr):  # zostaw tylko jeśli zostało min. 0.3 s mowy
            audio = trimmed
    except Exception:
        pass

    # 2) normalizacja amplitudy
    peak = np.max(np.abs(audio))
    if peak > 1e-6:
        audio = audio / peak

    mfccs = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=N_MFCC)

    # 3) CMVN – dla każdego współczynnika odejmij średnią i podziel przez odchylenie
    mfccs = (mfccs - np.mean(mfccs, axis=1, keepdims=True)) / (np.std(mfccs, axis=1, keepdims=True) + 1e-9)

    return mfccs.T


def extract_mfcc_from_file(file_path, sr=16000):
    """Wczytuje plik audio i zwraca znormalizowane MFCC."""
    audio, sample_rate = librosa.load(file_path, sr=sr)
    return extract_mfcc(audio, sample_rate)


# =====================================================================
# PIN – druga metoda uwierzytelniania (przechowywany jako hash z solą)
# =====================================================================
CONFIG_FILE = "config.json"
DEFAULT_PIN = "1234"


def _load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f)


def _hash_pin(pin, salt):
    # PBKDF2 – dużo trudniejszy do złamania niż zwykły hash
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), 100_000).hex()


def set_pin(pin):
    """Ustawia nowy PIN (zapisuje sól + hash, nigdy jawnego PIN-u)."""
    salt = secrets.token_hex(16)
    cfg = _load_config()
    cfg["pin_salt"] = salt
    cfg["pin_hash"] = _hash_pin(pin, salt)
    _save_config(cfg)


def pin_is_set():
    cfg = _load_config()
    return "pin_hash" in cfg and "pin_salt" in cfg


def ensure_default_pin():
    """Jeśli PIN nie jest jeszcze ustawiony, ustaw domyślny."""
    if not pin_is_set():
        set_pin(DEFAULT_PIN)
        return True
    return False


def verify_pin(pin):
    """Sprawdza PIN w sposób odporny na ataki czasowe."""
    cfg = _load_config()
    if not pin_is_set():
        ensure_default_pin()
        cfg = _load_config()
    candidate = _hash_pin(pin, cfg["pin_salt"])
    return secrets.compare_digest(candidate, cfg["pin_hash"])


# =====================================================================
# Odczyt historii logowań (dla panelu w aplikacji)
# =====================================================================
def read_history(limit=50):
    """Zwraca listę ostatnich zdarzeń (najnowsze pierwsze) jako listę słowników."""
    if not os.path.exists(LOG_FILE):
        return []
    rows = []
    with open(LOG_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    rows.reverse()
    return rows[:limit]


def history_stats():
    """Prosta statystyka logowań do pulpitu: liczba prób, udane, skuteczność."""
    if not os.path.exists(LOG_FILE):
        return {"total": 0, "granted": 0, "denied": 0, "success_rate": 0.0, "last_login": "-"}
    total = granted = denied = 0
    last_login = "-"
    with open(LOG_FILE, "r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            result = row.get("result", "")
            if result in ("GRANTED", "DENIED", "SPOOF_DETECTED"):
                total += 1
            if result == "GRANTED":
                granted += 1
                last_login = row.get("timestamp", "-")
            elif result in ("DENIED", "SPOOF_DETECTED"):
                denied += 1
    rate = (granted / total * 100) if total else 0.0
    return {"total": total, "granted": granted, "denied": denied,
            "success_rate": rate, "last_login": last_login}


# =====================================================================
# 1. LOGOWANIE ZDARZEŃ (AUDYT)
# =====================================================================
def log_event(user, result, score=None, detail=""):
    """
    Zapisuje zdarzenie bezpieczeństwa do pliku CSV.

    user   - identyfikator użytkownika/konta (np. "owner")
    result - wynik zdarzenia, np. GRANTED / DENIED / SPOOF_DETECTED / LOCKED
    score  - pewność systemu w procentach (lub None)
    detail - dodatkowy opis (np. powód odrzucenia)
    """
    os.makedirs(LOG_DIR, exist_ok=True)
    file_exists = os.path.exists(LOG_FILE)

    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "user", "result", "score_percent", "detail"])
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        score_str = f"{score:.1f}" if isinstance(score, (int, float)) else ""
        writer.writerow([timestamp, user, result, score_str, detail])


# =====================================================================
# 2. LICZNIK PRÓB + BLOKADA CZASOWA
# =====================================================================
class AttemptManager:
    """
    Pilnuje liczby nieudanych prób logowania i wprowadza blokadę czasową
    po przekroczeniu limitu (ochrona przed brute-force / wielokrotnym podszywaniem).
    """

    def __init__(self, max_attempts=MAX_ATTEMPTS, lockout_seconds=LOCKOUT_SECONDS):
        self.max_attempts = max_attempts
        self.lockout_seconds = lockout_seconds
        self.failed_attempts = 0
        self.lock_until = 0.0  # znacznik czasu (time.time()), do kiedy obowiązuje blokada

    def is_locked(self):
        """Czy system jest aktualnie zablokowany."""
        return time.time() < self.lock_until

    def remaining_lock(self):
        """Ile sekund pozostało blokady (zaokrąglone w górę)."""
        remaining = self.lock_until - time.time()
        return max(0, int(np.ceil(remaining)))

    def register_failure(self):
        """
        Rejestruje nieudaną próbę. Zwraca True, jeśli przekroczono limit
        i właśnie nałożono blokadę.
        """
        self.failed_attempts += 1
        if self.failed_attempts >= self.max_attempts:
            self.lock_until = time.time() + self.lockout_seconds
            self.failed_attempts = 0  # reset licznika po nałożeniu blokady
            return True
        return False

    def register_success(self):
        """Udane logowanie kasuje licznik nieudanych prób."""
        self.failed_attempts = 0

    def attempts_left(self):
        """Ile prób pozostało do blokady."""
        return self.max_attempts - self.failed_attempts


# =====================================================================
# 3. TEST ANTY-SPOOFINGOWY (LIVENESS)
# =====================================================================
def liveness_check(audio, sr):
    """
    Prosty heurystyczny test "żywotności" nagrania.

    Cel: odróżnić żywą mowę od ataków typu:
      - cisza / brak mowy (ktoś nie mówi),
      - czysty ton / sygnał syntetyczny,
      - bardzo płaski / monotonny sygnał.

    Analizujemy:
      - energię (RMS) -> czy w ogóle ktoś mówi,
      - dynamikę energii -> żywa mowa ma naturalne wahania głośności,
      - tempo/sylaby (onsety) -> mowa ma rytm w ludzkim zakresie,
      - płaskość widmową -> szum/ton mają inną charakterystykę niż mowa.

    Zwraca: (passed: bool, details: dict)
    """
    details = {}

    audio = np.asarray(audio, dtype=np.float32).flatten()

    # Czy nagranie nie jest po prostu ciszą (sprawdzamy na surowym sygnale)
    raw_peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    details["raw_peak"] = round(raw_peak, 5)
    has_energy = raw_peak > 0.01

    # Normalizujemy amplitudę, by progi nie zależały od głośności/mikrofonu
    if raw_peak > 1e-6:
        audio = audio / raw_peak

    # --- Energia (RMS) ---
    rms = librosa.feature.rms(y=audio)[0]
    mean_rms = float(np.mean(rms))
    std_rms = float(np.std(rms))
    details["mean_rms"] = round(mean_rms, 5)
    details["std_rms"] = round(std_rms, 5)

    # Żywa mowa ma wahania głośności (sylaby, pauzy). Odtworzony ton bywa płaski.
    # Współczynnik zmienności energii:
    energy_variation = std_rms / (mean_rms + 1e-9)
    details["energy_variation"] = round(energy_variation, 3)
    has_dynamics = energy_variation > 0.15

    # --- Tempo / sylaby (detekcja onsetów) ---
    onset_env = librosa.onset.onset_strength(y=audio, sr=sr)
    onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
    duration = len(audio) / sr
    syllable_rate = len(onsets) / max(duration, 1e-9)  # onsety na sekundę
    details["onsets"] = int(len(onsets))
    details["syllable_rate"] = round(syllable_rate, 2)
    # Ludzka mowa to mniej więcej 1–8 "uderzeń" sylabicznych na sekundę;
    # zostawiamy szeroki zakres, by nie odrzucać prawdziwego głosu.
    human_tempo = 0.5 <= syllable_rate <= 15.0

    # --- Płaskość widmowa ---
    # Bliska 1.0 = sygnał szumopodobny; bardzo niska = czysty ton syntetyczny.
    flatness = float(np.mean(librosa.feature.spectral_flatness(y=audio)))
    details["spectral_flatness"] = round(flatness, 4)
    natural_spectrum = 1e-5 < flatness < 0.7

    passed = bool(has_energy and has_dynamics and human_tempo and natural_spectrum)

    # Powód odrzucenia (do logu i komunikatu)
    reason = []
    if not has_energy:
        reason.append("brak mowy/cisza")
    if not has_dynamics:
        reason.append("brak dynamiki (możliwy replay/ton)")
    if not human_tempo:
        reason.append("nietypowe tempo mowy")
    if not natural_spectrum:
        reason.append("nienaturalne widmo")
    details["reason"] = ", ".join(reason) if reason else "OK"

    return passed, details
