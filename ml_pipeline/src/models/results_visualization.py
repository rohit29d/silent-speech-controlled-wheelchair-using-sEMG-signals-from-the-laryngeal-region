from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix

from configs.settings import (
    COLORS_LABELS,
    FIGSIZE_LARGE,
    FIGSIZE_MEDIUM,
    PLOT_DPI,
    PLOT_FORMAT,
    PLOTS_DIR_PATH,
)


def _plot_path(filename: str) -> Path:
    return PLOTS_DIR_PATH / filename


def plot_confusion_matrix(y_true, y_pred, y_labels, title="Confusion Matrix", filename="confusion_matrix_rf.png"):
    cm = confusion_matrix(y_true, y_pred, labels=y_labels)
    plt.figure(figsize=FIGSIZE_MEDIUM)
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=y_labels,
        yticklabels=y_labels,
        cbar_kws={"label": "Count"},
        annot_kws={"size": 12},
    )
    plt.title(title, fontsize=14, fontweight="bold")
    plt.ylabel("True Label", fontsize=12)
    plt.xlabel("Predicted Label", fontsize=12)
    plt.tight_layout()
    plt.savefig(_plot_path(filename), dpi=PLOT_DPI, format=PLOT_FORMAT, bbox_inches="tight")
    plt.close()
    return cm


def plot_feature_importance(model, feature_names, top_n=15, filename="feature_importance_rf.png"):
    importances = model.feature_importances_
    indices = np.argsort(importances)[::-1][:top_n]
    df_imp = pd.DataFrame(
        {
            "Feature": [feature_names[i] for i in indices],
            "Importance": importances[indices],
        }
    )
    plt.figure(figsize=FIGSIZE_MEDIUM)
    sns.barplot(data=df_imp, y="Feature", x="Importance", palette="viridis")
    plt.title(f"Top-{top_n} Feature Importance", fontsize=14, fontweight="bold")
    plt.xlabel("Importance Score", fontsize=12)
    plt.tight_layout()
    plt.savefig(_plot_path(filename), dpi=PLOT_DPI, format=PLOT_FORMAT, bbox_inches="tight")
    plt.close()
    return df_imp


def plot_preprocessing_effects(raw_signal, filtered, denoised, fs=8000.0, title="Preprocessing Pipeline"):
    from scipy.fft import fft, fftfreq
    from scipy.signal import welch

    n_samples = len(raw_signal)
    freqs = fftfreq(n_samples, 1.0 / fs)
    raw_fft = np.abs(fft(raw_signal))
    den_fft = np.abs(fft(denoised))
    positive_freqs = freqs >= 0

    fig, axes = plt.subplots(2, 2, figsize=FIGSIZE_LARGE)
    axes[0, 0].plot(raw_signal, color="gray", alpha=0.6, label="Raw")
    axes[0, 0].plot(denoised, color="red", alpha=0.8, label="Denoised")
    axes[0, 0].set_title("Time Domain", fontsize=12, fontweight="bold")
    axes[0, 0].set_xlabel("Samples")
    axes[0, 0].set_ylabel("Amplitude")
    axes[0, 0].legend()
    axes[0, 0].grid(alpha=0.3)

    axes[0, 1].plot(freqs[positive_freqs], raw_fft[positive_freqs], color="gray", alpha=0.6, label="Raw")
    axes[0, 1].plot(freqs[positive_freqs], den_fft[positive_freqs], color="red", alpha=0.8, label="Denoised")
    axes[0, 1].set_title("Frequency Domain", fontsize=12, fontweight="bold")
    axes[0, 1].set_xlabel("Frequency (Hz)")
    axes[0, 1].set_ylabel("Magnitude")
    axes[0, 1].set_xlim(0, 500)
    axes[0, 1].legend()
    axes[0, 1].grid(alpha=0.3)

    emg_mask = (freqs >= 20.0) & (freqs <= 450.0)
    axes[1, 0].plot(freqs[emg_mask], raw_fft[emg_mask], color="gray", alpha=0.6, label="Raw")
    axes[1, 0].plot(freqs[emg_mask], den_fft[emg_mask], color="red", alpha=0.8, label="Denoised")
    axes[1, 0].set_title("EMG Band (20-450 Hz)", fontsize=12, fontweight="bold")
    axes[1, 0].set_xlabel("Frequency (Hz)")
    axes[1, 0].set_ylabel("Magnitude")
    axes[1, 0].legend()
    axes[1, 0].grid(alpha=0.3)

    freq_raw, psd_raw = welch(raw_signal, fs=fs, nperseg=256)
    freq_den, psd_den = welch(denoised, fs=fs, nperseg=256)
    axes[1, 1].semilogy(freq_raw, psd_raw, color="gray", alpha=0.6, label="Raw")
    axes[1, 1].semilogy(freq_den, psd_den, color="red", alpha=0.8, label="Denoised")
    axes[1, 1].set_title("Power Spectral Density", fontsize=12, fontweight="bold")
    axes[1, 1].set_xlabel("Frequency (Hz)")
    axes[1, 1].set_ylabel("PSD")
    axes[1, 1].set_xlim(0, 500)
    axes[1, 1].legend()
    axes[1, 1].grid(alpha=0.3)

    plt.suptitle(title, fontsize=16, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(_plot_path("preprocessing_effects.png"), dpi=PLOT_DPI, format=PLOT_FORMAT, bbox_inches="tight")
    plt.close(fig)


def plot_class_distribution(y_labels, title="Class Distribution", filename="class_distribution.png"):
    unique, counts = np.unique(y_labels, return_counts=True)
    plt.figure(figsize=FIGSIZE_MEDIUM)
    colors = [COLORS_LABELS.get(label, "blue") for label in unique]
    plt.bar(unique, counts, color=colors, alpha=0.7, edgecolor="black")
    plt.title(title, fontsize=14, fontweight="bold")
    plt.xlabel("Class", fontsize=12)
    plt.ylabel("Count", fontsize=12)
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(_plot_path(filename), dpi=PLOT_DPI, format=PLOT_FORMAT, bbox_inches="tight")
    plt.close()


def print_classification_report(y_true, y_pred, y_labels):
    print("\n" + "=" * 80)
    print("CLASSIFICATION REPORT")
    print("=" * 80)
    print(classification_report(y_true, y_pred, labels=y_labels, zero_division=0))
