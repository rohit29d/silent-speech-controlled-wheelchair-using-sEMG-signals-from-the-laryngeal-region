import os
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import LabelEncoder, StandardScaler

from configs.settings import DATASET_DIR, FEATURE_CSV_FILENAME, PLOTS_DIR_PATH


OUTPUT_DIR = "outputs/demo_signals"
TOP_N_SUBJECTS = 3
RF_CONFIG = {
    "n_estimators": 100,
    "max_depth": 15,
    "min_samples_split": 20,
    "class_weight": "balanced",
    "n_jobs": -1,
    "random_state": 42,
}


def load_data():
    if not os.path.exists(FEATURE_CSV_FILENAME):
        raise FileNotFoundError(f"Could not find {FEATURE_CSV_FILENAME}. Run feature extraction first.")

    df = pd.read_csv(FEATURE_CSV_FILENAME)
    feature_cols = [col for col in df.columns if col not in ["Label", "Subject"]]
    return df[feature_cols].values, df["Label"].values, df["Subject"].values, feature_cols


def perform_loso_analysis(X, y, subjects, feature_names):
    unique_subjects = np.unique(subjects)
    subject_accuracies = {}
    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y)

    for subject in unique_subjects:
        test_mask = subjects == subject
        train_mask = ~test_mask
        X_train, y_train = X[train_mask], y_encoded[train_mask]
        X_test, y_test = X[test_mask], y_encoded[test_mask]

        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        selector = SelectKBest(f_classif, k=12)
        X_train_sel = selector.fit_transform(X_train_scaled, y_train)
        X_test_sel = selector.transform(X_test_scaled)

        classifier = RandomForestClassifier(**RF_CONFIG)
        classifier.fit(X_train_sel, y_train)
        preds = classifier.predict(X_test_sel)
        subject_accuracies[subject] = accuracy_score(y_test, preds)

    return subject_accuracies


def plot_loso_results(subject_accuracies):
    df_res = pd.DataFrame(list(subject_accuracies.items()), columns=["Subject", "Accuracy"])
    df_res = df_res.sort_values(by="Accuracy", ascending=True)

    plt.figure(figsize=(10, 12))
    plt.hlines(y=df_res["Subject"], xmin=0, xmax=df_res["Accuracy"], color="skyblue", alpha=0.6)
    plt.plot(df_res["Accuracy"], df_res["Subject"], "o", color="steelblue")

    top_3 = df_res.nlargest(3, "Accuracy")
    plt.plot(top_3["Accuracy"], top_3["Subject"], "o", color="orange", markersize=10, label="Top 3 Candidates")
    for _, row in top_3.iterrows():
        plt.text(row["Accuracy"] + 0.01, row["Subject"], f"{row['Accuracy']:.1%}", va="center", color="darkorange", fontweight="bold")

    plt.xlabel("Accuracy (0.0 - 1.0)", fontsize=12)
    plt.ylabel("Subject ID", fontsize=12)
    plt.title("LOSO Analysis: Which Subject works best?", fontsize=14)
    plt.grid(True, axis="x", linestyle="--", alpha=0.7)
    plt.legend()
    plt.tight_layout()
    plt.savefig(PLOTS_DIR_PATH / "loso_subject_accuracy.png", dpi=300)
    plt.close()
    return df_res.sort_values(by="Accuracy", ascending=False)


def extract_best_files(top_subjects, src_root, dest_root):
    src_path = Path(src_root)
    dest_path = Path(dest_root)
    if dest_path.exists():
        shutil.rmtree(dest_path)
    dest_path.mkdir(parents=True, exist_ok=True)

    copied_count = 0
    for subject in top_subjects:
        subject_folder = src_path / subject
        if not subject_folder.exists():
            continue

        silent_folder = subject_folder / "silent"
        if not silent_folder.exists():
            silent_folder = subject_folder

        for label_dir in silent_folder.iterdir():
            if not label_dir.is_dir():
                continue
            dest_label_dir = dest_path / label_dir.name
            dest_label_dir.mkdir(parents=True, exist_ok=True)
            for csv_file in label_dir.glob("**/*.csv"):
                shutil.copy2(csv_file, dest_label_dir / f"{subject}_{csv_file.name}")
                copied_count += 1

    return copied_count


def main():
    X, y, subjects, features = load_data()
    accuracies = perform_loso_analysis(X, y, subjects, features)
    df_sorted = plot_loso_results(accuracies)
    top_subjects = df_sorted["Subject"].head(TOP_N_SUBJECTS).values
    extract_best_files(top_subjects, DATASET_DIR, OUTPUT_DIR)


if __name__ == "__main__":
    main()
