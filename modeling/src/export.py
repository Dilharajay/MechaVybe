import tensorflow as tf
from pathlib import Path
import numpy as np

def export_tflite_and_header(model: tf.keras.Model, X_train_scaled: np.ndarray, feature_max: np.ndarray, threshold: float, output_dir: str):
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
    
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    model_path = out_dir / "anomaly_model.tflite"
    model_path.write_bytes(tflite_model)
    print(f"\nSaved TFLite model: {model_path} ({len(tflite_model)} bytes)")

    input_dim = X_train_scaled.shape[1]
    
    # Convert to C Header format for ESP32
    c_array = ", ".join([f"0x{b:02x}" for b in tflite_model])
    c_header_content = f"""// Auto-generated Anomaly Detection Model
// Input Shape: {input_dim} (FFT Bins)
// Threshold: {threshold:.6f}

#ifndef MODEL_H
#define MODEL_H

#include <stdint.h>

const unsigned int model_tflite_len = {len(tflite_model)};
const uint8_t model_tflite[] = {{
    {c_array}
}};

// Normalization max values (multiply ESP32 inputs by 1/feature_max)
const float feature_max[{input_dim}] = {{
    {", ".join([f"{val:.4f}" for val in feature_max])}
}};

const float ANOMALY_THRESHOLD = {threshold:.6f};

#endif // MODEL_H
"""

    header_path = out_dir / "model.h"
    header_path.write_text(c_header_content)
    print(f"Saved C-Header: {header_path}")
