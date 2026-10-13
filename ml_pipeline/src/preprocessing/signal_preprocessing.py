import numpy as np
import pywt
from scipy import signal as scipy_signal

from configs.settings import (
    BUTTER_HIGHCUT,
    BUTTER_LOWCUT,
    BUTTER_ORDER,
    PRESERVE_BAND,
    PRESERVE_SCALE,
    SAMPLING_RATE,
    USE_FLOOR,
    WAVELET_LEVEL,
    WAVELET_MODE,
    WAVELET_TYPE,
)


def apply_butter_bandpass(
    data,
    lowcut=BUTTER_LOWCUT,
    highcut=BUTTER_HIGHCUT,
    order=BUTTER_ORDER,
    fs=SAMPLING_RATE,
):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = scipy_signal.butter(order, [low, high], btype="band")
    filtered = scipy_signal.filtfilt(b, a, data.astype(np.float32))
    return filtered.astype(np.float32)


def apply_wavelet_denoising_bandaware(
    signal_input,
    fs,
    wavelet,
    level,
    preserve_band=None,
    preserve_scale=0.6,
    use_floor=True,
    mode="soft",
    debug=False,
):
    signal_input = np.asarray(signal_input, dtype=np.float32)

    if level is None:
        level = pywt.dwt_max_level(len(signal_input), pywt.Wavelet(wavelet).dec_len)

    coeffs = pywt.wavedec(signal_input, wavelet, level=level)
    coeffs_thresholded = [coeffs[0]]
    thresholds_info = []

    for idx, coeffs_level in enumerate(coeffs[1:], start=1):
        detail_level = level - (idx - 1)
        f_low = fs / (2 ** (detail_level + 1))
        f_high = fs / (2 ** detail_level)

        sigma_n = np.median(np.abs(coeffs_level)) / 0.6745
        sigma_n_sq = sigma_n**2
        sigma_y_sq = np.mean(coeffs_level**2)
        sigma_x_sq = max(sigma_y_sq - sigma_n_sq, 0.0)

        if sigma_x_sq > 0:
            threshold = sigma_n_sq / np.sqrt(sigma_x_sq)
        else:
            threshold = np.max(np.abs(coeffs_level))

        if preserve_band is not None:
            p_low, p_high = preserve_band
            overlaps = not (f_high < p_low or f_low > p_high)
            threshold *= float(preserve_scale) if overlaps else 1.5

        if use_floor:
            universal_thr = sigma_n * np.sqrt(2 * np.log(len(coeffs_level)))
            if preserve_band is None:
                threshold = max(threshold, universal_thr)
            elif f_low >= preserve_band[1] or f_high <= preserve_band[0]:
                threshold = max(threshold, universal_thr)

        coeffs_thresholded.append(pywt.threshold(coeffs_level, value=threshold, mode=mode))
        thresholds_info.append(
            {
                "detail_level": detail_level,
                "f_low": float(f_low),
                "f_high": float(f_high),
                "sigma_n": float(sigma_n),
                "threshold": float(threshold),
                "len_coeffs": int(len(coeffs_level)),
            }
        )

    denoised = pywt.waverec(coeffs_thresholded, wavelet)
    denoised = denoised[: len(signal_input)].astype(np.float32)
    if debug:
        return denoised, thresholds_info
    return denoised


def preprocess_signal(raw_signal, fs=SAMPLING_RATE):
    filtered = apply_butter_bandpass(raw_signal, fs=fs)
    return apply_wavelet_denoising_bandaware(
        filtered,
        fs=fs,
        wavelet=WAVELET_TYPE,
        level=WAVELET_LEVEL,
        preserve_band=PRESERVE_BAND,
        preserve_scale=PRESERVE_SCALE,
        use_floor=USE_FLOOR,
        mode=WAVELET_MODE,
        debug=False,
    )
