from dagster import asset, Definitions, Config, MaterializeResult, AssetExecutionContext
import mlflow
import mlflow.keras
import numpy as np
import tensorflow as tf
from .data import load_data
from .features import preprocess_signal
from .model import build_autoencoder
from .export import export_tflite_and_header
import tempfile
import os

class DataConfig(Config):
    data_dir: str = "../pc_app/dataset/machine_001/healthy/"
    target_axis: str = 'az'
    fs: float = 1000.0

class FeatureConfig(Config):
    window_size: int = 128
    stride: int = 64

class TrainConfig(Config):
    epochs: int = 30
    batch_size: int = 64
    validation_split: float = 0.2
    percentile_threshold: float = 99.0
    mlflow_tracking_uri: str = "sqlite:///mlruns.db"
    mlflow_experiment_name: str = "vibration_anomaly_detection"

class ExportConfig(Config):
    output_dir: str = "model"

@asset
def raw_signal(context: AssetExecutionContext, config: DataConfig) -> np.ndarray:
    context.log.info(f"Loading data from {config.data_dir}")
    signal = load_data(config.data_dir, config.target_axis, config.fs)
    context.log.info(f"Loaded signal of length {len(signal)}")
    return signal

@asset
def training_features(context: AssetExecutionContext, config: FeatureConfig, raw_signal: np.ndarray) -> dict:
    context.log.info(f"Extracting features with window_size={config.window_size}, stride={config.stride}")
    X_train_scaled, feature_max = preprocess_signal(raw_signal, config.window_size, config.stride)
    context.log.info(f"Extracted {len(X_train_scaled)} features of size {X_train_scaled.shape[1]}")
    return {
        "X_train_scaled": X_train_scaled,
        "feature_max": feature_max
    }

@asset
def trained_autoencoder(context: AssetExecutionContext, config: TrainConfig, training_features: dict) -> dict:
    mlflow.set_tracking_uri(config.mlflow_tracking_uri)
    mlflow.set_experiment(config.mlflow_experiment_name)
    
    X_train_scaled = training_features["X_train_scaled"]
    input_dim = X_train_scaled.shape[1]
    
    with mlflow.start_run() as run:
        mlflow.log_param("epochs", config.epochs)
        mlflow.log_param("batch_size", config.batch_size)
        mlflow.log_param("validation_split", config.validation_split)
        mlflow.log_param("percentile_threshold", config.percentile_threshold)
        mlflow.log_param("input_dim", input_dim)
        
        # Build and train
        model = build_autoencoder(input_dim)
        history = model.fit(
            X_train_scaled,
            X_train_scaled,
            epochs=config.epochs,
            batch_size=config.batch_size,
            validation_split=config.validation_split,
            verbose=1
        )
        
        # Log metrics from last epoch
        mlflow.log_metric("loss", history.history['loss'][-1])
        mlflow.log_metric("val_loss", history.history['val_loss'][-1])
        
        # Calculate threshold
        train_predictions = model.predict(X_train_scaled)
        train_mse = np.mean(np.square(X_train_scaled - train_predictions), axis=1)
        threshold = float(np.percentile(train_mse, config.percentile_threshold))
        
        mlflow.log_metric("anomaly_threshold", threshold)
        
        # Save model to mlflow
        mlflow.keras.log_model(model, "autoencoder_model")
        context.log.info(f"Calculated anomaly threshold: {threshold:.6f}")

        # Save model to disk for passing to the next step
        model_path = os.path.join(config.mlflow_experiment_name, "keras_model.keras")
        os.makedirs(config.mlflow_experiment_name, exist_ok=True)
        model.save(model_path)
        
    return {
        "model_path": model_path,
        "threshold": threshold
    }

@asset
def exported_model(context: AssetExecutionContext, config: ExportConfig, training_features: dict, trained_autoencoder: dict) -> MaterializeResult:
    model = tf.keras.models.load_model(trained_autoencoder["model_path"])
    threshold = trained_autoencoder["threshold"]
    X_train_scaled = training_features["X_train_scaled"]
    feature_max = training_features["feature_max"]
    
    export_tflite_and_header(model, X_train_scaled, feature_max, threshold, config.output_dir)

    
    context.log.info(f"Exported model to {config.output_dir}")
    return MaterializeResult(
        metadata={
            "output_dir": config.output_dir,
            "tflite_size_bytes": os.path.getsize(os.path.join(config.output_dir, "anomaly_model.tflite")),
        }
    )

defs = Definitions(
    assets=[raw_signal, training_features, trained_autoencoder, exported_model]
)
