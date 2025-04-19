import subprocess
import time
import re
from tqdm import tqdm
from datetime import datetime
import os

# Set model directory for Ollama
os.environ['OLLAMA_MODELS'] = '/data/wdblue8tb/ollama'

# Open log file
log_file = open(f"ollama_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", "w")

# Models to download
model_ls = [
    "athene-v2",
    "aya-expanse:8b-q4_K_S",
    "cogito",
    "command-r",
    "command-r7b:7b-12-2024-q4_K_M",
    "deepcoder",
    "deepseek-r1:7b-qwen-distill-q4_K_M",
    "deepseek-r1:8b-llama-distill-q4_K_M",
    "dolphin3:8b-llama3.1-q4_K_M",
    "exaone3.5:7.8b-instruct-q4_K_M",
    "falcon",
    "falcon3:7b-instruct-q4_K_M",
    "gemma2",
    "gemma3:4b-it-q8_0",
    "glm4:9b-chat-q4_K_M",
    "granite3-dense:8b-instruct-q4_K_M",
    "granite3.1-dense:8b-instruct-q4_K_M",
    "granite3.1-moe:3b-instruct-q8_0",
    "granite3.2-vision:2b-fp16",
    "granite3.2-vision:2b-q8_0",
    "hermes3:8b-llama3.1-q3_K_M",
    "internlm2:7b-chat-1m-v2.5-q4_K_M",
    "llama2",
    "llama3.1:8b-instruct-q4_K_M",
    "llama3.2:3b-instruct-q8_0",
    "llama3.2:3b-text-fp16",
    "llama3.3",
    "marco-o1:7b-q4_K_M",
    "mistral:7b-instruct-q4_K_M",
    "mistral-small3.1",
    "mixtral",
    "nemotron",
    "nemotron-mini",
    "olmo2:7b-1124-instruct-q4_K_M",
    "openthinker:7b-q4_K_M",
    "phi3.5",
    "phi4",
    "phi4-mini:3.8b-q4_K_M",
    "phi4-mini:3.8b-q8_0",
    "qwen2.5:7b-instruct-q4_K_M",
    "qwq",
    "reflection",
    "sailor2:8b-chat-q4_K_M",
    "smallthinker:3b-preview-q8_0",
    "smollm2",
    "solar-pro",
    "tulu3:8b-q4_K_M",
    "vicuna",
    "wizardlm",
    "yi"
]

DELAY_BETWEEN_DOWNLOADS_SEC = 5

def extract_progress(text):
    match = re.search(r'(\d+)%', text)
    return int(match.group(1)) if match else None

def get_downloaded_models() -> list:
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
        return [line.split()[0] for line in lines[1:] if line.strip()]
    except Exception as e:
        print(f"Failed to list models: {e}")
        return []

def download_model(model_name, timeout=3600):
    try:
        print(f"⏬ Downloading {model_name}")
        pbar = tqdm(total=100, desc=model_name, unit='%')
        process = subprocess.Popen(
            ["ollama", "pull", model_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        last_progress = 0
        start = time.time()
        last_activity = start

        for line in iter(process.stdout.readline, ''):
            log_file.write(line)
            progress = extract_progress(line)
            if progress and progress > last_progress:
                pbar.update(progress - last_progress)
                last_progress = progress
                last_activity = time.time()
            elif time.time() - last_activity > 300:
                print("⚠️  Stalled download detected.")
                break

        process.wait(timeout=30)
        if process.returncode != 0:
            print(f"❌ Error downloading {model_name}")
        else:
            print(f"✅ Done: {model_name}")
        pbar.update(100 - last_progress)
        pbar.close()
    except Exception as e:
        print(f"❌ Exception: {e}")
        pbar.close()

def main():
    downloaded = set(get_downloaded_models())
    print(f"✅ Already downloaded: {downloaded}")
    for model in model_ls:
        if model in downloaded:
            print(f"⏩ Skipping {model}")
            continue
        download_model(model)
        time.sleep(DELAY_BETWEEN_DOWNLOADS_SEC)

if __name__ == "__main__":
    main()
