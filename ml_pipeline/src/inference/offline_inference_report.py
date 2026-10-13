import argparse
import os
import re

import numpy as np
import pandas as pd

from configs.settings import (
    HOP_SAMPLES,
    OFFLINE_SUMMARY_FILENAME,
    RT_CONFIDENCE_THRESH,
    SAMPLING_RATE,
    WINDOW_SAMPLES,
)
from src.data.emg_csv import load_emg_csv_signal
from src.inference.realtime_testing import EMGClassifierRT


def infer_command_name(csv_path: str, class_labels) -> str:
    text = csv_path.lower()
    tokens = set(re.findall(r"[a-z0-9]+", text))
    for label in class_labels:
        candidate = str(label).lower()
        if candidate in tokens:
            return candidate
    return "unknown"


def run_offline_inference_report(
    csv_path: str,
    n_windows: int | None = None,
    confidence_threshold: float = RT_CONFIDENCE_THRESH,
    out_csv: str = OFFLINE_SUMMARY_FILENAME,
):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    signal_name = os.path.basename(csv_path)
    classifier = EMGClassifierRT()
    signal_command = infer_command_name(csv_path, classifier.label_encoder.classes_)
    signal_data = load_emg_csv_signal(csv_path)

    if len(signal_data) < WINDOW_SAMPLES:
        raise ValueError(f"Signal too short: {len(signal_data)} samples, need at least {WINDOW_SAMPLES}")

    max_windows = 1 + (len(signal_data) - WINDOW_SAMPLES) // HOP_SAMPLES
    total_windows_to_scan = max_windows if n_windows is None else min(n_windows, max_windows)

    predictions = []
    confidences = []
    for i in range(total_windows_to_scan):
        start = i * HOP_SAMPLES
        window = signal_data[start : start + WINDOW_SAMPLES]
        label, confidence, _rms = classifier.predict(window)
        if label is None:
            continue
        predictions.append(label)
        confidences.append(float(confidence))

    if not predictions:
        pd.DataFrame(
            [
                {"metric": "input_signal_name", "value": signal_name},
                {"metric": "input_signal_command", "value": signal_command},
                {"metric": "input_signal_path", "value": csv_path},
                {"metric": "valid_windows_classified", "value": 0},
            ]
        ).to_csv(out_csv, index=False)
        return out_csv

    total_valid = len(predictions)
    conf_arr = np.asarray(confidences, dtype=np.float32)
    class_counts = pd.Series(predictions).value_counts()
    dominant_class = str(class_counts.index[0])
    dominant_pct = 100.0 * int(class_counts.iloc[0]) / total_valid
    mean_conf = float(np.mean(conf_arr))
    min_conf = float(np.min(conf_arr))
    max_conf = float(np.max(conf_arr))
    above_thr_pct = 100.0 * float(np.mean(conf_arr >= confidence_threshold))

    if total_valid > 1:
        same_next = sum(1 for i in range(1, total_valid) if predictions[i] == predictions[i - 1])
        temporal_consistency = 100.0 * same_next / (total_valid - 1)
    else:
        temporal_consistency = 0.0

    rows = [
        {"metric": "input_signal_name", "value": signal_name},
        {"metric": "input_signal_command", "value": signal_command},
        {"metric": "input_signal_path", "value": csv_path},
        {"metric": "total_valid_windows_classified", "value": total_valid},
        {"metric": "dominant_predicted_class", "value": dominant_class},
        {"metric": "dominant_predicted_class_percentage", "value": round(dominant_pct, 4)},
        {"metric": "confidence_mean", "value": round(mean_conf, 6)},
        {"metric": "confidence_min", "value": round(min_conf, 6)},
        {"metric": "confidence_max", "value": round(max_conf, 6)},
        {"metric": "windows_above_confidence_threshold_percentage", "value": round(above_thr_pct, 4)},
        {"metric": "temporal_consistency_percentage", "value": round(temporal_consistency, 4)},
        {"metric": "sampling_rate_hz", "value": SAMPLING_RATE},
    ]

    for cls_name, cls_count in class_counts.items():
        cls_pct = 100.0 * float(cls_count) / total_valid
        rows.append({"metric": f"class_{cls_name}_count", "value": int(cls_count)})
        rows.append({"metric": f"class_{cls_name}_percentage", "value": round(cls_pct, 4)})

    pd.DataFrame(rows).to_csv(out_csv, index=False)
    return out_csv


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate pre-recorded sEMG CSV and export report-ready inference metrics."
    )
    parser.add_argument("csv_path", nargs="?", default=None, help="Path to input CSV file")
    parser.add_argument("--n-windows", type=int, default=None)
    parser.add_argument("--conf-threshold", type=float, default=RT_CONFIDENCE_THRESH)
    parser.add_argument("--output", default=OFFLINE_SUMMARY_FILENAME)
    args = parser.parse_args()

    csv_path = args.csv_path or input("Enter CSV file path: ").strip().strip('"')
    if not csv_path:
        print("No CSV path provided. Exiting.")
        return

    out_csv = run_offline_inference_report(
        csv_path=csv_path,
        n_windows=args.n_windows,
        confidence_threshold=args.conf_threshold,
        out_csv=args.output,
    )
    print(f"Saved summary: {out_csv}")


if __name__ == "__main__":
    main()
