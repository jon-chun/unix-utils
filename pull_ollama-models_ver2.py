import subprocess
import time
import re
from tqdm import tqdm
from datetime import datetime

# List of models to download
models = [
    "falcon3:7b-instruct-q4_K_M",
    "exaone3.5:7.8b-instruct-q4_K_M",
    "tulu3:8b-q4_K_M",
    "marco-o1:7b-q4_K_M",
    "olmo2:7b-1124-instruct-q4_K_M",
    "qwen2.5:7b-instruct-q4_K_M",
    "hermes3:8b-llama3.1-q3_K_M",
    "llama3.1:8b-instruct-q4_K_M",
    "mistral:7b-instruct-q4_K_M",
    "deepseek-r1:8b-llama-distill-q4_K_M",
    "gemma3:4b-it-q8_0",
    "deepseek-r1:7b-qwen-distill-q4_K_M",
    "llama3.2:3b-text-fp16",
    "llama3.2:3b-instruct-q8_0",
    "mistral:7b-instruct-q4_K_M",
    "granite3.2-vision:2b-fp16",
    "granite3.2-vision:2b-q8_0",
    "granite3.2-vision:2b-q8_0",
    "phi4-mini:3.8b-q8_0",
    "phi4-mini:3.8b-q4_K_M",
    "openthinker:7b-q4_K_M",
    "command-r7b:7b-12-2024-q4_K_M",
    "dolphin3:8b-llama3.1-q4_K_M",
    "smallthinker:3b-preview-q8_0",
    "granite3.1-dense:8b-instruct-q4_K_M",
    "granite3.1-moe:3b-instruct-q8_0",
    "sailor2:8b-chat-q4_K_M",
    "aya-expanse:8b-q4_K_S",
    "granite3-dense:8b-instruct-q4_K_M",
    "glm4:9b-chat-q4_K_M",
    "internlm2:7b-chat-1m-v2.5-q4_K_M",
]

# Delay between downloads in seconds
DELAY_BETWEEN_DOWNLOADS_SEC = 5

def clean_model_name(name: str) -> str:
    """
    Converts a model name into an OS-safe alias.
    Rules:
      - Lowercase all characters.
      - Keep only alphanumeric, '_' and '-' characters.
      - Replace punctuation (like '.', ':', etc.) with a single dash.
      - Collapse consecutive whitespace into a single underscore.
    """
    # Lowercase the name
    name = name.lower()
    # Replace punctuation that is not alphanumeric, underscore, dash, or whitespace with a dash
    name = re.sub(r'[^\w\s-]', '-', name)
    # Collapse any consecutive whitespace into a single underscore
    name = re.sub(r'\s+', '_', name)
    # Collapse multiple dashes into one dash
    name = re.sub(r'-+', '-', name)
    # Optionally, strip leading/trailing dashes/underscores
    name = name.strip('-_')
    return name

def get_downloaded_models() -> list:
    """
    Runs 'ollama list', parses the output, and returns a list of already downloaded model names.
    Assumes the first column in each non-header line is the model name.
    """
    try:
        process = subprocess.Popen(
            ["ollama", "list"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            print(f"Error running 'ollama list': {stderr.strip()}")
            return []
        
        lines = stdout.strip().splitlines()
        downloaded = []
        # Skip header (assume first line is header)
        for line in lines[1:]:
            # Split line into columns (split by whitespace)
            parts = line.split()
            if parts:
                downloaded.append(parts[0])
        return downloaded
    except Exception as e:
        print(f"An error occurred while listing models: {e}")
        return []

def extract_progress(line):
    """
    Extracts the first integer percentage found in the line.
    For example, from "Progress: 45%" it returns 45.
    """
    match = re.search(r'(\d+)%', line)
    if match:
        return int(match.group(1))
    return None

def download_model(model_name):
    # Create an OS-safe alias for the model
    alias = clean_model_name(model_name)
    try:
        # Print start timestamp with alias info
        start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{start_time}] Starting download: {model_name} (alias: {alias})")
        
        with tqdm(total=100, desc=f"Downloading {alias}", unit='%') as pbar:
            process = subprocess.Popen(
                ["ollama", "pull", model_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            last_progress = 0
            # Process output line by line
            while True:
                line = process.stdout.readline()
                if line:
                    progress = extract_progress(line)
                    if progress is not None and progress > last_progress:
                        pbar.update(progress - last_progress)
                        last_progress = progress
                elif process.poll() is not None:
                    break
            stdout, stderr = process.communicate()
            if last_progress < 100:
                pbar.update(100 - last_progress)
            if process.returncode != 0:
                print(f"Error downloading {model_name}: {stderr.strip()}")
        
        # Print finish timestamp
        end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{end_time}] Finished download: {model_name} (alias: {alias})")
    except Exception as e:
        print(f"An error occurred while downloading {model_name}: {e}")

def main():
    # Get the list of already downloaded models
    downloaded_models = get_downloaded_models()
    print("Downloaded models:", downloaded_models)
    
    # For each model in our list, skip if it's already downloaded
    for model in models:
        if model in downloaded_models:
            print(f"Model '{model}' already downloaded. Skipping.")
            continue
        download_model(model)
        time.sleep(DELAY_BETWEEN_DOWNLOADS_SEC)

if __name__ == "__main__":
    main()
