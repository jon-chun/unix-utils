import subprocess
import time
import re
from tqdm import tqdm
from datetime import datetime

import os
os.environ['OLLAMA_MODELS'] = '/data/wdblue8tb/ollama'

log_file = open(f"ollama_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", "w")

# log_file.write(line)


# List of models to download
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


# Delay between downloads in seconds
DELAY_BETWEEN_DOWNLOADS_SEC = 5

def clean_model_name(name: str) -> str:
    """
    Converts a model name into an OS-safe alias.
    Rules:
      - Lowercase all characters.
      - Keep only alphanumeric, '_' and '-' characters.
      - Replace punctuation (like '.', ':', etc.) with a single dash.
      - Collapse consecutive whitespaces into a single underscore.
    """
    name = name.lower()
    # Replace any character that is not alphanumeric, whitespace, underscore, or dash with a dash.
    name = re.sub(r'[^\w\s-]', '-', name)
    # Collapse consecutive whitespace into an underscore
    name = re.sub(r'\s+', '_', name)
    # Collapse multiple dashes into a single dash
    name = re.sub(r'-+', '-', name)
    return name.strip('-_')

def get_downloaded_models() -> list:
    """
    Runs 'ollama list', parses the output, and returns a list of downloaded model names.
    Assumes the first column in each non-header line is the model name.
    """
    try:
        process = subprocess.Popen(
            ["ollama", "list"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        stdout, stderr = process.communicate()
        if process.returncode != 0:
            print(f"Error running 'ollama list': {stderr.strip()}")
            return []
        lines = stdout.strip().splitlines()
        downloaded = []
        # Skip header (assume first line is header)
        for line in lines[1:]:
            parts = line.split()
            if parts:
                downloaded.append(parts[0])
        return downloaded
    except Exception as e:
        print(f"An error occurred while listing models: {e}")
        return []

def extract_progress(text):
    """
    Extracts the first integer percentage found in the text.
    For example, from "45%" returns 45.
    """
    match = re.search(r'(\d+)%', text)
    if match:
        return int(match.group(1))
    return None

def download_model(model_name, timeout=3600):  # Default timeout of 1 hour
    alias = clean_model_name(model_name)
    try:
        start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{start_time}] Starting download: {model_name} (alias: {alias})")
        
        # Create progress bar
        pbar = tqdm(total=100, desc=f"Downloading {alias}", unit='%')
        
        # Start the process
        process = subprocess.Popen(model_ls = [
    "athene-v2:72b-q4_K_M",
    "aya-expanse:8b-q4_K_S",
    "cogito:8b-v1-preview-llama-q4_K_M",
    "cogito:14b-v1-preview-qwen-q4_K_M",
    "cogito:32b-v1-preview-qwen-q4_K_M",
    "command-r7b:7b-12-2024-q4_K_M",
    "deepcoder:14b-preview-q4_K_M",
    "deepseek-r1:7b-qwen-distill-q4_K_M",
    "deepseek-r1:8b-llama-distill-q4_K_M",
    "dolphin3:8b-llama3.1-q4_K_M",
    "exaone3.5:7.8b-instruct-q4_K_M",
    "exaone-deep:7.8b-q4_K_M",
    "exaone-deep:32b-q4_K_M",
    "falcon3:10b-instruct-q4_K_M",
    "falcon3:7b-instruct-q4_K_M",
    "gemma2:9b-instruct-q5_K_M",
    "gemma2:27b-instruct-q4_K_M",
    "gemma3:4b-it-q8_0",
    "gemma3:12b-it-q4_K_M",
    "gemma3:27b-it-q4_K_M",
    "glm4:9b-chat-q4_K_M",
    "granite3-dense:8b-instruct-q4_K_M",
    "granite3.1-dense:8b-instruct-q4_K_M",
    "granite3.1-moe:3b-instruct-q8_0",
    "granite3.2-vision:2b-fp16",
    "granite3.2-vision:2b-q8_0",
    "granite3.3:8b",
    "hermes3:8b-llama3.1-q3_K_M",
    "internlm2:7b-chat-1m-v2.5-q4_K_M",
    "llama2:7b-chat-q4_K_M",
    "llama2:13b-chat-q4_K_M",
    "llama3.1:8b-instruct-q4_K_M",
    "llama3.2:3b-instruct-q8_0",
    "llama3.2:3b-text-fp16",
    "llama3.3:70b-instruct-q4_K_M",
    "marco-o1:7b-q4_K_M",
    "mistral:7b-instruct-q4_K_M",
    "mistral-small3.1:24b-instruct-2503-q4_K_M",
    "mixtral:8x7b-instruct-v0.1-q3_K_M",
    "nemotron:70b-instruct-q4_K_M",
    "nemotron-mini:4b-instruct-q3_K_M",
    "nemotron-mini:4b-instruct-q8_0",
    "olmo2:7b-1124-instruct-q4_K_M",
    "openthinker:7b-q4_K_M",
    "openthinker:32b-v2-q4_K_M",
    "phi3.5:3.8b-mini-instruct-q4_K_M",
    "phi3.5:3.8b-mini-instruct-q8_0",
    "phi4:14b-q4_K_M",
    "phi4-mini:3.8b-q4_K_M",
    "phi4-mini:3.8b-q8_0",
    "qwen2.5:7b-instruct-q4_K_M",
    "qwq:32b-preview-q4_K_M",
    "reflection:70b-q4_K_M",
    "sailor2:8b-chat-q4_K_M",
    "smallthinker:3b-preview-q8_0",
    "smollm2:1.7b-instruct-q8_0",
    "solar-pro:22b-preview-instruct-q4_K_M",
    "tulu3:8b-q4_K_M",
    "tulu3:70b-q4_K_M"
    # "vicuna",
    # "wizardlm",
    # "yi"
]

            ["ollama", "pull", model_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Combine stderr with stdout
            universal_newlines=True,   # Handle text properly
            bufsize=1                  # Line buffered
        )
        
        last_progress = 0
        start_download_time = time.time()
        last_activity_time = start_download_time
        
        # Read output line by line
        while process.poll() is None:
            # Check for timeout
            current_time = time.time()
            if current_time - start_download_time > timeout:
                process.terminate()
                print(f"Download timed out after {timeout} seconds for {model_name}")
                break
            
            # Try to read a line without blocking
            line = process.stdout.readline()
            if line:
                last_activity_time = current_time
                
                # Extract progress percentage from the line
                progress = extract_progress(line)
                if progress is not None and progress > last_progress:
                    pbar.update(progress - last_progress)
                    last_progress = progress
            else:
                # No output available at the moment, sleep briefly
                time.sleep(0.1)
                
                # Check for stalled download (5 minutes without activity)
                if current_time - last_activity_time > 300:
                    print(f"Download appears stalled (no activity for 5 minutes). Continuing...")
                    break
        
        # Ensure the progress bar reaches 100% at the end
        if last_progress < 100:
            pbar.update(100 - last_progress)
            
        # Close progress bar
        pbar.close()
        
        # Wait for process to complete (with timeout)
        try:
            return_code = process.wait(timeout=10)  # Wait up to 10 more seconds
        except subprocess.TimeoutExpired:
            process.terminate()
            print(f"Had to forcefully terminate the process for {model_name}")
            return_code = -1
        
        # Check for errors
        if return_code != 0:
            print(f"Error downloading {model_name}: Process returned code {return_code}")
        else:
            end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{end_time}] Finished download: {model_name} (alias: {alias})")
            
        # Verify the model was downloaded successfully
        downloaded_models = get_downloaded_models()
        if model_name not in downloaded_models:
            print(f"Warning: Process completed but {model_name} was not found in installed models.")
            
    except Exception as e:
        print(f"An error occurred while downloading {model_name}: {e}")
        # Make sure to close the progress bar if an exception occurs
        if 'pbar' in locals():
            pbar.close()

def main():
    downloaded_models = get_downloaded_models()
    print("Downloaded models:", downloaded_models)
    for model in model_ls:
        if model in downloaded_models:
            print(f"Model '{model}' already downloaded. Skipping.")
            continue
        download_model(model)
        time.sleep(DELAY_BETWEEN_DOWNLOADS_SEC)

if __name__ == "__main__":
    main()