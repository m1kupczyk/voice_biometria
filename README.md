# System kontroli dostępu oparty na biometrii głosowej


## Wymagania
- Python 3.10+ (testowane na 3.12)
- Mikrofon (system poprosi o zgodę na dostęp)

## Instalacja
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Uruchomienie aplikacji
```bash
python app.py
```
Po starcie ładowanie bibliotek może potrwać 30–60 s — należy poczekać na okno.

- **Logowanie głosem:** przeczytaj wylosowaną frazę po rozpoczęciu nagrywania.
- **Zapasowy PIN:** domyślnie `1234` (można zmienić w panelu po zalogowaniu).

## Zawartość
| Plik | Opis |
|---|---|
| `app.py` | interfejs graficzny (logowanie + panel) |
| `security.py` | ekstrakcja cech MFCC, liveness, PIN, blokada, audyt |
| `train_model.py` | trening modeli GMM (użytkownik + UBM) |
| `evaluate.py` | ewaluacja jakości systemu (FAR/FRR/EER) |
| `models/` | wytrenowane modele GMM (gotowe do uruchomienia) |
| `config.json` | hash zapasowego PIN-u (PBKDF2-HMAC-SHA256) |
| `requirements.txt` | zależności |

> Modele są już wytrenowane — aplikację można uruchomić od razu, bez treningu.
> `train_model.py` i `evaluate.py` wymagają dodatkowo katalogu `dataset/` z próbkami.
