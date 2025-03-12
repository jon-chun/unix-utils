import subprocess
import re
import os

def get_ollama_models():
    """Retrieve the list of models from Ollama."""
    result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
    models = []
    for line in result.stdout.splitlines():
        if line.strip() and not line.startswith('NAME'):
            models.append(line.split()[0])
    return models

def generate_os_friendly_name(model_name):
    """Generate an OS-friendly name from the original model name."""
    # Replace reserved characters (e.g., ':', '.') with '-'
    name = re.sub(r'[:.]+', '-', model_name)
    # Collapse multiple sequential '-' or '_' to a single '-'
    name = re.sub(r'[-_]+', '-', name)
    # Replace spaces with '_'
    name = re.sub(r'\s+', '_', name)
    # Convert to lowercase
    return name.lower()

def create_model_alias(original_name, alias_name):
    """Create a new model alias in Ollama."""
    modelfile_content = f"FROM {original_name}\n"
    modelfile_path = f"/tmp/{alias_name}.modelfile"
    with open(modelfile_path, 'w') as f:
        f.write(modelfile_content)
    subprocess.run(['ollama', 'create', alias_name, '--file', modelfile_path])
    os.remove(modelfile_path)

def main():
    models = get_ollama_models()
    for model in models:
        alias_name = generate_os_friendly_name(model)
        if alias_name != model:
            existing_models = get_ollama_models()
            if alias_name not in existing_models:
                print(f"Creating alias '{alias_name}' for model '{model}'")
                create_model_alias(model, alias_name)
            else:
                print(f"Alias '{alias_name}' already exists for model '{model}'")
        else:
            print(f"Model '{model}' already has an OS-friendly name")

if __name__ == "__main__":
    main()
