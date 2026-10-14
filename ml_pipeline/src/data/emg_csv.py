from pathlib import Path

import numpy as np
import pandas as pd


def load_emg_csv_signal(csv_path: str | Path) -> np.ndarray:
    csv_path = Path(csv_path)
    df = pd.read_csv(csv_path, skiprows=6)
    return df.iloc[:, 2].values.astype(np.float32)
