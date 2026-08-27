import numpy as np
from scipy.fft import rfft
from typing import Tuple

def extract_fft_features(signal_window: np.ndarray) -> np.ndarray:
    # Remove DC offset
    signal_window = signal_window - np.mean(signal_window)
    # Apply Hanning window
    windowed = signal_window * np.hanning(len(signal_window))
    # Compute FFT magnitude (first half of the spectrum)
    fft_mag = np.abs(rfft(windowed))
    return fft_mag.astype(np.float32)

def preprocess_signal(full_signal: np.ndarray, window_size: int, stride: int) -> Tuple[np.ndarray, np.ndarray]:
    X_features = []
    for i in range(0, len(full_signal) - window_size, stride):
        window = full_signal[i:i + window_size]
        X_features.append(extract_fft_features(window))

    X_train = np.array(X_features)

    # Normalize features (MinMax scaling based on training data)
    feature_max = np.max(X_train, axis=0) + 1e-6 # prevent div by zero
    X_train_scaled = X_train / feature_max

    return X_train_scaled, feature_max
