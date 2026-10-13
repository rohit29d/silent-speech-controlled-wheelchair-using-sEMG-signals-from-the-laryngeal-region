import numpy as np
from scipy.linalg import toeplitz
from scipy.signal import welch
from scipy.stats import entropy, kurtosis, skew

from configs.settings import (
    ACTIVE_RMS_THRESH,
    FEATURE_NAMES,
    HOP_SAMPLES,
    N_FEATURES,
    SAMPLING_RATE,
    WINDOW_SAMPLES,
)


def extract_emg_features(signal: np.ndarray, fs: float = SAMPLING_RATE):
    signal = signal.astype(np.float32)

    mav = np.mean(np.abs(signal))
    rms = np.sqrt(np.mean(signal**2))
    wl = np.sum(np.abs(np.diff(signal)))
    var = np.var(signal)
    std = np.std(signal)
    sk = skew(signal)
    kur = kurtosis(signal)

    threshold = 1e-4
    zc = np.sum(
        (signal[:-1] * signal[1:] < 0)
        & (np.abs(signal[:-1] - signal[1:]) > threshold)
    )

    s1 = signal[:-2] - signal[1:-1]
    s2 = signal[1:-1] - signal[2:]
    ssc = np.sum((s1 * s2 < 0) & (np.abs(s1) > threshold) & (np.abs(s2) > threshold))

    freqs, psd = welch(signal, fs=fs, nperseg=min(256, len(signal)))
    total_pwr = np.sum(psd)
    psd_norm = psd / total_pwr if total_pwr > 0 else psd

    mnf = np.sum(freqs * psd_norm)
    cumsum_psd = np.cumsum(psd_norm)
    mdf = freqs[np.searchsorted(cumsum_psd, 0.5, side="left")] if total_pwr > 0 else 0.0
    peak_f = freqs[np.argmax(psd)] if np.any(psd > 0) else 0.0
    spec_entropy = entropy(psd_norm) if total_pwr > 0 else 0.0

    norm_wl = wl / (np.sum(np.abs(signal)) + 1e-8)
    log_total_power = np.log10(total_pwr + 1e-8)
    log_var = np.log10(var + 1e-8)
    spec_centroid_ratio = (mnf / (peak_f + 1e-8)) if peak_f > 0 else 0.0
    spec_energy_concentration = 1.0 / (1.0 + spec_entropy)

    idx_low = (freqs >= 20.0) & (freqs < 80.0)
    idx_mid = (freqs >= 80.0) & (freqs < 200.0)
    idx_high = (freqs >= 200.0) & (freqs < 450.0)
    pwr_low = np.sum(psd[idx_low])
    pwr_mid = np.sum(psd[idx_mid])
    pwr_high = np.sum(psd[idx_high])

    total_band_power = pwr_low + pwr_mid + pwr_high + 1e-8
    pwr_low_ratio = pwr_low / total_band_power
    pwr_mid_ratio = pwr_mid / total_band_power
    power_ratio = pwr_low / (pwr_high + 1e-8)

    if len(signal) > 2:
        tkeo = signal[1:-1] ** 2 - (signal[:-2] * signal[2:])
        tkeo_mav = np.mean(np.abs(tkeo))
        tkeo_rms = np.sqrt(np.mean(tkeo**2))
        tkeo_std = np.std(tkeo)
    else:
        tkeo_mav = tkeo_rms = tkeo_std = 0.0

    try:
        autocorr = np.correlate(signal, signal, mode="full")
        autocorr = autocorr[len(autocorr) // 2 :]
        ar_matrix = toeplitz(autocorr[:4])
        ar_rhs = autocorr[1:5]
        ar1, ar2, ar3, ar4 = np.linalg.solve(ar_matrix, ar_rhs).tolist()
    except Exception:
        ar1 = ar2 = ar3 = ar4 = 0.0

    return [
        mav,
        rms,
        wl,
        var,
        std,
        sk,
        kur,
        zc,
        ssc,
        mnf,
        mdf,
        peak_f,
        spec_entropy,
        total_pwr,
        norm_wl,
        log_total_power,
        log_var,
        power_ratio,
        spec_centroid_ratio,
        spec_energy_concentration,
        tkeo_mav,
        tkeo_rms,
        tkeo_std,
        pwr_low,
        pwr_mid,
        pwr_high,
        pwr_low_ratio,
        pwr_mid_ratio,
        ar1,
        ar2,
        ar3,
        ar4,
    ]


def extract_features_sliding(
    signal: np.ndarray,
    window_size: int = WINDOW_SAMPLES,
    increment: int = HOP_SAMPLES,
):
    features = []
    for start in range(0, len(signal) - window_size + 1, increment):
        window = signal[start : start + window_size].astype(np.float32)
        rms = np.sqrt(np.mean(window**2))
        if rms < ACTIVE_RMS_THRESH:
            continue
        features.append(extract_emg_features(window))
    return features


def validate_features(features) -> bool:
    features_arr = np.array(features, dtype=np.float32)
    return np.all(np.isfinite(features_arr))
