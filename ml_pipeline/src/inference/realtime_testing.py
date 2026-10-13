import os
import time

import joblib
import numpy as np

from configs.settings import (
    DAQ_BOARD_NUM,
    DAQ_BUFFER_SIZE,
    DAQ_CHANNEL,
    HOP_SAMPLES,
    LABEL_ENCODER_FILENAME,
    MODEL_FILENAME,
    OUTPUT_DIR,
    RT_ACTIVE_RMS_THRESH,
    RT_CONFIDENCE_THRESH,
    SAMPLING_RATE,
    SCALER_FILENAME,
    SELECTOR_FILENAME,
    WINDOW_SAMPLES,
)
from src.data.emg_csv import load_emg_csv_signal
from src.preprocessing.feature_extraction import extract_emg_features, validate_features
from src.preprocessing.signal_preprocessing import preprocess_signal


class EMGClassifierRT:
    def __init__(self, artifact_dir: str = OUTPUT_DIR):
        self.artifact_dir = artifact_dir
        self.model = joblib.load(os.path.join(artifact_dir, MODEL_FILENAME))
        self.scaler = joblib.load(os.path.join(artifact_dir, SCALER_FILENAME))
        self.label_encoder = joblib.load(os.path.join(artifact_dir, LABEL_ENCODER_FILENAME))
        selector_info = joblib.load(os.path.join(artifact_dir, SELECTOR_FILENAME))
        self.selected_mask = np.array(selector_info["mask"])
        self.selected_features = selector_info["selected_features"]

    def predict(self, raw_signal: np.ndarray):
        denoised = preprocess_signal(raw_signal, fs=SAMPLING_RATE)
        rms = float(np.sqrt(np.mean(denoised**2)))
        if rms < RT_ACTIVE_RMS_THRESH:
            return None, 0.0, rms

        feats = np.array(extract_emg_features(denoised), dtype=np.float32).reshape(1, -1)
        if not validate_features(feats):
            return None, 0.0, rms

        feats_scaled = self.scaler.transform(feats)
        feats_sel = feats_scaled[:, self.selected_mask]
        probs = self.model.predict_proba(feats_sel)[0]
        pred_idx = int(np.argmax(probs))
        confidence = float(np.max(probs))
        label = self.label_encoder.inverse_transform([pred_idx])[0]
        return label, confidence, rms


def test_from_csv_file(classifier: EMGClassifierRT, csv_path: str, n_windows: int = 100):
    print(f"\nLoading CSV file: {csv_path}")
    try:
        signal_data = load_emg_csv_signal(csv_path)
        predictions = []
        confidences = []
        rms_values = []

        for i in range(n_windows):
            start = i * HOP_SAMPLES
            if start + WINDOW_SAMPLES > len(signal_data):
                break

            window = signal_data[start : start + WINDOW_SAMPLES]
            label, confidence, rms = classifier.predict(window)
            if label is None:
                continue

            predictions.append(label)
            confidences.append(confidence)
            rms_values.append(rms)
            flag = "OK" if confidence >= RT_CONFIDENCE_THRESH else "LOW"
            print(f"[{i + 1:3d}] {label:8s} | conf={confidence:.3f} ({flag}) | rms={rms:.5f}")

        return predictions, confidences, rms_values
    except Exception as exc:
        print(f"Error while testing from CSV: {exc}")
        return [], [], []


def test_from_daq_usb1808(classifier: EMGClassifierRT, duration_sec: int = 30):
    try:
        from mcculw import ul
        from mcculw.enums import FunctionType, ScanOptions, ULRange
    except ImportError:
        print("MCCulW library not installed. Install with: pip install mcculw")
        return

    try:
        mem_handle = ul.scaled_win_buf_alloc(DAQ_BUFFER_SIZE)
        if not mem_handle:
            print("Buffer allocation failed.")
            return

        ul.a_in_scan(
            DAQ_BOARD_NUM,
            DAQ_CHANNEL,
            DAQ_CHANNEL,
            DAQ_BUFFER_SIZE,
            SAMPLING_RATE,
            ULRange.BIP10VOLTS,
            mem_handle,
            ScanOptions.BACKGROUND | ScanOptions.CONTINUOUS | ScanOptions.SCALEDATA,
        )

        buffer = []
        start_time = time.time()
        frame = 0
        while (time.time() - start_time) < duration_sec:
            status, curr_count, _curr_index = ul.get_status(DAQ_BOARD_NUM, FunctionType.AIFUNCTION)
            if status == 0:
                print("\nDAQ stopped unexpectedly.")
                break

            if curr_count > 0:
                data_array = ul.scaled_win_buf_to_array(mem_handle, 0, curr_count)
                buffer.extend(data_array)

            while len(buffer) >= WINDOW_SAMPLES:
                frame += 1
                window = np.array(buffer[:WINDOW_SAMPLES], dtype=np.float32)
                label, confidence, rms = classifier.predict(window)
                if label is not None and confidence >= RT_CONFIDENCE_THRESH:
                    print(f"[{frame:4d}] {label:8s} (conf={confidence:.2f}, rms={rms:.4f})")
                buffer = buffer[WINDOW_SAMPLES:]
            time.sleep(0.01)

        ul.stop_background(DAQ_BOARD_NUM, FunctionType.AIFUNCTION)
        ul.win_buf_free(mem_handle)
    except Exception as exc:
        print(f"DAQ error: {exc}")


def main_menu():
    classifier = EMGClassifierRT(OUTPUT_DIR)
    while True:
        print("\n1. Test from CSV file (offline)")
        print("2. Test from USB-1808 DAQ (real-time)")
        print("3. Exit")
        choice = input("Select option (1-3): ").strip()

        if choice == "1":
            csv_file = input("Enter CSV file path: ").strip()
            if os.path.exists(csv_file):
                test_from_csv_file(classifier, csv_file)
            else:
                print(f"File not found: {csv_file}")
        elif choice == "2":
            duration = input("Acquisition duration (sec, default 30): ").strip()
            try:
                duration_value = int(duration) if duration else 30
            except ValueError:
                duration_value = 30
            test_from_daq_usb1808(classifier, duration_sec=duration_value)
        elif choice == "3":
            break
        else:
            print("Invalid option. Please choose 1, 2, or 3.")


if __name__ == "__main__":
    main_menu()
