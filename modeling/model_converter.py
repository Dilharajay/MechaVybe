from pathlib import Path


MODEL_PATH = Path("model/model.tflite")
OUTPUT_PATH = Path("../firmware/src/model.h")



model_data = MODEL_PATH.read_bytes()


with OUTPUT_PATH.open("w") as f:

    f.write("#pragma once\n\n")

    f.write("#include <cstdint>\n\n")

    f.write("alignas(16) const unsigned char g_model[] = {\n")


    for i in range(0, len(model_data), 12):

        chunk = model_data[i:i + 12]

        values = ", ".join(
            f"0x{byte:02x}"
            for byte in chunk
        )

        f.write(f"    {values},\n")


    f.write("};\n\n")

    f.write(
        "const unsigned int g_model_len = "
        f"{len(model_data)};\n"
    )


print(f"Generated: {OUTPUT_PATH}")
print(f"Model size: {len(model_data)} bytes")