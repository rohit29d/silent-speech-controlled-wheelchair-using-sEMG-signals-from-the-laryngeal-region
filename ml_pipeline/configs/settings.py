from pathlib import Path
import os
import random

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"


def _resolve_dataset_dir() -> Path:
    env_path = os.getenv("FULL_PIPELINE_DATASET_DIR")
    if env_path:
        return Path(env_path).expanduser().resolve()

    default_path = PROJECT_ROOT.parent / "DATASET50"
    if default_path.exists():
        return default_path.resolve()

    return (PROJECT_ROOT / "data" / "dataset50").resolve()


RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

DATASET_DIR_PATH = _resolve_dataset_dir()
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
MODELS_DIR = OUTPUTS_DIR / "models"
PLOTS_DIR_PATH = OUTPUTS_DIR / "plots"
DEMO_SIGNALS_DIR = OUTPUTS_DIR / "demo_signals"
DATA_OUTPUT_DIR = OUTPUTS_DIR / "data"
REPORTS_DIR = OUTPUTS_DIR / "reports"

for directory in (
    OUTPUTS_DIR,
    MODELS_DIR,
    PLOTS_DIR_PATH,
    DEMO_SIGNALS_DIR,
    DATA_OUTPUT_DIR,
    REPORTS_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)

DATASET_DIR = str(DATASET_DIR_PATH)
OUTPUT_DIR = str(MODELS_DIR)
PLOTS_DIR = str(PLOTS_DIR_PATH)

SAMPLING_RATE = 8000
WINDOW_SIZE_MS = 1000
WINDOW_INCREMENT_MS = 50

WINDOW_SAMPLES = int(SAMPLING_RATE * WINDOW_SIZE_MS / 1000)
HOP_SAMPLES = int(SAMPLING_RATE * WINDOW_INCREMENT_MS / 1000)

BUTTER_LOWCUT = 20
BUTTER_HIGHCUT = 350
BUTTER_ORDER = 4

WAVELET_TYPE = "db6"
WAVELET_LEVEL = 6
PRESERVE_BAND = (20, 450)
PRESERVE_SCALE = 0.6
USE_FLOOR = True
WAVELET_MODE = "soft"

ACTIVE_RMS_THRESH = 0.005
N_FEATURES = 32
FEATURE_NAMES = [
    "MAV",
    "RMS",
    "WL",
    "VAR",
    "STD",
    "Skewness",
    "Kurtosis",
    "ZC",
    "SSC",
    "MNF",
    "MDF",
    "PeakF",
    "SpecEntropy",
    "TotalPower",
    "NormWL",
    "LogTotalPower",
    "LogVar",
    "PowerRatio",
    "SpecCentroidRatio",
    "SpecEnergyConcentration",
    "TKEO_MAV",
    "TKEO_RMS",
    "TKEO_STD",
    "Pwr_Low",
    "Pwr_Mid",
    "Pwr_High",
    "Pwr_Low_Ratio",
    "Pwr_Mid_Ratio",
    "AR1",
    "AR2",
    "AR3",
    "AR4",
]

VALID_LABELS = ["front", "left", "back", "right", "start", "stop"]
N_CLASSES = len(VALID_LABELS)
RF_CONFIG = {
    "n_estimators": 100,
    "max_depth": 15,
    "min_samples_split": 20,
    "min_samples_leaf": 7,
    "max_features": "sqrt",
    "criterion": "gini",
    "class_weight": "balanced",
    "random_state": RANDOM_SEED,
    "n_jobs": -1,
    "verbose": 0,
}
N_FEATURES_SELECTED = 32

TEST_SIZE = 0.20
TRAIN_SPLIT_RANDOM_STATE = RANDOM_SEED

USE_DATA_AUGMENTATION = True
AUGMENTATION_METHODS = ["amplitude_scale"]
AMPLITUDE_SCALE_RANGE = (0.8, 1.25)

DAQ_BOARD_NUM = 0
DAQ_CHANNEL = 0
DAQ_SAMPLING_RATE = 8000
DAQ_BUFFER_SIZE = DAQ_SAMPLING_RATE * 2
DAQ_UPDATE_MS = 50
RT_ACTIVE_RMS_THRESH = 0.005
RT_CONFIDENCE_THRESH = 0.40

FEATURE_CSV_FILENAME = str(DATA_OUTPUT_DIR / "master_training_features.csv")
MODEL_FILENAME = "final_rf_model_mcu.joblib"
SCALER_FILENAME = "final_scaler_6_class.joblib"
LABEL_ENCODER_FILENAME = "final_label_encoder_6_class.joblib"
SELECTOR_FILENAME = "final_feature_selector_6_class.joblib"
METADATA_FILENAME = "training_metadata.json"
OFFLINE_SUMMARY_FILENAME = str(REPORTS_DIR / "offline_inference_summary.csv")

PLOT_DPI = 300
PLOT_FORMAT = "png"
FIGSIZE_LARGE = (15, 10)
FIGSIZE_MEDIUM = (12, 8)
FIGSIZE_SMALL = (10, 6)
COLORS_LABELS = {
    "front": "#1f77b4",
    "left": "#ff7f0e",
    "back": "#2ca02c",
    "right": "#d62728",
    "start": "#9467bd",
    "stop": "#8c564b",
}
