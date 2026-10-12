# System kontroli dostępu oparty na biometrii głosowej

**Aplikacja autoryzująca użytkownika na podstawie unikalnych cech głosu**

Przedmiot: *Bezpieczeństwo systemów komputerowych*

---

## 1. Cel projektu

Celem projektu jest stworzenie systemu kontroli dostępu, który uwierzytelnia
użytkownika na podstawie **biometrii głosowej** — unikalnych cech jego głosu
(barwy, charakterystyki traktu głosowego). System wpuszcza właściciela, a
odrzuca inne osoby, nawet o podobnym głosie (np. członków rodziny). Jako
zapasową metodę logowania zaimplementowano kod **PIN**.

---

## 2. Zasada działania biometrii

System wykorzystuje klasyczne podejście **GMM-UBM** (Gaussian Mixture Model –
Universal Background Model), powszechnie stosowane w rozpoznawaniu mówcy.

### 2.1. Ekstrakcja cech (MFCC)
Z każdego nagrania wyliczane są **współczynniki melowo-cepstralne (MFCC)** —
20 współczynników opisujących barwę głosu w kolejnych ramkach czasowych.
Przed obliczeniem stosowane są:
- **przycięcie ciszy** – pauzy nie psują wyniku (stabilniejsze rozpoznawanie),
- **normalizacja amplitudy** – głośność nagrania przestaje mieć znaczenie,
- **CMVN** (Cepstral Mean-Variance Normalization) – usuwa wpływ mikrofonu/kanału.

Ta sama funkcja (`security.extract_mfcc`) jest używana przy treningu, logowaniu
i ewaluacji — dzięki temu cechy liczone są identycznie wszędzie.

### 2.2. Dwa modele
- **Model użytkownika** – GMM (16 składowych) wytrenowany na próbkach właściciela.
- **Model tła (UBM)** – GMM wytrenowany na głosach innych osób.

### 2.3. Decyzja
Dla nagrania liczona jest różnica logarytmów wiarygodności (log-likelihood ratio):

```
delta = log P(nagranie | model_użytkownika) − log P(nagranie | model_tła)
pewność = sigmoid(delta) × 100%
```

Jeśli `pewność ≥ próg` (domyślnie **70%**) → dostęp przyznany.

---

## 3. Mechanizmy bezpieczeństwa

Projekt realizuje kilka zabezpieczeń istotnych dla przedmiotu:

| Mechanizm | Opis | Plik |
|---|---|---|
| **Uwierzytelnianie biometryczne** | rozpoznawanie mówcy (GMM-UBM) | `app.py`, `security.py` |
| **Druga metoda (PIN)** | PIN jako fallback, przechowywany jako **hash PBKDF2-HMAC-SHA256 (100 000 iteracji) z losową solą** — nigdy jawnie | `security.py` |
| **Odporność na ataki czasowe** | porównanie hashy przez `secrets.compare_digest` | `security.py` |
| **Licznik prób + blokada czasowa** | po 3 nieudanych próbach blokada 30 s (ochrona przed brute-force) | `security.AttemptManager` |
| **Test anty-spoofingowy (liveness)** | wykrywa ciszę/odtworzone nagranie/ton na podstawie energii, dynamiki, tempa mowy i widma | `security.liveness_check` |
| **Challenge-response** | losowa fraza do wypowiedzenia przy każdym logowaniu (utrudnia atak replay) | `security.get_random_phrase` |
| **Audyt zdarzeń** | każde logowanie zapisywane z datą, godziną, wynikiem i pewnością | `logs/access_log.csv` |

**Przechowywanie danych:** PIN tylko jako hash z solą; głos jako statystyczny
model GMM, z którego nie da się odtworzyć nagrania. Dane uwierzytelniające nie
są przechowywane w postaci jawnej.

---

## 4. Interfejs aplikacji

Aplikacja (`app.py`, biblioteka *CustomTkinter*) ma dwa ekrany:

**Ekran logowania:**
- logowanie głosem (animowana fala, losowa fraza) **lub** PIN-em,
- licznik prób i blokada wspólne dla obu metod.

**Panel (po zalogowaniu):**
- **Pulpit** – dokładność ostatniej próby (wskaźnik kołowy), statystyki, oraz
  „odcisk głosowy" (wizualizacja 20 współczynników MFCC z hoverem pokazującym %),
- **Historia logowań** – dziennik prób z datą, godziną i wynikiem,
- **Dotrenuj model** – nagranie dodatkowych próbek i automatyczne przetrenowanie,
- **Zmień PIN** – zmiana PIN-u z weryfikacją starego,
- **Wyloguj**.

---

## 5. Struktura plików

```
app.py                  – aplikacja z interfejsem (logowanie + panel)
security.py             – cechy MFCC, liveness, PIN, blokada, audyt, historia
train_model.py          – trening modeli (użytkownik + UBM)
enroll.py               – nagrywanie próbek użytkownika i trening
record_impostor.py      – nagrywanie głosów innych osób (intruzów)
download_polish.py      – pobranie polskich głosów (FLEURS) jako tła
evaluate.py             – ewaluacja jakości (FAR / FRR / EER)
add_samples_and_train.py– konwersja M4A→WAV i trening
convert_mac.py          – konwersja plików audio (macOS)
verify.py               – prosta weryfikacja w konsoli
models/                 – wytrenowane modele GMM
dataset/user/           – próbki głosu właściciela
dataset/intruders/      – głosy intruzów (cnceleb, voxceleb, polish)
logs/                   – dziennik zdarzeń i raporty ewaluacji
config.json             – hash PIN-u (z solą)
```

---

## 6. Ewaluacja (metryki bezpieczeństwa biometrii)

Skrypt `evaluate.py` liczy standardowe metryki:
- **FAR** (False Acceptance Rate) – odsetek intruzów błędnie wpuszczonych,
- **FRR** (False Rejection Rate) – odsetek właściciela błędnie odrzuconego,
- **EER** (Equal Error Rate) – punkt, w którym FAR = FRR.

Wyniki uzyskane w projekcie (79 nagrań właściciela, 300 intruzów):

| Metryka | Wynik |
|---|---|
| Średnia pewność – właściciel | 95.2% |
| Średnia pewność – intruzi | 3.0% |
| EER | 0.00% (przy progu 9.7%) |
| FAR przy progu 70% | 0.00% |
| FRR przy progu 70% | 1.27% |

**Wniosek dotyczący bezpieczeństwa:** wynik EER = 0% dotyczył „łatwych" intruzów
z internetu (inny język, inny mikrofon). W praktyce trudniejszym przypadkiem jest
osoba spokrewniona, mówiąca do tego samego mikrofonu — cechy głosu są częściowo
dziedziczne, więc FAR rośnie. Aby to ograniczyć, model tła wzbogacono o **polskie
głosy** (zbiór FLEURS), które są akustycznie bliższe użytkownikowi, oraz
umożliwiono dodanie lokalnych próbek negatywnych (`record_impostor.py`). To
pokazuje realny kompromis biometrii: dobór progu oraz reprezentatywnego tła
bezpośrednio wpływa na poziom bezpieczeństwa.

---

## 7. Uruchomienie

```bash
# 1. (opcjonalnie) pobranie polskich głosów tła
pip install datasets soundfile
python download_polish.py

# 2. trening modeli
python train_model.py

# 3. uruchomienie aplikacji
python app.py
```

Domyślny PIN: **1234** (do zmiany w panelu po zalogowaniu).

Wymagane biblioteki: `librosa`, `numpy`, `scipy`, `scikit-learn`, `sounddevice`,
`joblib`, `customtkinter`, `soundfile`.

---

## 8. Ograniczenia i możliwy rozwój

- Wynik na żywo zależy od warunków nagrania (mikrofon, hałas, sposób mówienia) —
  najlepsze efekty daje rejestracja i logowanie tym samym mikrofonem.
- Biometria głosowa ma wyższy FAR dla osób spokrewnionych — można go obniżać
  dodając więcej lokalnych próbek negatywnych i podnosząc próg.
- Możliwy rozwój: adaptacja MAP modelu użytkownika z UBM, cechy delta/delta-delta,
  zaawansowana detekcja spoofingu (anti-replay), wsparcie wielu użytkowników.
