import os
import subprocess
import time
import re
import json
from tqdm import tqdm
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import argparse

# ─── CONFIGURATION ─────────────────────────────────────────────
OLLAMA_MODELS_PATH = '/data/wdblue8tb/ollama'
os.environ['OLLAMA_MODELS'] = OLLAMA_MODELS_PATH
CHECKPOINT_FILE = "downloaded_models.json"
LOG_FILE = f"ollama_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
METADATA_JSON = "model_metadata.json"
METADATA_TXT = "model_report.txt"
SUSPICIOUS_LOG = "skipped_but_suspicious.txt"

FLAG_CONCURRENT = False
CONCURRENT_MAX_DOWN = 2
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
suspicious_log = open(SUSPICIOUS_LOG, "w")

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] {msg}"
    print(full_msg)
    log_file.write(full_msg + '\n')
    log_file.flush()

def log_suspicious(msg):
    suspicious_log.write(msg + '\n')
    suspicious_log.flush()

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

def is_model_manifest_complete(model_name):
    base = clean_model_name(model_name)
    manifest_path = os.path.join(
        OLLAMA_MODELS_PATH,
        "manifests",
        "registry.ollama.ai",
        "library",
        base
    )
    if not os.path.isdir(manifest_path) or not os.listdir(manifest_path):
        return False

    blobs_dir = os.path.join(OLLAMA_MODELS_PATH, "blobs")
    if not os.path.isdir(blobs_dir):
        return False

    for f in os.listdir(blobs_dir):
        try:
            size = os.path.getsize(os.path.join(blobs_dir, f))
            if size > 100 * 1024 * 1024:
                return True
        except Exception:
            continue

    log_suspicious(f"⚠️ Suspect incomplete: {model_name} — manifest present but blobs missing or tiny.")
    return False

# ─── MODEL DOWNLOAD ────────────────────────────────────────────
def download_model(model_name, metadata_dict, current_index, total):
    start_time = time.time()
    log(f"\n🚀 ({current_index}/{total}) Starting download: {model_name}")
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
            log(f"⚠️  No progress in 5 min for {model_name}, exiting early.")
            break

    process.wait(timeout=30)
    pbar.update(100 - last_progress)
    pbar.close()

    end_time = time.time()
    status = "success" if process.returncode == 0 else "failed"

    model_dir = os.path.join(OLLAMA_MODELS_PATH, "blobs")
    size = 0
    if os.path.exists(model_dir):
        size = sum(os.path.getsize(os.path.join(model_dir, f)) for f in os.listdir(model_dir) if os.path.isfile(os.path.join(model_dir, f)))

    log(f"✅ Finished {model_name} with status: {status} and downloaded size: {round(size / (1024 ** 3), 2)} GB")

    metadata_dict[model_name] = {
        "download_time_sec": round(end_time - start_time, 2),
        "status": status,
        "progress": last_progress,
        "size_gb_estimate": round(size / (1024 ** 3), 2),
        "log_tail": lines_captured[-3:]
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
def main(force_all=False):
    done = load_checkpoint()
    metadata = {}
    all_models = [(vendor, model) for vendor, models in model_groups.items() for model in models]
    pending = []

    for v, m in all_models:
        if force_all:
            pending.append((v, m))
        elif m in done:
            log(f"⏩ {m} is in checkpoint — skipping.")
        elif is_model_manifest_complete(m):
            log(f"⏩ {m} has complete manifest and blob — skipping.")
        else:
            pending.append((v, m))

    log(f"✅ Already downloaded: {len(done)} models")
    log(f"📦 Models to download: {len(pending)}\n")

    def _wrapped_download(vendor_model, index, total):
        vendor, model = vendor_model
        download_model(model, metadata, index, total)
        done.add(model)
        save_checkpoint(done)
        return model

    total = len(pending)
    if FLAG_CONCURRENT:
        with ThreadPoolExecutor(max_workers=CONCURRENT_MAX_DOWN) as executor:
            futures = {executor.submit(_wrapped_download, vm, idx + 1, total): vm for idx, vm in enumerate(pending)}
            for f in as_completed(futures):
                try:
                    f.result()
                except Exception as e:
                    log(f"❌ Exception in thread: {e}")
    else:
        for idx, vm in enumerate(pending):
            _wrapped_download(vm, idx + 1, total)
            time.sleep(DELAY_BETWEEN_DOWNLOADS_SEC)

    write_metadata(metadata)
    log("\n🎉 All downloads complete.")
    log_file.close()
    suspicious_log.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pull Ollama models with checkpointing and metadata.")
    parser.add_argument("--force", action="store_true", help="Force redownload of all models, skip checkpoint/manifest checks")
    args = parser.parse_args()
    main(force_all=args.force)
