import io
import os
import zipfile
import requests
import shutil

STOCKFISH_URL = "https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-windows-x86-64-avx2.zip"
DEST_DIR = "bin"
STOCKFISH_EXE_NAME = "stockfish-windows-x86-64-avx2.exe"

def setup_stockfish():
    if not os.path.exists(DEST_DIR):
        os.makedirs(DEST_DIR)
        print(f"Created directory: {DEST_DIR}")

    print(f"Downloading Stockfish from {STOCKFISH_URL}...")
    try:
        response = requests.get(STOCKFISH_URL)
        response.raise_for_status()
        print("Download complete.")

        print("Extracting...")
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            # List files to find the exe
            for file_info in z.infolist():
                if file_info.filename.endswith(".exe") and "stockfish" in file_info.filename.lower():
                    # Extract specifically this file to the bin dir
                    file_info.filename = os.path.basename(file_info.filename) # Flatten path
                    z.extract(file_info, DEST_DIR)
                    print(f"Extracted {file_info.filename} to {DEST_DIR}")
                    return

        print("Could not find Stockfish executable in zip.")
    except Exception as e:
        print(f"Error setting up Stockfish: {e}")

if __name__ == "__main__":
    setup_stockfish()
