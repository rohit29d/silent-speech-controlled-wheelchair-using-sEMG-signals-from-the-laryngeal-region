# full_pipeline

Speech recognition pipeline for sEMG-based command classification. The project includes training, real-time inference, offline report generation, and demo-sample selection utilities while keeping paths centralized and repo-friendly.

## Folder Structure

```text
full_pipeline/
├── configs/
│   ├── __init__.py
│   └── settings.py
├── notebooks/
├── outputs/
│   ├── data/
│   ├── demo_signals/
│   ├── models/
│   ├── plots/
│   └── reports/
├── src/
│   ├── data/
│   ├── inference/
│   ├── models/
│   ├── preprocessing/
│   └── utils/
├── tests/
├── .gitignore
├── README.md
├── requirements.txt
└── run_pipeline.py
```

## Setup

1. Create and activate a Python virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. If your dataset is not located at `../DATASET50`, set:

```bash
FULL_PIPELINE_DATASET_DIR=/path/to/DATASET50
```

On Windows PowerShell:

```powershell
$env:FULL_PIPELINE_DATASET_DIR="C:\path\to\DATASET50"
```

## How To Run

Train the main classifier:

```bash
python run_pipeline.py train
```

Train and generate the entire-dataset distribution plot:

```bash
python run_pipeline.py train-entire-dataset
```

Run offline inference on a recorded CSV:

```bash
python run_pipeline.py infer-offline -- "path/to/sample.csv"
```

Run the interactive real-time menu:

```bash
python run_pipeline.py realtime
```

Generate demo-sample selections from LOSO analysis:

```bash
python run_pipeline.py demo-samples
```

## Notes

- Project paths are centralized in `configs/settings.py`.
- Trained artifacts are saved under `outputs/models/`.
- Generated plots and CSV reports are written under `outputs/plots/` and `outputs/reports/`.
- Core model logic and feature extraction behavior were preserved during the refactor.
