import os

print(">>> Uruchamianie VoiceAuth Pro... ladowanie bibliotek moze potrwac 30-60 s.", flush=True)
print(">>> POCZEKAJ az pojawi sie okno. NIE naciskaj Ctrl+C.", flush=True)

import sys
import threading
import subprocess
import tkinter as tk

import numpy as np
import sounddevice as sd
import joblib
import customtkinter as ctk

import security

print(">>> Biblioteki zaladowane, otwieram okno...", flush=True)

# --- USTAWIENIA GŁÓWNE ---
FS = 16000
DURATION = 3
MODEL_DIR = "models"
USER_DIR = "dataset/user"
USER_ID = "owner"
THRESHOLD_PERCENT = 70.0

# --- PALETA / WYGLĄD ---
ACCENT = "#4cc9f0"        # jasny błękit – akcent
ACCENT_DARK = "#1f6f8b"
GREEN = "#06d6a0"
RED = "#ef476f"
YELLOW = "#ffd166"
CARD = "#1b1f2a"
CARD2 = "#232838"
BG = "#11131a"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class VoiceAuthApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("VoiceAuth Pro — System Kontroli Dostępu")
        self.geometry("960x640")
        self.minsize(880, 600)
        self.configure(fg_color=BG)

        # Czcionki
        self.font_h1 = ctk.CTkFont(family="SF Pro Display", size=30, weight="bold")
        self.font_h2 = ctk.CTkFont(family="SF Pro Display", size=20, weight="bold")
        self.font_body = ctk.CTkFont(family="SF Pro Text", size=14)
        self.font_small = ctk.CTkFont(family="SF Pro Text", size=12)
        self.font_mono = ctk.CTkFont(family="Menlo", size=13)

        # Modele
        self.user_gmm = None
        self.ubm_gmm = None
        self.models_ok = self._load_models()

        # Bezpieczeństwo
        security.ensure_default_pin()
        self.attempts = security.AttemptManager()

        # Dane ostatniego logowania (do pulpitu)
        self.last_method = None
        self.last_score = None
        self.last_mfcc = None

        # Kontener na strony
        self.container = ctk.CTkFrame(self, fg_color=BG)
        self.container.pack(fill="both", expand=True)

        self.login_frame = LoginFrame(self.container, self)
        self.dashboard_frame = None

        self.show_login()

    # ---------- Modele ----------
    def _load_models(self):
        try:
            self.user_gmm = joblib.load(os.path.join(MODEL_DIR, "user_model.gmm"))
            self.ubm_gmm = joblib.load(os.path.join(MODEL_DIR, "ubm_model.gmm"))
            return True
        except Exception:
            return False

    # ---------- Nawigacja ----------
    def show_login(self):
        if self.dashboard_frame is not None:
            self.dashboard_frame.pack_forget()
        self.login_frame.pack(fill="both", expand=True)
        self.login_frame.reset()

    def enter_dashboard(self, method, score=None, mfcc=None):
        self.last_method = method
        self.last_score = score
        self.last_mfcc = mfcc
        self.login_frame.pack_forget()
        # Tworzymy panel na nowo, by odświeżyć dane
        if self.dashboard_frame is not None:
            self.dashboard_frame.destroy()
        self.dashboard_frame = DashboardFrame(self.container, self)
        self.dashboard_frame.pack(fill="both", expand=True)

    def logout(self):
        security.log_event(USER_ID, "LOGOUT", detail=f"Metoda sesji: {self.last_method}")
        self.last_method = None
        self.last_score = None
        self.last_mfcc = None
        self.show_login()


# =====================================================================
# STRONA LOGOWANIA
# =====================================================================
class LoginFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=BG)
        self.controller = controller

        self.is_recording = False
        self.recorded_frames = []
        self.stream = None
        self.current_volume = 0.0
        self.phase = 0.0
        self.current_phrase = ""

        # Nagłówek
        header = ctk.CTkLabel(self, text="🔐 VoiceAuth Pro", font=controller.font_h1, text_color="white")
        header.pack(pady=(40, 2))
        sub = ctk.CTkLabel(self, text="System kontroli dostępu oparty na biometrii głosowej",
                           font=controller.font_body, text_color="#8a93a6")
        sub.pack(pady=(0, 20))

        # Karta logowania
        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=20)
        card.pack(padx=40, pady=10, fill="x")

        ctk.CTkLabel(card, text="Logowanie biometryczne", font=controller.font_h2,
                     text_color="white").pack(pady=(22, 4))

        self.lbl_phrase = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=15, slant="italic"),
                                       text_color=YELLOW, wraplength=520)
        self.lbl_phrase.pack(pady=(0, 6))

        self.canvas = ctk.CTkCanvas(card, width=520, height=110, bg=CARD2, highlightthickness=0)
        self.canvas.pack(pady=8)
        self.draw_wave(0)

        self.btn_voice = ctk.CTkButton(card, text="🎤  Zaloguj głosem", font=controller.font_h2,
                                       height=52, corner_radius=14, fg_color=ACCENT,
                                       hover_color=ACCENT_DARK, text_color="#06222e",
                                       command=self.start_voice_login)
        self.btn_voice.pack(pady=14, padx=40, fill="x")

        # Separator "albo"
        sep = ctk.CTkFrame(card, fg_color="transparent")
        sep.pack(fill="x", padx=40, pady=(4, 4))
        ctk.CTkFrame(sep, height=1, fg_color="#333a4d").pack(side="left", fill="x", expand=True, pady=10)
        ctk.CTkLabel(sep, text="  albo  ", font=controller.font_small, text_color="#6b7280").pack(side="left")
        ctk.CTkFrame(sep, height=1, fg_color="#333a4d").pack(side="left", fill="x", expand=True, pady=10)

        # PIN
        pin_row = ctk.CTkFrame(card, fg_color="transparent")
        pin_row.pack(pady=(4, 22), padx=40, fill="x")
        self.entry_pin = ctk.CTkEntry(pin_row, placeholder_text="Wpisz PIN", show="•",
                                      height=46, corner_radius=12, font=controller.font_body)
        self.entry_pin.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.entry_pin.bind("<Return>", lambda e: self.login_pin())
        self.btn_pin = ctk.CTkButton(pin_row, text="Zaloguj PIN-em", width=140, height=46,
                                     corner_radius=12, fg_color=CARD2, hover_color="#2e3550",
                                     command=self.login_pin)
        self.btn_pin.pack(side="left")

        # Status
        self.lbl_status = ctk.CTkLabel(self, text="", font=controller.font_body, text_color="#8a93a6")
        self.lbl_status.pack(pady=8)

        if not controller.models_ok:
            self.lbl_status.configure(text="⚠️ Brak modeli — uruchom najpierw train_model.py", text_color=RED)
            self.btn_voice.configure(state="disabled")

        
    def reset(self):
        self.lbl_phrase.configure(text="")
        self.entry_pin.delete(0, "end")
        if self.controller.models_ok:
            self.lbl_status.configure(text="", text_color="#8a93a6")
        self.btn_voice.configure(state="normal" if self.controller.models_ok else "disabled",
                                 text="🎤  Zaloguj głosem")
        self.draw_wave(0)

    # ---------- Animacja fali ----------
    def draw_wave(self, amplitude):
        self.canvas.delete("all")
        width, height = 520, 110
        mid_y = height / 2
        self.phase += 0.4
        pts_main, pts_echo = [], []
        for x in range(0, width, 5):
            att = np.sin(np.pi * (x / width))
            pts_main.extend([x, mid_y + np.sin((x * 0.05) + self.phase) * amplitude * att])
            pts_echo.extend([x, mid_y + np.sin((x * 0.03) - self.phase) * (amplitude * 0.5) * att])
        self.canvas.create_line(pts_echo, fill=ACCENT_DARK, width=2, smooth=True)
        self.canvas.create_line(pts_main, fill=ACCENT, width=3, smooth=True)

    def update_animation(self):
        if self.is_recording:
            amp = min(self.current_volume * 80, 45)
            self.draw_wave(amp)
            self.after(30, self.update_animation)
        else:
            self.draw_wave(0)

    def audio_callback(self, indata, frames, t, status):
        self.current_volume = np.linalg.norm(indata) * 10
        if self.is_recording:
            self.recorded_frames.append(indata.copy())

    # ---------- Logowanie głosem ----------
    def start_voice_login(self):
        if self.controller.attempts.is_locked():
            rem = self.controller.attempts.remaining_lock()
            self.lbl_status.configure(text=f"🔒 Zablokowano. Spróbuj za {rem} s.", text_color=RED)
            security.log_event(USER_ID, "LOCKED", detail=f"Pozostała blokada: {rem}s")
            return

        self.is_recording = True
        self.recorded_frames = []
        self.current_phrase = security.get_random_phrase()
        self.lbl_phrase.configure(text=f"Powiedz: „{self.current_phrase}”")
        self.lbl_status.configure(text="🔴 Słucham... mów wyraźnie przez 3 sekundy", text_color=GREEN)
        self.btn_voice.configure(state="disabled", text="Trwa weryfikacja...")
        self.entry_pin.configure(state="disabled")
        self.btn_pin.configure(state="disabled")

        self.stream = sd.InputStream(samplerate=FS, channels=1, callback=self.audio_callback)
        self.stream.start()
        self.update_animation()
        self.after(int(DURATION * 1000), self.process_voice)

    def process_voice(self):
        self.is_recording = False
        try:
            self.stream.stop()
            self.stream.close()
        except Exception:
            pass
        self.draw_wave(0)
        self.lbl_status.configure(text="Analiza biometryczna...", text_color="white")
        self.update_idletasks()

        if self.recorded_frames:
            audio = np.concatenate(self.recorded_frames, axis=0)
        else:
            audio = np.zeros((FS, 1), dtype="float32")

        self._unlock_inputs()

        try:
            alive, details = security.liveness_check(audio, FS)
            if not alive:
                self.lbl_status.configure(text=f"⚠️ Podejrzane nagranie: {details['reason']}", text_color=RED)
                security.log_event(USER_ID, "SPOOF_DETECTED", detail=details["reason"])
                self._register_fail()
                return

            mfccs = security.extract_mfcc(audio, FS)
            delta = self.controller.user_gmm.score(mfccs) - self.controller.ubm_gmm.score(mfccs)
            score = 100 / (1 + np.exp(-delta))

            if score >= THRESHOLD_PERCENT:
                self.controller.attempts.register_success()
                security.log_event(USER_ID, "GRANTED", score=score, detail="Głos")
                self.lbl_status.configure(text=f"✅ Dostęp przyznany ({score:.1f}%)", text_color=GREEN)
                self.btn_voice.configure(text="🎤  Zaloguj głosem")
                self.after(500, lambda: self.controller.enter_dashboard("Głos", score, mfccs))
            else:
                security.log_event(USER_ID, "DENIED", score=score, detail=f"Głos, poniżej {THRESHOLD_PERCENT}%")
                self.lbl_status.configure(text=f"❌ Odmowa dostępu ({score:.1f}%)", text_color=RED)
                self._register_fail()
        except Exception as e:
            self.lbl_status.configure(text=f"Błąd analizy: {e}", text_color=RED)
            security.log_event(USER_ID, "ERROR", detail=str(e))

    # ---------- Logowanie PIN ----------
    def login_pin(self):
        if self.controller.attempts.is_locked():
            rem = self.controller.attempts.remaining_lock()
            self.lbl_status.configure(text=f"🔒 Zablokowano. Spróbuj za {rem} s.", text_color=RED)
            return
        pin = self.entry_pin.get().strip()
        if not pin:
            self.lbl_status.configure(text="Wpisz PIN.", text_color=YELLOW)
            return
        if security.verify_pin(pin):
            self.controller.attempts.register_success()
            security.log_event(USER_ID, "GRANTED", detail="PIN")
            self.lbl_status.configure(text="✅ PIN poprawny", text_color=GREEN)
            self.after(300, lambda: self.controller.enter_dashboard("PIN", None, None))
        else:
            security.log_event(USER_ID, "DENIED", detail="Błędny PIN")
            self.lbl_status.configure(text="❌ Błędny PIN", text_color=RED)
            self.entry_pin.delete(0, "end")
            self._register_fail()

    # ---------- Pomocnicze ----------
    def _register_fail(self):
        locked = self.controller.attempts.register_failure()
        if locked:
            security.log_event(USER_ID, "LOCKED",
                               detail=f"Limit prób, blokada {security.LOCKOUT_SECONDS}s")
            self.lbl_status.configure(text=f"🔒 Zbyt wiele prób! Blokada {security.LOCKOUT_SECONDS} s.",
                                      text_color=RED)
        self.btn_voice.configure(text="🎤  Zaloguj głosem")

    def _unlock_inputs(self):
        self.btn_voice.configure(state="normal")
        self.entry_pin.configure(state="normal")
        self.btn_pin.configure(state="normal")


# =====================================================================
# PANEL (DASHBOARD)
# =====================================================================
class DashboardFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color=BG)
        self.controller = controller
        self.train_thread = None

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=220, fg_color=CARD, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        ctk.CTkLabel(self.sidebar, text="VoiceAuth Pro", font=controller.font_h2,
                     text_color=ACCENT).pack(pady=(28, 4), padx=20)
        ctk.CTkLabel(self.sidebar, text=f"Zalogowano: {controller.last_method}",
                     font=controller.font_small, text_color="#8a93a6").pack(pady=(0, 24))

        self.nav_buttons = {}
        for key, label, icon in [
            ("home", "Pulpit", "📊"),
            ("history", "Historia logowań", "🕒"),
            ("train", "Dotrenuj model", "🎙️"),
            ("pin", "Zmień PIN", "🔑"),
        ]:
            b = ctk.CTkButton(self.sidebar, text=f"  {icon}  {label}", anchor="w",
                              font=controller.font_body, height=44, corner_radius=10,
                              fg_color="transparent", hover_color=CARD2,
                              command=lambda k=key: self.show_section(k))
            b.pack(fill="x", padx=14, pady=3)
            self.nav_buttons[key] = b

        ctk.CTkButton(self.sidebar, text="  🚪  Wyloguj", anchor="w", font=controller.font_body,
                      height=44, corner_radius=10, fg_color="transparent", hover_color="#3a1f2a",
                      text_color=RED, command=controller.logout).pack(side="bottom", fill="x",
                                                                      padx=14, pady=18)

        # Obszar treści
        self.content = ctk.CTkFrame(self, fg_color=BG)
        self.content.pack(side="left", fill="both", expand=True)

        self.show_section("home")

    # ---------- Przełączanie sekcji ----------
    def show_section(self, key):
        for child in self.content.winfo_children():
            child.destroy()
        for k, b in self.nav_buttons.items():
            b.configure(fg_color=CARD2 if k == key else "transparent")
        {
            "home": self.build_home,
            "history": self.build_history,
            "train": self.build_train,
            "pin": self.build_pin,
        }[key]()

    def _section_title(self, text, subtitle=""):
        ctk.CTkLabel(self.content, text=text, font=self.controller.font_h1,
                     text_color="white").pack(anchor="w", padx=30, pady=(28, 0))
        if subtitle:
            ctk.CTkLabel(self.content, text=subtitle, font=self.controller.font_body,
                         text_color="#8a93a6").pack(anchor="w", padx=30, pady=(2, 16))
        else:
            ctk.CTkLabel(self.content, text="", height=8).pack()

    # ---------- PULPIT ----------
    def build_home(self):
        c = self.controller
        self._section_title("Pulpit", "Podsumowanie ostatniego logowania i statystyki bezpieczeństwa")

        top = ctk.CTkFrame(self.content, fg_color="transparent")
        top.pack(fill="x", padx=30, pady=6)

        # Karta: dokładność ostatniej próby
        gauge_card = ctk.CTkFrame(top, fg_color=CARD, corner_radius=18)
        gauge_card.pack(side="left", padx=(0, 14))
        ctk.CTkLabel(gauge_card, text="Dokładność Twojej próby", font=c.font_h2,
                     text_color="white").pack(pady=(18, 4), padx=24)
        gauge = ctk.CTkCanvas(gauge_card, width=200, height=200, bg=CARD, highlightthickness=0)
        gauge.pack(padx=24, pady=(0, 20))
        if c.last_score is not None:
            self._draw_gauge(gauge, c.last_score, 200)
        else:
            self._draw_gauge_text(gauge, "PIN", "Logowano PIN-em", 200)

        # Karta: voiceprint (wow-feature)
        vp_card = ctk.CTkFrame(top, fg_color=CARD, corner_radius=18)
        vp_card.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(vp_card, text="🧬 Twój odcisk głosowy (MFCC)", font=c.font_h2,
                     text_color="white").pack(pady=(18, 2), padx=24, anchor="w")
        ctk.CTkLabel(vp_card, text="Wizualizacja 20 współczynników barwy głosu z Twojej próby",
                     font=c.font_small, text_color="#8a93a6").pack(padx=24, anchor="w")
        vp = ctk.CTkCanvas(vp_card, width=460, height=150, bg=CARD2, highlightthickness=0)
        vp.pack(padx=24, pady=18, fill="x")
        if c.last_mfcc is not None:
            self.after(60, lambda: self._draw_voiceprint(vp, c.last_mfcc))
        else:
            vp.create_text(230, 75, text="Dostępne po logowaniu głosem",
                           fill="#6b7280", font=("SF Pro Text", 13))

        # Statystyki
        stats = security.history_stats()
        row = ctk.CTkFrame(self.content, fg_color="transparent")
        row.pack(fill="x", padx=30, pady=14)
        self._stat_card(row, "Wszystkie próby", str(stats["total"]), ACCENT)
        self._stat_card(row, "Udane", str(stats["granted"]), GREEN)
        self._stat_card(row, "Odrzucone", str(stats["denied"]), RED)
        self._stat_card(row, "Skuteczność", f"{stats['success_rate']:.0f}%", YELLOW)

    def _stat_card(self, parent, title, value, color):
        card = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=16)
        card.pack(side="left", fill="x", expand=True, padx=6)
        ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=28, weight="bold"),
                     text_color=color).pack(pady=(16, 0))
        ctk.CTkLabel(card, text=title, font=self.controller.font_small,
                     text_color="#8a93a6").pack(pady=(0, 16))

    # ---------- HISTORIA ----------
    def build_history(self):
        self._section_title("Historia logowań", "Pełny dziennik prób z datą, godziną i wynikiem")
        rows = security.read_history(limit=200)

        wrapper = ctk.CTkFrame(self.content, fg_color=CARD2, corner_radius=12)
        wrapper.pack(fill="both", expand=True, padx=30, pady=(0, 20))

        if not rows:
            ctk.CTkLabel(wrapper, text="Brak zapisanych zdarzeń.",
                         text_color="#6b7280").pack(pady=20)
            return

        # Pojedynczy widget Text = bardzo szybkie renderowanie (zamiast setek ramek)
        txt = tk.Text(wrapper, bg=CARD2, fg="#c8d0e0", bd=0, highlightthickness=0,
                      wrap="none", padx=14, pady=10, font=("Menlo", 12), spacing1=2, spacing3=2,
                      cursor="arrow")
        scrollbar = ctk.CTkScrollbar(wrapper, command=txt.yview)
        scrollbar.pack(side="right", fill="y", pady=6)
        txt.configure(yscrollcommand=scrollbar.set)
        txt.pack(side="left", fill="both", expand=True, padx=6, pady=6)

        colors = {"GRANTED": GREEN, "DENIED": RED, "SPOOF_DETECTED": RED,
                  "LOCKED": YELLOW, "LOGOUT": "#8a93a6", "ERROR": YELLOW, "PIN_CHANGED": ACCENT}
        labels = {"GRANTED": "✅ Przyznano", "DENIED": "❌ Odmowa", "SPOOF_DETECTED": "⚠️ Spoofing",
                  "LOCKED": "🔒 Blokada", "LOGOUT": "🚪 Wylogowano", "ERROR": "⚠️ Błąd",
                  "PIN_CHANGED": "🔑 Zmiana PIN"}
        for res, col in colors.items():
            txt.tag_config(res, foreground=col)
        txt.tag_config("head", foreground="#8a93a6")

        txt.insert("end", f"{'DATA I GODZINA':<22}{'WYNIK':<16}{'PEWNOŚĆ':<10}SZCZEGÓŁY\n", "head")
        txt.insert("end", "─" * 78 + "\n", "head")
        for r in rows:
            res = r.get("result", "")
            ts = r.get("timestamp", "")
            sc = r.get("score_percent", "")
            sc = f"{sc}%" if sc else "—"
            label = labels.get(res, res)
            detail = r.get("detail", "")
            txt.insert("end", f"{ts:<22}{label:<15}{sc:<10}{detail}\n", res)

        txt.configure(state="disabled")

    # ---------- DOTRENUJ ----------
    def build_train(self):
        self._section_title("Dotrenuj model", "Dodaj więcej swoich próbek głosu, by zwiększyć dokładność")

        card = ctk.CTkFrame(self.content, fg_color=CARD, corner_radius=18)
        card.pack(fill="x", padx=30, pady=6)

        ctk.CTkLabel(card, text="Liczba nowych próbek do nagrania:", font=self.controller.font_body,
                     text_color="white").pack(anchor="w", padx=24, pady=(20, 4))

        self.sample_count = ctk.IntVar(value=5)
        slider_row = ctk.CTkFrame(card, fg_color="transparent")
        slider_row.pack(fill="x", padx=24)
        self.slider = ctk.CTkSlider(slider_row, from_=3, to=15, number_of_steps=12,
                                    variable=self.sample_count, command=self._update_count_lbl)
        self.slider.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.lbl_count = ctk.CTkLabel(slider_row, text="5", font=self.controller.font_h2,
                                      text_color=ACCENT, width=40)
        self.lbl_count.pack(side="left")

        self.btn_train = ctk.CTkButton(card, text="🎙️  Nagraj próbki i przetrenuj",
                                       font=self.controller.font_h2, height=50, corner_radius=14,
                                       fg_color=ACCENT, hover_color=ACCENT_DARK, text_color="#06222e",
                                       command=self.start_training)
        self.btn_train.pack(fill="x", padx=24, pady=18)

        self.train_status = ctk.CTkLabel(card, text="Gotowy. Kliknij, by rozpocząć.",
                                         font=self.controller.font_body, text_color="#8a93a6")
        self.train_status.pack(pady=(0, 6))
        self.train_bar = ctk.CTkProgressBar(card, height=10, corner_radius=6)
        self.train_bar.set(0)
        self.train_bar.pack(fill="x", padx=24, pady=(0, 22))

        info = ctk.CTkFrame(self.content, fg_color=CARD, corner_radius=18)
        info.pack(fill="x", padx=30, pady=10)
        ctk.CTkLabel(info, text="💡 Wskazówka", font=self.controller.font_h2,
                     text_color=YELLOW).pack(anchor="w", padx=24, pady=(16, 2))
        ctk.CTkLabel(info, text="Mów od razu po starcie nagrania, wyraźnie przez całe 3 sekundy,\n"
                                "tym samym mikrofonem co przy logowaniu. Więcej próbek = wyższa dokładność.",
                     font=self.controller.font_body, text_color="#b8c0d0",
                     justify="left").pack(anchor="w", padx=24, pady=(0, 18))

    def _update_count_lbl(self, _=None):
        self.lbl_count.configure(text=str(self.sample_count.get()))

    def start_training(self):
        if self.train_thread and self.train_thread.is_alive():
            return
        count = self.sample_count.get()
        self.btn_train.configure(state="disabled", text="Trwa nagrywanie...")
        self.slider.configure(state="disabled")
        self.train_thread = threading.Thread(target=self._train_worker, args=(count,), daemon=True)
        self.train_thread.start()

    def _set_train_status(self, text, progress=None, color="#8a93a6"):
        def upd():
            self.train_status.configure(text=text, text_color=color)
            if progress is not None:
                self.train_bar.set(progress)
        self.after(0, upd)

    def _record_clip(self):
        frames = []

        def cb(indata, n, t, s):
            frames.append(indata.copy())

        with sd.InputStream(samplerate=FS, channels=1, callback=cb):
            sd.sleep(int(DURATION * 1000))
        if not frames:
            return np.zeros((FS, 1), dtype="float32")
        return np.concatenate(frames, axis=0)

    def _next_index(self):
        nums = []
        for f in os.listdir(USER_DIR):
            if f.startswith("sample_") and f.endswith(".wav"):
                try:
                    nums.append(int(f.replace("sample_", "").replace(".wav", "")))
                except ValueError:
                    pass
        return max(nums, default=0) + 1

    def _train_worker(self, count):
        from scipy.io.wavfile import write
        try:
            os.makedirs(USER_DIR, exist_ok=True)
            idx = self._next_index()
            saved = 0
            for i in range(count):
                self._set_train_status(f"🔴 Nagrywam próbkę {i + 1}/{count} — MÓW TERAZ!",
                                       progress=(i / (count + 1)), color=GREEN)
                audio = self._record_clip()
                peak = float(np.max(np.abs(audio)))
                if peak < 0.01:
                    self._set_train_status(f"⚠️ Próbka {i + 1} za cicha — pomijam.", color=YELLOW)
                    sd.sleep(600)
                    continue
                write(os.path.join(USER_DIR, f"sample_{idx}.wav"), FS, audio)
                idx += 1
                saved += 1
                self._set_train_status(f"✅ Zapisano próbkę {i + 1}/{count}", progress=((i + 1) / (count + 1)))
                sd.sleep(500)

            if saved == 0:
                self._set_train_status("Nie nagrano żadnej próbki. Sprawdź mikrofon.", color=RED)
                self._reset_train_button()
                return

            self._set_train_status("⚙️ Trenuję model... to może potrwać kilka minut.",
                                   progress=0.9, color=ACCENT)
            result = subprocess.run([sys.executable, "train_model.py"],
                                    capture_output=True, text=True)
            if result.returncode == 0:
                self.after(0, self.controller._load_models)
                self._set_train_status(f"✅ Gotowe! Dodano {saved} próbek i przetrenowano model.",
                                       progress=1.0, color=GREEN)
            else:
                self._set_train_status(f"❌ Błąd treningu: {result.stderr[-200:]}", color=RED)
        except Exception as e:
            self._set_train_status(f"❌ Błąd: {e}", color=RED)
        finally:
            self._reset_train_button()

    def _reset_train_button(self):
        def upd():
            self.btn_train.configure(state="normal", text="🎙️  Nagraj próbki i przetrenuj")
            self.slider.configure(state="normal")
        self.after(0, upd)

    # ---------- ZMIANA PIN ----------
    def build_pin(self):
        self._section_title("Zmień PIN", "PIN to zapasowa metoda logowania (przechowywany jako hash z solą)")

        card = ctk.CTkFrame(self.content, fg_color=CARD, corner_radius=18)
        card.pack(fill="x", padx=30, pady=6)

        ctk.CTkLabel(card, text="Obecny PIN", font=self.controller.font_body,
                     text_color="white").pack(anchor="w", padx=24, pady=(20, 2))
        self.pin_old = ctk.CTkEntry(card, show="•", height=44, corner_radius=12)
        self.pin_old.pack(fill="x", padx=24)

        ctk.CTkLabel(card, text="Nowy PIN", font=self.controller.font_body,
                     text_color="white").pack(anchor="w", padx=24, pady=(14, 2))
        self.pin_new = ctk.CTkEntry(card, show="•", height=44, corner_radius=12)
        self.pin_new.pack(fill="x", padx=24)

        ctk.CTkLabel(card, text="Powtórz nowy PIN", font=self.controller.font_body,
                     text_color="white").pack(anchor="w", padx=24, pady=(14, 2))
        self.pin_new2 = ctk.CTkEntry(card, show="•", height=44, corner_radius=12)
        self.pin_new2.pack(fill="x", padx=24)

        ctk.CTkButton(card, text="Zapisz nowy PIN", font=self.controller.font_h2, height=48,
                      corner_radius=14, fg_color=ACCENT, hover_color=ACCENT_DARK,
                      text_color="#06222e", command=self.change_pin).pack(fill="x", padx=24, pady=18)

        self.pin_status = ctk.CTkLabel(card, text="", font=self.controller.font_body)
        self.pin_status.pack(pady=(0, 18))

    def change_pin(self):
        old = self.pin_old.get().strip()
        new = self.pin_new.get().strip()
        new2 = self.pin_new2.get().strip()
        if not security.verify_pin(old):
            self.pin_status.configure(text="❌ Obecny PIN jest błędny.", text_color=RED)
            return
        if len(new) < 4:
            self.pin_status.configure(text="❌ Nowy PIN musi mieć min. 4 znaki.", text_color=RED)
            return
        if new != new2:
            self.pin_status.configure(text="❌ Nowe PIN-y nie są takie same.", text_color=RED)
            return
        security.set_pin(new)
        security.log_event(USER_ID, "PIN_CHANGED", detail="Użytkownik zmienił PIN")
        self.pin_status.configure(text="✅ PIN został zmieniony.", text_color=GREEN)
        self.pin_old.delete(0, "end")
        self.pin_new.delete(0, "end")
        self.pin_new2.delete(0, "end")

    # ---------- RYSOWANIE (wow-features) ----------
    def _draw_gauge(self, canvas, percent, size):
        canvas.delete("all")
        pad = 18
        canvas.create_oval(pad, pad, size - pad, size - pad, outline="#2a3040", width=14)
        color = GREEN if percent >= THRESHOLD_PERCENT else (YELLOW if percent >= 45 else RED)
        extent = -3.6 * percent
        canvas.create_arc(pad, pad, size - pad, size - pad, start=90, extent=extent,
                          style="arc", outline=color, width=14)
        canvas.create_text(size / 2, size / 2 - 6, text=f"{percent:.0f}%",
                           fill="white", font=("SF Pro Display", 34, "bold"))
        status = "PRZYZNANO" if percent >= THRESHOLD_PERCENT else "ODMOWA"
        canvas.create_text(size / 2, size / 2 + 26, text=status, fill=color,
                           font=("SF Pro Text", 12, "bold"))

    def _draw_gauge_text(self, canvas, big, small, size):
        canvas.delete("all")
        pad = 18
        canvas.create_oval(pad, pad, size - pad, size - pad, outline="#2a3040", width=14)
        canvas.create_text(size / 2, size / 2 - 6, text=big, fill=ACCENT,
                           font=("SF Pro Display", 30, "bold"))
        canvas.create_text(size / 2, size / 2 + 24, text=small, fill="#8a93a6",
                           font=("SF Pro Text", 11))

    def _draw_voiceprint(self, canvas, mfcc):
        canvas.delete("all")
        w = canvas.winfo_width() or 460
        h = 150
        means = np.mean(mfcc, axis=0)
        n = len(means)
        lo, hi = means.min(), means.max()
        rng = (hi - lo) if (hi - lo) > 1e-9 else 1.0
        norm = (means - lo) / rng
        gap = 6
        bw = (w - gap * (n + 1)) / n

        self._vp_canvas = canvas
        self._vp_h = h
        self._vp_bars = []  # (x0, x1, index, percent)
        for i, v in enumerate(norm):
            bar_h = 12 + v * (h - 30)
            x0 = gap + i * (bw + gap)
            y0 = h - bar_h
            shade = int(80 + v * 160)
            color = f"#{shade // 3:02x}{shade:02x}{min(255, shade + 40):02x}"
            canvas.create_rectangle(x0, y0, x0 + bw, h - 4, fill=color, outline="", tags=f"bar{i}")
            self._vp_bars.append((x0, x0 + bw, i, float(v) * 100))

        canvas.bind("<Motion>", self._vp_hover)
        canvas.bind("<Leave>", lambda e: (canvas.delete("tip"), canvas.delete("hl")))

    def _vp_hover(self, event):
        c = self._vp_canvas
        c.delete("tip")
        c.delete("hl")
        for x0, x1, i, pct in self._vp_bars:
            if x0 <= event.x <= x1:
                # podświetl słupek
                c.create_rectangle(x0 - 1, 4, x1 + 1, self._vp_h - 4, outline=ACCENT, width=2, tags="hl")
                # dymek z wartością procentową
                label = f"MFCC {i + 1}: {pct:.0f}%"
                tx = min(max(event.x, 45), (c.winfo_width() or 460) - 45)
                c.create_rectangle(tx - 42, 6, tx + 42, 26, fill="#0c1018", outline=ACCENT, tags="tip")
                c.create_text(tx, 16, text=label, fill="white",
                              font=("SF Pro Text", 11, "bold"), tags="tip")
                break


if __name__ == "__main__":
    app = VoiceAuthApp()
    app.mainloop()
