"""
Skrypt ewaluacji systemu biometrii głosowej.

Liczy metryki jakości używane do oceny systemów biometrycznych:
  - FAR (False Acceptance Rate)  – odsetek intruzów błędnie WPUSZCZONYCH,
  - FRR (False Rejection Rate)   – odsetek właściciela błędnie ODRZUCONEGO,
  - EER (Equal Error Rate)       – punkt, w którym FAR = FRR (im niżej, tym lepiej).

Dla każdego nagrania liczymy taki sam wynik jak aplikacja:
    delta = user_gmm.score(mfcc) - ubm_gmm.score(mfcc)
    pewność = sigmoid(delta) * 100 [%]

Następnie przesuwamy próg decyzyjny od 0% do 100% i dla każdego progu
liczymy FAR i FRR, a na końcu znajdujemy EER.

Wyniki zapisujemy do logs/evaluation_report.txt oraz logs/roc_data.csv.
Jeśli dostępny jest matplotlib, generujemy też wykres logs/far_frr_curve.png.

UWAGA: domyślnie ewaluujemy na danych z folderu dataset/ (te same, na których
trenowano model), więc wyniki są optymistyczne. Do raportu warto użyć
osobnych nagrań testowych (held-out), ale do demonstracji metryk to wystarczy.
"""

import os
import csv

import numpy as np
import joblib

import security  # wspólna ekstrakcja cech (identyczna jak w app.py i train_model.py)

MODEL_DIR = "models"
USER_DIR = "dataset/user"
INTRUDER_DIR = "dataset/intruders"
LOG_DIR = "logs"

REPORT_FILE = os.path.join(LOG_DIR, "evaluation_report.txt")
ROC_CSV = os.path.join(LOG_DIR, "roc_data.csv")
PLOT_FILE = os.path.join(LOG_DIR, "far_frr_curve.png")


def score_file(file_path, user_gmm, ubm_gmm):
    """Zwraca pewność systemu w procentach dla pojedynczego pliku."""
    mfccs = security.extract_mfcc_from_file(file_path)
    delta = user_gmm.score(mfccs) - ubm_gmm.score(mfccs)
    probability = 1 / (1 + np.exp(-delta))
    return probability * 100


def collect_scores(folder, user_gmm, ubm_gmm, limit=None):
    """Liczy wyniki dla wszystkich nagrań w folderze (rekurencyjnie)."""
    scores = []
    count = 0
    for root, _, files in os.walk(folder):
        for file in files:
            if not file.endswith((".wav", ".flac")):
                continue
            path = os.path.join(root, file)
            try:
                scores.append(score_file(path, user_gmm, ubm_gmm))
                count += 1
                if limit is not None and count >= limit:
                    return scores
            except Exception as e:
                print(f"  Pominięto {file}: {e}")
    return scores


def compute_far_frr(genuine, impostor, thresholds):
    """
    Dla każdego progu liczy:
      FRR = % nagrań właściciela z wynikiem PONIŻEJ progu (błędne odrzucenie),
      FAR = % nagrań intruzów z wynikiem RÓWNYM/POWYŻEJ progu (błędna akceptacja).
    """
    genuine = np.array(genuine)
    impostor = np.array(impostor)

    far_list, frr_list = [], []
    for t in thresholds:
        frr = np.mean(genuine < t) * 100 if len(genuine) else 0.0
        far = np.mean(impostor >= t) * 100 if len(impostor) else 0.0
        frr_list.append(frr)
        far_list.append(far)
    return np.array(far_list), np.array(frr_list)


def find_eer(thresholds, far, frr):
    """Znajduje EER jako próg, gdzie |FAR - FRR| jest najmniejsze."""
    idx = int(np.argmin(np.abs(far - frr)))
    eer = (far[idx] + frr[idx]) / 2
    return eer, thresholds[idx], idx


def main():
    os.makedirs(LOG_DIR, exist_ok=True)

    print("Ładowanie modeli...")
    user_gmm = joblib.load(os.path.join(MODEL_DIR, "user_model.gmm"))
    ubm_gmm = joblib.load(os.path.join(MODEL_DIR, "ubm_model.gmm"))

    print(f"Liczenie wyników dla właściciela ({USER_DIR})...")
    genuine = collect_scores(USER_DIR, user_gmm, ubm_gmm)
    print(f"  -> {len(genuine)} nagrań")

    # Ograniczamy liczbę intruzów, żeby ewaluacja nie trwała zbyt długo
    print(f"Liczenie wyników dla intruzów ({INTRUDER_DIR})...")
    impostor = collect_scores(INTRUDER_DIR, user_gmm, ubm_gmm, limit=300)
    print(f"  -> {len(impostor)} nagrań")

    if not genuine or not impostor:
        print("BŁĄD: brak wystarczających danych (sprawdź foldery dataset/user i dataset/intruders).")
        return

    thresholds = np.linspace(0, 100, 1001)
    far, frr = compute_far_frr(genuine, impostor, thresholds)
    eer, eer_threshold, idx = find_eer(thresholds, far, frr)

    # FAR/FRR dla progu używanego w aplikacji (70%)
    app_threshold = 70.0
    app_idx = int(np.argmin(np.abs(thresholds - app_threshold)))

    # --- RAPORT TEKSTOWY ---
    lines = []
    lines.append("=" * 55)
    lines.append(" RAPORT EWALUACJI – BIOMETRIA GŁOSOWA")
    lines.append("=" * 55)
    lines.append(f"Nagrania właściciela (genuine): {len(genuine)}")
    lines.append(f"Nagrania intruzów (impostor):   {len(impostor)}")
    lines.append("")
    lines.append(f"Średnia pewność – właściciel: {np.mean(genuine):.1f}%")
    lines.append(f"Średnia pewność – intruzi:    {np.mean(impostor):.1f}%")
    lines.append("")
    lines.append(f"EER (Equal Error Rate): {eer:.2f}%  przy progu {eer_threshold:.1f}%")
    lines.append("")
    lines.append(f"Dla progu aplikacji = {app_threshold:.0f}%:")
    lines.append(f"   FAR (intruzi wpuszczeni):     {far[app_idx]:.2f}%")
    lines.append(f"   FRR (właściciel odrzucony):   {frr[app_idx]:.2f}%")
    lines.append("=" * 55)

    report = "\n".join(lines)
    print("\n" + report)

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report + "\n")
    print(f"\nZapisano raport: {REPORT_FILE}")

    # --- DANE KRZYWEJ DO CSV ---
    with open(ROC_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["threshold_percent", "FAR_percent", "FRR_percent"])
        for t, fa, fr in zip(thresholds, far, frr):
            writer.writerow([f"{t:.1f}", f"{fa:.3f}", f"{fr:.3f}"])
    print(f"Zapisano dane krzywej: {ROC_CSV}")

    # --- WYKRES (opcjonalnie) ---
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        plt.figure(figsize=(8, 5))
        plt.plot(thresholds, far, label="FAR (fałszywa akceptacja)", color="#ff4040")
        plt.plot(thresholds, frr, label="FRR (fałszywe odrzucenie)", color="#1f538d")
        plt.axvline(eer_threshold, color="gray", linestyle="--",
                    label=f"EER = {eer:.2f}%")
        plt.scatter([eer_threshold], [eer], color="black", zorder=5)
        plt.xlabel("Próg decyzyjny [%]")
        plt.ylabel("Błąd [%]")
        plt.title("Krzywe FAR / FRR i punkt EER")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(PLOT_FILE, dpi=120)
        print(f"Zapisano wykres: {PLOT_FILE}")
    except ImportError:
        print("(matplotlib niezainstalowany – pominięto wykres; dane są w roc_data.csv)")


if __name__ == "__main__":
    main()
