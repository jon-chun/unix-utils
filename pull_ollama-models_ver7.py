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

# ─── CONFIGURATION ─────────────────────────────────────────────
# NOTE: Ensure this path is correct for your system
OLLAMA_MODELS_PATH = '/data/wdblue8tb/ollama'
# Check if the path exists, provide a fallback or warning if not
if not os.path.exists(OLLAMA_MODELS_PATH):
    print(f"⚠️ WARNING: OLLAMA_MODELS_PATH '{OLLAMA_MODELS_PATH}' does not exist. Using default.")
    # Attempt to find the default Ollama path or use a placeholder
    default_path = os.path.expanduser("~/.ollama/models")
    if os.path.exists(default_path):
         OLLAMA_MODELS_PATH = default_path
         print(f"✅ Found default Ollama path: {OLLAMA_MODELS_PATH}")
    else:
        # If you know the typical default on other systems, add checks here
        # As a last resort, use a relative path or stop execution
        print(f"🛑 ERROR: Default Ollama path '{default_path}' not found either. Please set OLLAMA_MODELS_PATH correctly.")
        # Depending on requirements, you might exit here:
        # exit(1)
        # Or use a potentially incorrect path, which might cause issues later:
        OLLAMA_MODELS_PATH = './ollama_models' # Example fallback
        print(f"⚠️ Using fallback path: {OLLAMA_MODELS_PATH}. Downloads might fail if Ollama isn't configured for this.")
        os.makedirs(OLLAMA_MODELS_PATH, exist_ok=True) # Create if it doesn't exist


os.environ['OLLAMA_MODELS'] = OLLAMA_MODELS_PATH
CHECKPOINT_FILE = "downloaded_models.json"
LOG_FILE = f"ollama_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log" # Changed extension to .log
METADATA_JSON = "model_metadata.json"
METADATA_TXT = "model_report.txt"
SUSPICIOUS_LOG = "skipped_but_suspicious.log" # Changed extension to .log

FLAG_CONCURRENT = False # Set to True to enable concurrent downloads
CONCURRENT_MAX_DOWN = 2 # Max concurrent downloads if FLAG_CONCURRENT is True
DELAY_BETWEEN_DOWNLOADS_SEC = 5 # Delay only used when FLAG_CONCURRENT is False

# ─── MODEL LIST BY VENDOR ─────────────────────────────────────
model_groups = {
    "llama": ["llama2", "llama3.1:8b-instruct-q4_K_M", "llama3.2:3b-instruct-q8_0", "llama3.2:3b-text-fp16", "llama3.3"],
    "gemma": ["gemma2", "gemma3:4b-it-q8_0"],
    "phi": [
        "phi3.5",
        "phi4",
        "phi4-mini:3.8b-q4_K_M",
        "phi4-mini:3.8b-q8_0",
        # --- NEW Microsoft Models ---
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
        # --- NEW IBM Models ---
        "granite3.3",
        "granite3.3:2b",
        "granite3.3:8b"
     ],
    # --- NEW Qwen Group ---
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
# Ensure log files are closed properly if script exits early
log_file = None
suspicious_log = None
try:
    log_file = open(LOG_FILE, "w", encoding='utf-8')
    suspicious_log = open(SUSPICIOUS_LOG, "w", encoding='utf-8')
except IOError as e:
    print(f"🛑 ERROR: Cannot open log file: {e}")
    exit(1) # Exit if logging isn't possible

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] {msg}"
    print(full_msg)
    if log_file:
        log_file.write(full_msg + '\n')
        log_file.flush() # Ensure messages are written immediately

def log_suspicious(msg):
    if suspicious_log:
        suspicious_log.write(msg + '\n')
        suspicious_log.flush()

# ─── CHECKPOINTING ─────────────────────────────────────────────
def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content.strip(): # Handle empty file
                    return set()
                return set(json.loads(content))
        except json.JSONDecodeError:
            log(f"⚠️ Checkpoint file {CHECKPOINT_FILE} is corrupted. Starting fresh.")
            return set()
        except IOError as e:
            log(f"⚠️ Error reading checkpoint file {CHECKPOINT_FILE}: {e}. Starting fresh.")
            return set()
    return set()

def save_checkpoint(done_models):
    try:
        with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
            json.dump(sorted(list(done_models)), f, indent=2)
    except IOError as e:
        log(f"⚠️ Error writing checkpoint file {CHECKPOINT_FILE}: {e}")


# ─── UTILS ─────────────────────────────────────────────────────
def extract_progress(text):
    # Improved regex to handle potential variations and ensure it's a progress line
    # Look for patterns like 'pulling manifest', 'downloading...', '[=> ]', 'verifying sha256' etc.
    # and a percentage value.
    if "pulling" in text or "downloading" in text or "verifying" in text or "using" in text:
         match = re.search(r'(\d{1,3})\s?%', text)
         return int(match.group(1)) if match else None
    return None # Return None if it doesn't look like a progress line

def clean_model_name_for_path(name):
    """Cleans the model name specifically for creating filesystem paths."""
    # Replace ':' with a safe separator like '__'
    name = name.replace(':', '__')
    # Keep alphanumeric, underscore, hyphen, and the new '__' separator
    name = re.sub(r'[^\w\-\.]', '_', name) # Allow dots as well
    # Replace multiple underscores/hyphens with a single one
    name = re.sub(r'[_]+', '_', name)
    name = re.sub(r'[-]+', '-', name)
    return name.strip('-_')

def get_model_manifest_path(model_name):
    """Constructs the expected manifest directory path for a given model."""
    # Ollama typically stores manifests under library/<model_base_name>/<tag>
    # Example: llama3:8b -> library/llama3/8b
    # Example: phi4-mini:3.8b-q8_0 -> library/phi4-mini/3.8b-q8_0
    parts = model_name.split(':', 1)
    base_name = parts[0]
    tag = parts[1] if len(parts) > 1 else 'latest' # Default tag is 'latest'

    # Clean the base name and tag for path construction if necessary,
    # but Ollama might use the raw names directly in the path.
    # Let's assume Ollama handles potentially problematic characters.
    # We only need this for checking existence.
    manifest_dir = os.path.join(
        OLLAMA_MODELS_PATH,
        "manifests",
        "registry.ollama.ai",
        "library",
        base_name,
        tag # Check for the specific tag directory
    )
    return manifest_dir


def is_model_download_complete(model_name):
    """Checks if a model's manifest exists and associated blobs seem present."""
    manifest_dir = get_model_manifest_path(model_name)

    if not os.path.isdir(manifest_dir):
        # log(f"Debug: Manifest dir not found for {model_name} at {manifest_dir}")
        return False

    # Check if the main manifest file exists within the tag directory
    # Ollama manifest files often don't have an extension or might be named like the tag
    # Let's just check if the directory is non-empty for simplicity,
    # A more robust check would involve parsing the manifest content.
    if not os.listdir(manifest_dir):
         # log(f"Debug: Manifest dir is empty for {model_name} at {manifest_dir}")
        return False

    # Simple blob check: Look for *any* large file in the main blobs directory.
    # This is a heuristic and not foolproof. A better check would involve
    # reading the manifest, finding the required blob shas, and checking
    # if those specific blobs exist.
    blobs_dir = os.path.join(OLLAMA_MODELS_PATH, "blobs")
    if not os.path.isdir(blobs_dir):
        # This would be unusual if manifests exist, but check anyway
        log_suspicious(f"⚠️ Suspicious: Manifest dir exists for {model_name} but blobs directory '{blobs_dir}' is missing.")
        return False

    try:
        # Check if there's at least one reasonably sized blob file
        # Adjust the size threshold as needed (e.g., 10MB)
        min_blob_size = 10 * 1024 * 1024
        found_large_blob = False
        for entry in os.scandir(blobs_dir):
             # Blobs are typically named like 'sha256-...'
             if entry.is_file() and entry.name.startswith('sha256-'):
                try:
                    if entry.stat().st_size >= min_blob_size:
                        found_large_blob = True
                        break
                except OSError:
                    # File might be temporarily unavailable or removed
                    continue
        if not found_large_blob:
             log_suspicious(f"⚠️ Suspicious: Manifest exists for {model_name}, but no large blobs found in {blobs_dir}.")
             return False # Treat as incomplete if no significant blobs are found

    except OSError as e:
        log_suspicious(f"⚠️ Error accessing blobs directory {blobs_dir} for {model_name}: {e}")
        return False # Cannot verify blobs, assume incomplete

    # If manifest dir exists, is not empty, and at least one large blob exists,
    # assume it's likely complete enough to skip.
    return True

# ─── MODEL DOWNLOAD ────────────────────────────────────────────
def download_model(model_name, metadata_dict, current_index, total):
    start_time = time.time()
    log(f"\n🚀 ({current_index}/{total}) Starting download: {model_name}")
    # Use a persistent tqdm bar
    pbar = tqdm(total=100, desc=f"{model_name[:30]:<30}", unit='%', leave=False) # Keep bar after completion temporarily
    # Increased buffer size might help with faster output processing
    process = subprocess.Popen([
        "ollama", "pull", model_name
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', bufsize=8192)

    last_progress = 0
    last_activity = time.time()
    lines_captured = []
    hung_detector_timeout = 600 # 10 minutes of no progress or output

    try:
        for line in iter(process.stdout.readline, ''):
            if not line: # End of stream
                 break
            log_file.write(line) # Log everything
            lines_captured.append(line.strip())
            progress = extract_progress(line)

            if progress is not None: # Only update if extract_progress returns a number
                # Ensure progress doesn't go backwards (can happen with multi-part downloads)
                # Only update the visual bar for forward progress
                update_amount = max(0, progress - last_progress)
                if update_amount > 0:
                   pbar.update(update_amount)
                last_progress = progress # Always store the latest reported percentage
                last_activity = time.time() # Reset activity timer on progress update
            elif line.strip(): # Check if the line has content
                 # Reset activity timer even on non-progress output lines
                 last_activity = time.time()


            # Check for stall
            if time.time() - last_activity > hung_detector_timeout:
                log(f"⚠️ No progress or output update in {hung_detector_timeout // 60} min for {model_name}. Terminating process.")
                process.terminate() # Try graceful termination
                time.sleep(5) # Give it time to terminate
                if process.poll() is None: # Check if it's still running
                    log(f"⚠️ Process {model_name} did not terminate gracefully. Killing.")
                    process.kill() # Force kill
                status = "timed_out"
                pbar.close() # Close the progress bar on timeout
                metadata_dict[model_name] = {
                    "download_time_sec": round(time.time() - start_time, 2),
                    "status": status,
                    "progress": last_progress,
                    "size_gb_estimate": "N/A", # Unknown size on timeout
                    "log_tail": lines_captured[-5:] # Log last few lines for context
                }
                return model_name, status # Return status

        # Process finished reading output, wait for it to exit
        process.wait(timeout=60) # Wait up to 60 seconds for cleanup
        pbar.n = 100 # Ensure bar visually completes
        pbar.refresh()
        status = "success" if process.returncode == 0 else f"failed (code: {process.returncode})"

    except subprocess.TimeoutExpired:
        log(f"⚠️ Process {model_name} exceeded wait timeout after stream closed. Killing.")
        process.kill()
        status = "failed (timeout_wait)"
    except Exception as e:
         log(f"❌ Unexpected error processing {model_name}: {e}")
         status = f"failed (exception: {e})"
         if process.poll() is None: # Check if process still running after exception
             process.kill()
    finally:
         # Ensure stdout is closed if open
         if process.stdout:
             process.stdout.close()
         # Ensure pbar is closed if it hasn't been
         if not pbar.disable: # Check if pbar might already be closed
            # If status indicates success but progress bar isn't full, force it
            if "success" in status and pbar.n < 100:
                pbar.update(100 - pbar.n)
            pbar.close() # Close the bar


    end_time = time.time()
    size_gb = "N/A" # Default size

    # Try to estimate size based on blobs *after* download attempt
    # This is still a very rough estimate of the *total* blob store size,
    # not the size of the specific model downloaded.
    try:
        blobs_dir = os.path.join(OLLAMA_MODELS_PATH, "blobs")
        if os.path.exists(blobs_dir):
            total_size_bytes = sum(f.stat().st_size for f in os.scandir(blobs_dir) if f.is_file())
            size_gb = round(total_size_bytes / (1024 ** 3), 2)
        else:
            size_gb = 0 # Blobs dir doesn't exist
    except Exception as e:
        log(f"⚠️ Could not estimate blob directory size: {e}")
        size_gb = "Error"

    # Determine final status message more accurately
    if status == "success":
         final_message = f"✅ Finished {model_name} successfully."
    elif status == "timed_out":
         final_message = f"⏰ Timed out downloading {model_name} after {round(end_time - start_time)}s."
    else:
         final_message = f"❌ Finished {model_name} with status: {status}."

    log(f"{final_message} | Total blob size: ~{size_gb} GB")

    metadata_dict[model_name] = {
        "download_time_sec": round(end_time - start_time, 2),
        "status": status,
        "final_progress_%": last_progress if status != 'success' else 100, # Record last known progress if failed/timed out
        "total_blob_size_gb": size_gb,
        "log_tail": lines_captured[-5:] # Log more lines
    }
    # Add a small delay before the next one starts, especially after failures
    time.sleep(1)
    return model_name, status

# ─── REPORTING ─────────────────────────────────────────────────
def write_metadata(metadata_dict):
    log("\n📊 Generating reports...")
    try:
        with open(METADATA_JSON, 'w', encoding='utf-8') as f:
            json.dump(metadata_dict, f, indent=2, sort_keys=True)
        log(f"📄 JSON metadata saved to {METADATA_JSON}")
    except IOError as e:
        log(f"⚠️ Error writing JSON metadata: {e}")

    try:
        with open(METADATA_TXT, 'w', encoding='utf-8') as f:
            f.write(f"Ollama Model Download Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=====================================================\n\n")
            success_count = 0
            failed_count = 0
            timed_out_count = 0

            for model, data in sorted(metadata_dict.items()):
                f.write(f"Model: {model}\n")
                status = data.get('status', 'unknown')
                f.write(f"  Status: {status}\n")
                f.write(f"  Download Time (sec): {data.get('download_time_sec', 'N/A')}\n")
                f.write(f"  Final Progress (%): {data.get('final_progress_%', 'N/A')}\n")
                f.write(f"  Estimated Total Blob Size (GB): {data.get('total_blob_size_gb', 'N/A')}\n")
                f.write("  Log Tail:\n")
                for line in data.get('log_tail', []):
                    f.write(f"    {line}\n")
                f.write("-" * 50 + "\n\n")

                if status == "success":
                    success_count += 1
                elif status == "timed_out":
                    timed_out_count += 1
                else: # Any other non-success status counts as failed
                    failed_count += 1

            f.write("=====================================================\n")
            f.write("Summary:\n")
            f.write(f"  Successful: {success_count}\n")
            f.write(f"  Failed:     {failed_count}\n")
            f.write(f"  Timed Out:  {timed_out_count}\n")
            f.write(f"  Total Attempts: {len(metadata_dict)}\n")
            f.write("=====================================================\n")
        log(f"📄 Text report saved to {METADATA_TXT}")
    except IOError as e:
        log(f"⚠️ Error writing text report: {e}")


# ─── MAIN EXECUTION ────────────────────────────────────────────
def main(force_all=False, run_concurrent=FLAG_CONCURRENT):
    global log_file, suspicious_log # Allow modification if closed early

    downloaded_this_run = set()
    attempted_this_run = set()
    metadata = {} # Stores metadata for models attempted in *this* run

    try:
        done_previously = load_checkpoint()
        all_models_flat = [(vendor, model) for vendor, models in model_groups.items() for model in models]
        pending = []

        log("🔍 Checking model status...")
        for v, m in tqdm(all_models_flat, desc="Checking models"):
            attempted_this_run.add(m) # Track all models we intend to process
            if m in done_previously and not force_all:
                log(f"⏩ '{m}' found in checkpoint — skipping.")
                continue # Skip adding to pending list
            elif is_model_download_complete(m) and not force_all:
                log(f"⏩ '{m}' appears complete (manifest/blobs found) — skipping.")
                done_previously.add(m) # Add to checkpoint if found complete but not in checkpoint yet
                continue
            else:
                if force_all:
                   log(f"➕ Queuing '{m}' for download (forced).")
                elif m not in done_previously:
                    log(f"➕ Queuing '{m}' for download (not in checkpoint).")
                else: # This case should ideally not be hit if is_model_download_complete was True
                    log(f"➕ Queuing '{m}' for download (in checkpoint but check failed or forced).")
                pending.append((v, m))

        # Save checkpoint immediately after checks, in case is_model_download_complete added models
        save_checkpoint(done_previously)

        total_to_download = len(pending)
        log(f"\n✅ Models previously completed: {len(done_previously)}")
        log(f"📦 Models queued for download in this run: {total_to_download}\n")

        if not pending:
            log("🏁 No models need downloading.")
            return # Exit early if nothing to do

        # --- Download Execution ---
        current_done_set = done_previously.copy() # Use a copy for this run's checkpointing

        def _wrapped_download(vendor_model, index, total):
            _, model = vendor_model
            model_name_result, status = download_model(model, metadata, index, total)
            if status == "success":
                downloaded_this_run.add(model_name_result)
                current_done_set.add(model_name_result) # Add successfully downloaded model to the set
                save_checkpoint(current_done_set) # Update checkpoint after each success
            # Return model name regardless of status for tracking
            return model_name_result


        if run_concurrent:
            log(f"🚀 Starting concurrent downloads (max workers: {CONCURRENT_MAX_DOWN})...")
            with ThreadPoolExecutor(max_workers=CONCURRENT_MAX_DOWN) as executor:
                futures = {executor.submit(_wrapped_download, vm, idx + 1, total_to_download): vm for idx, vm in enumerate(pending)}
                for future in tqdm(as_completed(futures), total=total_to_download, desc="Overall Progress"):
                    vm = futures[future] # Get the original (vendor, model) tuple
                    model_name = vm[1]
                    try:
                        # Result already handled inside _wrapped_download
                        future.result()
                    except Exception as exc:
                        log(f"❌ Exception occurred for model '{model_name}': {exc}")
                        # Record failure in metadata if not already done by download_model
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
                # Add delay only if not the last model and concurrent flag is off
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
        if metadata: # Write reports only if downloads were attempted
             write_metadata(metadata)
        else:
             log("ℹ️ No new download attempts were made, skipping report generation.")

        # Final Checkpoint Save (includes models completed in this run)
        final_checkpoint_set = load_checkpoint() # Reload potentially updated checkpoint
        final_checkpoint_set.update(downloaded_this_run) # Add successful downloads from this run
        save_checkpoint(final_checkpoint_set)
        log(f"💾 Final checkpoint saved. Total completed models: {len(final_checkpoint_set)}")

        # Close log files
        if log_file:
            log_file.close()
            log_file = None # Prevent further writes
        if suspicious_log:
            suspicious_log.close()
            suspicious_log = None
        print("\nScript finished.") # Print to console after logs are closed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pull Ollama models with checkpointing, metadata, and improved robustness.")
    parser.add_argument("--force", action="store_true", help="Force redownload attempt of all models, ignoring checkpoints and existing manifests/blobs.")
    parser.add_argument("--concurrent", action="store_true", default=FLAG_CONCURRENT, help=f"Enable concurrent downloads (up to {CONCURRENT_MAX_DOWN}). Overrides FLAG_CONCURRENT setting.")
    parser.add_argument("--workers", type=int, default=CONCURRENT_MAX_DOWN, help="Set the number of concurrent download workers if --concurrent is used.")

    args = parser.parse_args()

    # Update config based on args
    run_concurrent_flag = args.concurrent
    if run_concurrent_flag:
       CONCURRENT_MAX_DOWN = args.workers # Allow overriding max workers via CLI

    main(force_all=args.force, run_concurrent=run_concurrent_flag)