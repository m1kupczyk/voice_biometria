import os
import subprocess

# Ścieżka do Twojego folderu z intruzami
INTRUDER_DIR = "dataset/intruders"

print("Rozpoczynam konwersję plików .m4a do .wav...")
converted_count = 0

for root, dirs, files in os.walk(INTRUDER_DIR):
    for file in files:
        if file.endswith(".m4a"):
            m4a_path = os.path.join(root, file)
            # Tworzymy nową nazwę pliku z końcówką .wav
            wav_path = os.path.splitext(m4a_path)[0] + ".wav"
            
            # Wywołujemy wbudowane narzędzie systemowe macOS 'afconvert'
            command = f'afconvert -f WAVE -d LEI16 "{m4a_path}" "{wav_path}"'
            os.system(command)
            
            # Usuwamy stary plik .m4a, żeby nie zajmował miejsca (opcjonalne)
            os.remove(m4a_path)
            
            converted_count += 1
            print(f"✅ Przekonwertowano: {file}")

print(f"Gotowe! Zamieniono {converted_count} plików .m4a na .wav.")