import subprocess
import time
from tqdm import tqdm

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
    "deepseek-r1:8b-llama-distill-q4_K_M"
]

# Delay between downloads in seconds
DELAY_BETWEEN_DOWNLOADS_SEC = 5

def download_model(model_name):
    try:
        # Initialize progress bar
        with tqdm(total=100, desc=f"Downloading {model_name}", unit='%') as pbar:
            # Run the pull command
            process = subprocess.Popen(
                ["ollama", "pull", model_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    # Here, you would parse the output to update the progress bar
                    # For example, if the output contains progress percentage:
                    # progress = extract_progress_from_output(output)
                    # pbar.update(progress - pbar.n)
                    pass
            _, stderr = process.communicate()
            if process.returncode != 0:
                print(f"Error downloading {model_name}: {stderr.strip()}")
    except Exception as e:
        print(f"An error occurred while downloading {model_name}: {e}")

def main():
    for model in models:
        download_model(model)
        time.sleep(DELAY_BETWEEN_DOWNLOADS_SEC)

if __name__ == "__main__":
    main()
