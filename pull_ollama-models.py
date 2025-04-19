import os
import subprocess
import time
import re
import json
from tqdm import tqdm
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

# ─── CONFIGURATION ─────────────────────────────────────────────
OLLAMA_MODELS_PATH = '/data/wdblue8tb/ollama'
os.environ['OLLAMA_MODELS'] = OLLAMA_MODELS_PATH
CHECKPOINT_FILE = "downloaded_models.json"
LOG_FILE = f"ollama_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
METADATA_JSON = "model_metadata.json"
METADATA_TXT = "model_report.txt"

FLAG_CONCURRENT = False           # Set to True for parallel downloads
CONCURRENT_MAX_DOWN = 2           # Max parallel downloads when FLAG_CONCURRENT is True
DELAY_BETWEEN_DOWNLOADS_SEC = 5

# ─── MODEL LIST BY VENDOR ─────────────────────────────────────
model_groups = {
    "llama": ["llama2", "llama3.1:8b-instruct-q4_K_M", "llama3.2:3b-instruct-q8_0", "llama3.2:3b-text-fp16", "llama3.3"],
    "gemma": ["gemma2", "gemma3:4b-it-q8_0"],
    "phi": ["phi3.5", "phi4", "phi4-mini:3.8b-q4_K_M", "phi4-mini:3.8b-q8_0"],
    "deepseek": ["deepseek-r1:7b-qwen-distill-q4_K_M", "deepseek-r1:8b-llama-distill-q4_K_M"],
    "mistral": ["mistral:7b-instruct-q4_K_M", "mistral-small3.1"],
    "granite": ["granite3-dense:8b-instruct-q4_K_M", "granite3.1-dense:8b-instruct-q4_K_M", "granite3.1-moe:3b-instruct-q8_0", "granite3.2-vision:2b-fp16", "granite3.2-vision:2b-q8_0"],
    "misc": ["athene-v2", "aya-expanse:8b-q4_K_S", "cogito", "command-r", "command-r7b:7b-12-2024-q4_K_M",
              "deepcoder", "dolphin3:8b-llama3.1-q4_K_M", "exaone3.5:7.8b-instruct-q4_K_M", "falcon",
              "falcon3:7b-instruct-q4_K_M", "glm4:9b-chat-q4_K_M", "hermes3:8b-llama3.1-q3_K_M",
              "internlm2:7b-chat-1m-v2.5-q4_K_M", "marco-o1:7b-q4_K_M", "mixtral", "nemotron",
              "nemotron-mini", "olmo2:7b-1124-instruct-q4_K_M", "openthinker:7b-q4_K_M", "qwen2.5:7b-instruct-q4_K_M",
              "qwq", "reflection", "sailor2:8b-chat-q4_K_M", "smallthinker:3b-preview-q8_0", "smollm2",
              "solar-pro", "tulu3:8b-q4_K_M", "vicuna", "wizardlm", "yi"]
}

# ─── LOGGING SETUP ─────────────────────────────────────────────
log_file = open(LOG_FILE, "w")


def log(msg):
    print(msg)
    log_file.write(msg + '\n')
    log_file.flush()


# ─── CHECKPOINTING ─────────────────────────────────────────────
def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r') as f:
            return set(json.load(f))
    return set()


def save_checkpoint(done_models):
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(sorted(list(done_models)), f, indent=2)


# ─── UTILS ─────────────────────────────────────────────────────
def extract_progress(text):
    match = re.search(r'(\d+)%', text)
    return int(match.group(1)) if match else None


def clean_model_name(name):
    name = name.lower()
    name = re.sub(r'[^\w\s-]', '-', name)
    name = re.sub(r'\s+', '_', name)
    return re.sub(r'-+', '-', name).strip('-_')


def is_model_manifest_present(model_name):
    base = clean_model_name(model_name)
    path = os.path.join(
        OLLAMA_MODELS_PATH,
        "manifests",
        "registry.ollama.ai",
        "library",
        base
    )
    return os.path.exists(path)


# ─── MODEL DOWNLOAD ────────────────────────────────────────────
def download_model(model_name, metadata_dict):
    start_time = time.time()
    log(f"\n🚀 Downloading: {model_name}")
    pbar = tqdm(total=100, desc=model_name, unit='%')
    process = subprocess.Popen([
        "ollama", "pull", model_name
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, bufsize=1)

    last_progress = 0
    last_activity = time.time()
    lines_captured = []

    for line in iter(process.stdout.readline, ''):
        log_file.write(line)
        lines_captured.append(line)
        progress = extract_progress(line)
        if progress and progress > last_progress:
            pbar.update(progress - last_progress)
            last_progress = progress
            last_activity = time.time()
        elif time.time() - last_activity > 300:
            log(f"⚠️  Timeout on {model_name}")
            break

    process.wait(timeout=30)
    pbar.update(100 - last_progress)
    pbar.close()

    end_time = time.time()
    metadata_dict[model_name] = {
        "download_time_sec": round(end_time - start_time, 2),
        "status": "success" if process.returncode == 0 else "failed",
        "progress": last_progress,
        "log_tail": lines_captured[-3:]  # Last 3 lines
    }


# ─── REPORTING ─────────────────────────────────────────────────
def write_metadata(metadata_dict):
    with open(METADATA_JSON, 'w') as f:
        json.dump(metadata_dict, f, indent=2)

    with open(METADATA_TXT, 'w') as f:
        for k, v in metadata_dict.items():
            f.write(f"{k}\n")
            for key, val in v.items():
                f.write(f"  {key}: {val}\n")
            f.write("\n")


# ─── MAIN EXECUTION ────────────────────────────────────────────
def main():
    done = load_checkpoint()
    metadata = {}

    all_models = [(vendor, model) for vendor, models in model_groups.items() for model in models]
    pending = [(v, m) for v, m in all_models if m not in done and not is_model_manifest_present(m)]

    log(f"✅ Models already downloaded: {len(done)}")
    log(f"📦 Models to download: {len(pending)}\n")

    def _wrapped_download(vendor_model):
        vendor, model = vendor_model
        download_model(model, metadata)
        done.add(model)
        save_checkpoint(done)
        return model

    if FLAG_CONCURRENT:
        with ThreadPoolExecutor(max_workers=CONCURRENT_MAX_DOWN) as executor:
            futures = {executor.submit(_wrapped_download, vm): vm for vm in pending}
            for f in as_completed(futures):
                try:
                    f.result()
                except Exception as e:
                    log(f"❌ Exception in thread: {e}")
    else:
        for vm in pending:
            _wrapped_download(vm)
            time.sleep(DELAY_BETWEEN_DOWNLOADS_SEC)

    write_metadata(metadata)
    log("\n🎉 All downloads complete.")
    log_file.close()


if __name__ == "__main__":
    main()