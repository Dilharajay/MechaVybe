import os
import glob
import numpy as np
import pandas as pd
import tensorflow as tf
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.fft import rfft

SEED = 42
np.random.seed(SEED)
tf.random.set_seed(SEED)

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------
DATA_DIR = "../pc_app/dataset/machine_001/healthy/"
WINDOW_SIZE = 128  # 128 samples @ 1000Hz = 128ms
STRIDE = 64
FS = 1000.0
TARGET_AXIS = 'az' # Primary vibration axis

# ---------------------------------------------------------
# 1. Data Loading & Feature Extraction
# ---------------------------------------------------------
def extract_fft_features(signal_window):
    # Remove DC offset
    signal_window = signal_window - np.mean(signal_window)
    # Apply Hanning window
    windowed = signal_window * np.hanning(len(signal_window))
    # Compute FFT magnitude (first half of the spectrum)
    fft_mag = np.abs(rfft(windowed))
    return fft_mag.astype(np.float32)

def generate_synthetic_data(num_samples, healthy=True):
    t = np.arange(num_samples) / FS
    # Base machine resonance at 50Hz and 120Hz
    signal = 0.5 * np.sin(2 * np.pi * 50 * t) + 0.2 * np.sin(2 * np.pi * 120 * t)
    
    if healthy:
        # Healthy: Normal operational noise
        signal += np.random.normal(0, 0.05, num_samples)
    else:
        # Faulty: Introduce high frequency bearing noise (300Hz) and impact spikes
        signal += np.random.normal(0, 0.15, num_samples)
        signal += 0.4 * np.sin(2 * np.pi * 300 * t)
    return signal

# Try loading real parquet data, otherwise use synthetic
parquet_files = glob.glob(os.path.join(DATA_DIR, "**/*.parquet"), recursive=True)

if len(parquet_files) > 0:
    print(f"Loading {len(parquet_files)} real dataset files from {DATA_DIR}...")
    all_signals = []
    for f in parquet_files:
        df = pd.read_parquet(f)
        if TARGET_AXIS in df.columns:
            all_signals.append(df[TARGET_AXIS].values)
    full_signal = np.concatenate(all_signals)
else:
    print(f"No .parquet files found in {DATA_DIR}. Generating synthetic baseline data...")
    full_signal = generate_synthetic_data(200_000, healthy=True)
    test_faulty_signal = generate_synthetic_data(50_000, healthy=False)

# Window the signal and extract FFT
X_features = []
for i in range(0, len(full_signal) - WINDOW_SIZE, STRIDE):
    window = full_signal[i:i + WINDOW_SIZE]
    X_features.append(extract_fft_features(window))

X_train = np.array(X_features)

# Normalize features (MinMax scaling based on training data)
feature_max = np.max(X_train, axis=0) + 1e-6 # prevent div by zero
X_train_scaled = X_train / feature_max

print(f"Extracted {len(X_train_scaled)} training windows. Feature size: {X_train_scaled.shape[1]}")
INPUT_DIM = X_train_scaled.shape[1]

# ---------------------------------------------------------
# 2. Build Autoencoder Model
# ---------------------------------------------------------
model = tf.keras.Sequential([
    tf.keras.layers.Input(shape=(INPUT_DIM,)),
    tf.keras.layers.Dense(32, activation="relu"),
    tf.keras.layers.Dense(16, activation="relu"),
    tf.keras.layers.Dense(8, activation="relu", name="bottleneck"), # Compression
    tf.keras.layers.Dense(16, activation="relu"),
    tf.keras.layers.Dense(32, activation="relu"),
    tf.keras.layers.Dense(INPUT_DIM, activation="linear") # Reconstruct original FFT
])

model.compile(optimizer="adam", loss="mse")
model.summary()

# ---------------------------------------------------------
# 3. Train the Autoencoder
# ---------------------------------------------------------
print("Training Autoencoder on healthy baseline data...")
history = model.fit(
    X_train_scaled,
    X_train_scaled, # Autoencoder target is its own input
    epochs=30,
    batch_size=64,
    validation_split=0.2,
    verbose=1,
)

# ---------------------------------------------------------
# 4. Determine Anomaly Threshold
# ---------------------------------------------------------
# Calculate reconstruction error (MSE) for all healthy training data
train_predictions = model.predict(X_train_scaled)
train_mse = np.mean(np.square(X_train_scaled - train_predictions), axis=1)

# Set threshold at the 99th percentile of healthy data error
THRESHOLD = np.percentile(train_mse, 99)
print(f"\nCalculated Anomaly Threshold: {THRESHOLD:.6f}")

# ---------------------------------------------------------
# 5. Convert to INT8 TensorFlow Lite
# ---------------------------------------------------------
def representative_dataset():
    # Provide a few hundred samples for the quantizer to calibrate activations
    for i in range(min(500, len(X_train_scaled))):
        yield [X_train_scaled[i:i+1].astype(np.float32)]

converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.representative_dataset = representative_dataset
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
converter.inference_input_type = tf.int8
converter.inference_output_type = tf.int8

tflite_model = converter.convert()

# ---------------------------------------------------------
# 6. Save Model and Generate C-Header
# ---------------------------------------------------------
output_dir = Path("model")
output_dir.mkdir(parents=True, exist_ok=True)

model_path = output_dir / "anomaly_model.tflite"
model_path.write_bytes(tflite_model)
print(f"\nSaved TFLite model: {model_path} ({len(tflite_model)} bytes)")

# Convert to C Header format for ESP32
c_array = ", ".join([f"0x{b:02x}" for b in tflite_model])
c_header_content = f"""// Auto-generated Anomaly Detection Model
// Input Shape: {INPUT_DIM} (FFT Bins)
// Threshold: {THRESHOLD:.6f}

#ifndef MODEL_H
#define MODEL_H

#include <stdint.h>

const unsigned int model_tflite_len = {len(tflite_model)};
const uint8_t model_tflite[] = {{
    {c_array}
}};

// Normalization max values (multiply ESP32 inputs by 1/feature_max)
const float feature_max[{INPUT_DIM}] = {{
    {", ".join([f"{val:.4f}" for val in feature_max])}
}};

const float ANOMALY_THRESHOLD = {THRESHOLD:.6f};

#endif // MODEL_H
"""

header_path = output_dir / "model.h"
header_path.write_text(c_header_content)
print(f"Saved C-Header: {header_path}")
print("\nDone! You can now copy model/model.h to your ESP32 firmware/include/ directory.")