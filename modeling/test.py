from train import model_path
import tensorflow as tf
import numpy as np

# ---------------------------------------------------------
# 9. Test INT8 model with TFLite interpreter
# ---------------------------------------------------------

interpreter = tf.lite.Interpreter(
    model_path=str(model_path)
)

interpreter.allocate_tensors()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

print()
print("Input details:")
print(input_details)

print()
print("Output details:")
print(output_details)


def predict(x1, x2):

    sample = np.array(
        [[x1, x2]],
        dtype=np.float32,
    )

    input_info = input_details[0]

    scale = input_info["quantization"][0]
    zero_point = input_info["quantization"][1]

    quantized = np.round(
        sample / scale + zero_point
    ).astype(np.int8)

    interpreter.set_tensor(
        input_info["index"],
        quantized,
    )

    interpreter.invoke()

    output_info = output_details[0]

    output_quantized = interpreter.get_tensor(
        output_info["index"]
    )

    output_scale = output_info["quantization"][0]
    output_zero_point = output_info["quantization"][1]

    output = (
        output_quantized.astype(np.float32)
        - output_zero_point
    ) * output_scale

    return float(output[0][0])


print()
print("INT8 model tests:")

tests = [
    (0.1, 0.2),
    (0.2, 0.4),
    (0.4, 0.5),
    (0.6, 0.6),
    (0.8, 0.7),
    (0.9, 0.9),
]

for x1, x2 in tests:

    prediction = predict(x1, x2)

    predicted_class = int(
        prediction >= 0.5
    )

    print(
        f"{x1:.2f} + {x2:.2f} "
        f"-> {prediction:.4f} "
        f"class={predicted_class}"
    )