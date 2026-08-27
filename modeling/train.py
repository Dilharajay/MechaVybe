from pathlib import Path

import numpy as np
import tensorflow as tf


SEED = 42

np.random.seed(SEED)
tf.random.set_seed(SEED)


# ---------------------------------------------------------
# 1. Generate dataset
# ---------------------------------------------------------

NUM_SAMPLES = 10_000

X = np.random.uniform(
    low=0.0,
    high=1.0,
    size=(NUM_SAMPLES, 2),
).astype(np.float32)


# Class 1 if x1 + x2 > 1
y = (X[:, 0] + X[:, 1] > 1.0).astype(np.float32)

y = y.reshape(-1, 1)


# ---------------------------------------------------------
# 2. Create train/test split
# ---------------------------------------------------------

indices = np.random.permutation(NUM_SAMPLES)

split = int(NUM_SAMPLES * 0.8)

train_indices = indices[:split]
test_indices = indices[split:]

X_train = X[train_indices]
y_train = y[train_indices]

X_test = X[test_indices]
y_test = y[test_indices]


# ---------------------------------------------------------
# 3. Build tiny neural network
# ---------------------------------------------------------

model = tf.keras.Sequential(
    [
        tf.keras.layers.Input(shape=(2,)),
        tf.keras.layers.Dense(8, activation="relu"),
        tf.keras.layers.Dense(4, activation="relu"),
        tf.keras.layers.Dense(1, activation="sigmoid"),
    ]
)


model.compile(
    optimizer="adam",
    loss="binary_crossentropy",
    metrics=["accuracy"],
)


model.summary()


# ---------------------------------------------------------
# 4. Train
# ---------------------------------------------------------

model.fit(
    X_train,
    y_train,
    epochs=20,
    batch_size=32,
    validation_split=0.2,
    verbose=1,
)


# ---------------------------------------------------------
# 5. Evaluate normal TensorFlow model
# ---------------------------------------------------------

loss, accuracy = model.evaluate(
    X_test,
    y_test,
    verbose=0,
)

print()
print("Float32 model accuracy:", accuracy)


# ---------------------------------------------------------
# 6. INT8 representative dataset
# ---------------------------------------------------------

def representative_dataset():
    for i in range(500):
        sample = X_train[i:i + 1]

        yield [sample.astype(np.float32)]


# ---------------------------------------------------------
# 7. Convert to fully INT8 TensorFlow Lite
# ---------------------------------------------------------

converter = tf.lite.TFLiteConverter.from_keras_model(model)

converter.optimizations = [
    tf.lite.Optimize.DEFAULT
]

converter.representative_dataset = representative_dataset

converter.target_spec.supported_ops = [
    tf.lite.OpsSet.TFLITE_BUILTINS_INT8
]

converter.inference_input_type = tf.int8
converter.inference_output_type = tf.int8


tflite_model = converter.convert()


# ---------------------------------------------------------
# 8. Save model
# ---------------------------------------------------------

output_dir = Path("model")

output_dir.mkdir(
    parents=True,
    exist_ok=True,
)

model_path = output_dir / "model.tflite"

model_path.write_bytes(tflite_model)


print()
print("Saved:", model_path)
print("Model size:", len(tflite_model), "bytes")