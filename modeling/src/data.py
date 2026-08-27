import os
import glob
import numpy as np
import pandas as pd

def generate_synthetic_data(num_samples, fs=1000.0, healthy=True):
    t = np.arange(num_samples) / fs
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

def load_data(data_dir: str, target_axis: str = 'az', fs: float = 1000.0) -> np.ndarray:
    parquet_files = glob.glob(os.path.join(data_dir, "**/*.parquet"), recursive=True)

    if len(parquet_files) > 0:
        print(f"Loading {len(parquet_files)} real dataset files from {data_dir}...")
        all_signals = []
        for f in parquet_files:
            df = pd.read_parquet(f)
            if target_axis in df.columns:
                all_signals.append(df[target_axis].values)
        if len(all_signals) > 0:
            return np.concatenate(all_signals)

    print(f"No .parquet files found in {data_dir}. Generating synthetic baseline data...")
    return generate_synthetic_data(200_000, fs=fs, healthy=True)
