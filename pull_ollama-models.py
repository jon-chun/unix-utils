###CODE:
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
import sys # Import sys for exiting

# ─── CONFIGURATION ─────────────────────────────────────────────
# NOTE: Ensure this path is correct for your system AND that your Ollama server is configured to use it.
OLLAMA_MODELS_PATH = '/data/wdblue8tb/ollama'
# Basic check if path exists (optional, as Ollama server config is the source of truth now)
if not os.path.exists(OLLAMA_MODELS_PATH):
    print(f"⚠️ WARNING: OLLAMA_MODELS_PATH '{OLLAMA_MODELS_PATH}' does not exist. This script requires it for logging/metadata, but Ollama server configuration determines where models are stored/listed.")
    # No fallback here, as the script now relies on the server's view.

# Set environment variable for 'ollama pull' subprocesses (might be redundant if server is globally configured, but harmless)
os.environ['OLLAMA_MODELS'] = OLLAMA_MODELS_PATH

# File names for logging and reporting
LOG_FILE = f"ollama_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
METADATA_JSON = "model_metadata.json"
METADATA_TXT = "model_report.txt"
# SUSPICIOUS_LOG is no longer needed as is_model_download_complete is removed

FLAG_CONCURRENT = False # Set to True to enable concurrent downloads
CONCURRENT_MAX_DOWN = 2 # Max concurrent downloads if FLAG_CONCURRENT is True
DELAY_BETWEEN_DOWNLOADS_SEC = 5 # Delay only used when FLAG_CONCURRENT is False

# ─── MODEL LIST BY VENDOR ─────────────────────────────────────
# (Keep your existing model_groups dictionary here)
model_groups = {
    "llama": ["llama2", "llama3.1:8b-instruct-q4_K_M", "llama3.2:3b-instruct-q8_0", "llama3.2:3b-text-fp16", "llama3.3"],
    "gemma": ["gemma2", "gemma3:4b-it-q8_0"],
    "phi": [
        "phi3.5",
        "phi4",
        "phi4-mini:3.8b-q4_K_M",
        "phi4-mini:3.8b-q8_0",
        "phi4-reasoning:14b-plus-q4_K_M",
        "phi4-mini-reasoning:3.8b-q8_0"
    ],
    "deepseek": ["deepseek-r1:7b-qwen-distill-q4_K_M", "deepseek-r1:8b-llama-distill-q4_K_M"],
    "mistral": ["mistral:7b-instruct-q4_K_M", "mistral-small3.1"],
    "granite": [
        "granite3-dense:8b-instruct-q4_K_M",
        "granite3.1-dense:8b-instruct-q4_K_M",
        "granite3.1-moe:3b-instruct-q8_0",
        "granite3.2-vision:2b-fp16",
        "granite3.2-vision:2b-q8_0",
        "granite3.3",
        "granite3.3:2b",
        "granite3.3:8b"
     ],
    "qwen": [
        "qwen3:0.6b",
        "qwen3:1.7b",
        "qwen3:4b",
        "qwen3:8b-q4_K_M",
        "qwen3:14b-q4_K_M",
        "qwen3:32b-q4_K_M",
        "qwen3:30b-a3b"
    ],
    "misc": ["athene-v2", "aya-expanse:8b-q4_K_S", "cogito", "command-r", "command-r7b:7b-12-2024-q4_K_M",
              "deepcoder", "dolphin3:8b-llama3.1-q4_K_M", "exaone3.5:7.8b-instruct-q4_K_M", "falcon",
              "falcon3:7b-instruct-q4_K_M", "glm4:9b-chat-q4_K_M", "hermes3:8b-llama3.1-q3_K_M",
              "internlm2:7b-chat-1m-v2.5-q4_K_M", "marco-o1:7b-q4_K_M", "mixtral", "nemotron",
              "nemotron-mini", "olmo2:7b-1124-instruct-q4_K_M", "openthinker:7b-q4_K_M", "qwen2.5:7b-instruct-q4_K_M",
              "qwq", "reflection", "sailor2:8b-chat-q4_K_M", "smallthinker:3b-preview-q8_0", "smollm2",
              "solar-pro", "tulu3:8b-q4_K_M", "vicuna", "wizardlm", "yi"]
}

# ─── LOGGING SETUP ─────────────────────────────────────────────
log_file = None
try:
    log_file = open(LOG_FILE, "w", encoding='utf-8')
except IOError as e:
    print(f"🛑 ERROR: Cannot open log file: {e}")
    sys.exit(1) # Exit if logging isn't possible

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] {msg}"
    print(full_msg)
    if log_file:
        log_file.write(full_msg + '\n')
        log_file.flush() # Ensure messages are written immediately

# ─── OLLAMA INTERACTION ───────────────────────────────────────

def get_ollama_list_models():
    """
    Runs 'ollama list' and returns a set of installed model names.
    Exits script if 'ollama list' command fails.
    """
    installed_models = set()
    try:
        log("ℹ️ Querying Ollama server for installed models via 'ollama list'...")
        # Use subprocess.run for simpler execution and error handling
        result = subprocess.run(
            ['ollama', 'list'],
            capture_output=True,
            text=True,
            check=True, # Raises CalledProcessError if command returns non-zero exit code
            encoding='utf-8',
            errors='replace' # Handle potential encoding errors in output
        )

        lines = result.stdout.strip().split('\n')

        if len(lines) <= 1:
            log("ℹ️ 'ollama list' returned no installed models.")
            return installed_models # Return empty set

        # Skip header line (index 0)
        for line in lines[1:]:
            parts = line.split() # Split by whitespace
            if parts:
                model_name = parts[0] # First part is the model name
                installed_models.add(model_name)

        log(f"✅ Found {len(installed_models)} models installed according to 'ollama list'.")
        return installed_models

    except FileNotFoundError:
        log("🛑 ERROR: 'ollama' command not found. Make sure Ollama is installed and in your PATH.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        log(f"🛑 ERROR: 'ollama list' command failed with exit code {e.returncode}.")
        log(f"   Stderr: {e.stderr}")
        log(f"   Stdout: {e.stdout}")
        log("   Please ensure the Ollama server is running and accessible.")
        sys.exit(1)
    except Exception as e:
        log(f"🛑 ERROR: An unexpected error occurred while running 'ollama list': {e}")
        sys.exit(1)


# ─── UTILS ─────────────────────────────────────────────────────
def extract_progress(text):
    # (Keep existing extract_progress function)
    if "pulling" in text or "downloading" in text or "verifying" in text or "using" in text:
         match = re.search(r'(\d{1,3})\s?%', text)
         return int(match.group(1)) if match else None
    return None

# clean_model_name_for_path is no longer needed by core logic
# get_model_manifest_path is no longer needed by core logic
# is_model_download_complete is no longer needed by core logic

# ─── MODEL DOWNLOAD ────────────────────────────────────────────
def download_model(model_name, metadata_dict, current_index, total):
    # (Keep existing download_model function - it's mostly independent)
    start_time = time.time()
    log(f"\n🚀 ({current_index}/{total}) Starting download: {model_name}")
    pbar = tqdm(total=100, desc=f"{model_name[:30]:<30}", unit='%', leave=False)
    process = subprocess.Popen([
        "ollama", "pull", model_name
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', bufsize=8192)

    last_progress = 0
    last_activity = time.time()
    lines_captured = []
    hung_detector_timeout = 600

    try:
        for line in iter(process.stdout.readline, ''):
            if not line: break
            log_file.write(line)
            lines_captured.append(line.strip())
            progress = extract_progress(line)

            if progress is not None:
                update_amount = max(0, progress - last_progress)
                if update_amount > 0: pbar.update(update_amount)
                last_progress = progress
                last_activity = time.time()
            elif line.strip():
                 last_activity = time.time()

            if time.time() - last_activity > hung_detector_timeout:
                log(f"⚠️ No progress or output update in {hung_detector_timeout // 60} min for {model_name}. Terminating process.")
                process.terminate()
                time.sleep(5)
                if process.poll() is None:
                    log(f"⚠️ Process {model_name} did not terminate gracefully. Killing.")
                    process.kill()
                status = "timed_out"
                pbar.close()
                metadata_dict[model_name] = {
                    "download_time_sec": round(time.time() - start_time, 2), "status": status,
                    "progress": last_progress, "size_gb_estimate": "N/A",
                    "log_tail": lines_captured[-5:]
                }
                return model_name, status

        process.wait(timeout=60)
        pbar.n = 100
        pbar.refresh()
        status = "success" if process.returncode == 0 else f"failed (code: {process.returncode})"

    except subprocess.TimeoutExpired:
        log(f"⚠️ Process {model_name} exceeded wait timeout after stream closed. Killing.")
        process.kill()
        status = "failed (timeout_wait)"
    except Exception as e:
         log(f"❌ Unexpected error processing {model_name}: {e}")
         status = f"failed (exception: {e})"
         if process.poll() is None: process.kill()
    finally:
         if process.stdout: process.stdout.close()
         if not pbar.disable:
            if "success" in status and pbar.n < 100: pbar.update(100 - pbar.n)
            pbar.close()

    end_time = time.time()
    size_gb = "N/A"
    try:
        blobs_dir = os.path.join(OLLAMA_MODELS_PATH, "blobs")
        if os.path.exists(blobs_dir):
            total_size_bytes = sum(f.stat().st_size for f in os.scandir(blobs_dir) if f.is_file())
            size_gb = round(total_size_bytes / (1024 ** 3), 2)
        else: size_gb = 0
    except Exception as e:
        log(f"⚠️ Could not estimate blob directory size: {e}")
        size_gb = "Error"

    if status == "success": final_message = f"✅ Finished {model_name} successfully."
    elif status == "timed_out": final_message = f"⏰ Timed out downloading {model_name} after {round(end_time - start_time)}s."
    else: final_message = f"❌ Finished {model_name} with status: {status}."

    log(f"{final_message} | Total blob size: ~{size_gb} GB")

    metadata_dict[model_name] = {
        "download_time_sec": round(end_time - start_time, 2), "status": status,
        "final_progress_%": last_progress if status != 'success' else 100,
        "total_blob_size_gb": size_gb, "log_tail": lines_captured[-5:]
    }
    time.sleep(1)
    return model_name, status

# ─── REPORTING ─────────────────────────────────────────────────
def write_metadata(metadata_dict):
    # (Keep existing write_metadata function)
    log("\n📊 Generating reports...")
    try:
        with open(METADATA_JSON, 'w', encoding='utf-8') as f:
            json.dump(metadata_dict, f, indent=2, sort_keys=True)
        log(f"📄 JSON metadata saved to {METADATA_JSON}")
    except IOError as e: log(f"⚠️ Error writing JSON metadata: {e}")

    try:
        with open(METADATA_TXT, 'w', encoding='utf-8') as f:
            f.write(f"Ollama Model Download Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=====================================================\n\n")
            success_count, failed_count, timed_out_count = 0, 0, 0
            for model, data in sorted(metadata_dict.items()):
                f.write(f"Model: {model}\n")
                status = data.get('status', 'unknown')
                f.write(f"  Status: {status}\n")
                f.write(f"  Download Time (sec): {data.get('download_time_sec', 'N/A')}\n")
                f.write(f"  Final Progress (%): {data.get('final_progress_%', 'N/A')}\n")
                f.write(f"  Estimated Total Blob Size (GB): {data.get('total_blob_size_gb', 'N/A')}\n")
                f.write("  Log Tail:\n")
                for line in data.get('log_tail', []): f.write(f"    {line}\n")
                f.write("-" * 50 + "\n\n")
                if status == "success": success_count += 1
                elif status == "timed_out": timed_out_count += 1
                else: failed_count += 1
            f.write("=====================================================\nSummary:\n")
            f.write(f"  Successful: {success_count}\n  Failed:     {failed_count}\n  Timed Out:  {timed_out_count}\n")
            f.write(f"  Total Attempts This Run: {len(metadata_dict)}\n=====================================================\n")
        log(f"📄 Text report saved to {METADATA_TXT}")
    except IOError as e: log(f"⚠️ Error writing text report: {e}")

# ─── MAIN EXECUTION ────────────────────────────────────────────
def main(force_all=False, run_concurrent=FLAG_CONCURRENT):
    global log_file # Allow modification if closed early

    attempted_this_run = set()
    metadata = {} # Stores metadata for models attempted in *this* run

    try:
        # Get the list of currently installed models directly from Ollama
        installed_models = get_ollama_list_models()

        all_models_flat = [(vendor, model) for vendor, models in model_groups.items() for model in models]
        pending = []

        log("🔍 Checking required models against 'ollama list' output...")
        for v, m in tqdm(all_models_flat, desc="Checking models"):
            attempted_this_run.add(m) # Track all models we intend to process

            # Core logic change: Check against 'ollama list' output
            if m in installed_models and not force_all:
                log(f"⏩ '{m}' found via 'ollama list' — skipping.")
                continue # Skip adding to pending list
            else:
                # Determine reason for queuing
                if force_all:
                   log(f"➕ Queuing '{m}' for download (forced).")
                elif m not in installed_models:
                    log(f"➕ Queuing '{m}' for download ('ollama list' did not find it).")
                # Add to pending list
                pending.append((v, m))

        total_to_download = len(pending)
        log(f"\n✅ Models already present according to 'ollama list': {len(installed_models)}")
        log(f"📦 Models queued for download in this run: {total_to_download}\n")

        if not pending:
            log("🏁 No models need downloading.")
            # Still generate reports for consistency, even if empty
            write_metadata(metadata)
            return # Exit early if nothing to do

        # --- Download Execution ---
        # Note: Checkpointing is removed. If the script is interrupted,
        # it will rely on 'ollama list' on the next run to see what finished.
        downloaded_this_run = set() # Track successes within this run for reporting

        def _wrapped_download(vendor_model, index, total):
            _, model = vendor_model
            model_name_result, status = download_model(model, metadata, index, total)
            if status == "success":
                downloaded_this_run.add(model_name_result)
            # Return model name regardless of status for tracking
            return model_name_result

        # (Concurrent/Sequential download execution logic remains the same)
        if run_concurrent:
            log(f"🚀 Starting concurrent downloads (max workers: {CONCURRENT_MAX_DOWN})...")
            with ThreadPoolExecutor(max_workers=CONCURRENT_MAX_DOWN) as executor:
                futures = {executor.submit(_wrapped_download, vm, idx + 1, total_to_download): vm for idx, vm in enumerate(pending)}
                for future in tqdm(as_completed(futures), total=total_to_download, desc="Overall Progress"):
                    vm = futures[future]
                    model_name = vm[1]
                    try:
                        future.result()
                    except Exception as exc:
                        log(f"❌ Exception occurred for model '{model_name}': {exc}")
                        if model_name not in metadata:
                             metadata[model_name] = {"status": f"failed (executor exception: {exc})"}
        else:
            log(f"🚀 Starting sequential downloads (delay: {DELAY_BETWEEN_DOWNLOADS_SEC}s)...")
            for idx, vm in enumerate(pending):
                model_name = vm[1]
                try:
                    _wrapped_download(vm, idx + 1, total_to_download)
                except Exception as exc:
                     log(f"❌ Exception occurred for model '{model_name}': {exc}")
                     if model_name not in metadata:
                         metadata[model_name] = {"status": f"failed (loop exception: {exc})"}
                if idx < total_to_download - 1:
                    log(f"⏳ Pausing for {DELAY_BETWEEN_DOWNLOADS_SEC} seconds...")
                    time.sleep(DELAY_BETWEEN_DOWNLOADS_SEC)

        log("\n🎉 All download tasks processed.")

    except Exception as e:
        log(f" CRITICAL ERROR in main execution loop: {e}")
        import traceback
        log(traceback.format_exc())
    finally:
        # --- Reporting and Cleanup ---
        # Write reports based on attempts during this run
        write_metadata(metadata)

        # No final checkpoint save needed
        # Optionally, run ollama list again to show final state
        log("\n🏁 Script finished. Running final 'ollama list' check:")
        try:
            final_installed_models = get_ollama_list_models()
            log(f"Final count from 'ollama list': {len(final_installed_models)}")
        except Exception:
             log("⚠️ Could not run final 'ollama list'.")


        # Close log file
        if log_file:
            log_file.close()
            log_file = None # Prevent further writes
        # No suspicious log to close
        print("\nScript finished.") # Print to console after logs are closed


if __name__ == "__main__":
    # Update description to reflect new logic
    parser = argparse.ArgumentParser(description="Pull Ollama models, checking status via 'ollama list' and generating metadata.")
    parser.add_argument("--force", action="store_true", help="Force download attempt of all models, ignoring 'ollama list' results.")
    parser.add_argument("--concurrent", action="store_true", default=FLAG_CONCURRENT, help=f"Enable concurrent downloads (up to {CONCURRENT_MAX_DOWN}). Overrides FLAG_CONCURRENT setting.")
    parser.add_argument("--workers", type=int, default=CONCURRENT_MAX_DOWN, help="Set the number of concurrent download workers if --concurrent is used.")

    args = parser.parse_args()

    run_concurrent_flag = args.concurrent
    if run_concurrent_flag:
       CONCURRENT_MAX_DOWN = args.workers

    main(force_all=args.force, run_concurrent=run_concurrent_flag)