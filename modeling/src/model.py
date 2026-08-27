import tensorflow as tf

def build_autoencoder(input_dim: int) -> tf.keras.Model:
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(input_dim,)),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(16, activation="relu"),
        tf.keras.layers.Dense(8, activation="relu", name="bottleneck"), # Compression
        tf.keras.layers.Dense(16, activation="relu"),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(input_dim, activation="linear") # Reconstruct original FFT
    ])

    model.compile(optimizer="adam", loss="mse")
    return model
