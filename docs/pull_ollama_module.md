ollama_downloader/
├── __init__.py
├── downloader.py         # Contains all logic above
├── cli.py                # Entry point wrapper for argparse
├── logs/
│   ├── ollama_log_*.txt
│   ├── skipped_but_suspicious.txt
├── data/
│   ├── downloaded_models.json
│   ├── model_metadata.json
│   └── model_report.txt
└── README.md
