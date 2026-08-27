# MechaVybe: Data Collection & Model Training Guideline

This guide explains how to properly collect "healthy" baseline vibration data using the hardware and PC application, and how to seamlessly push that data into the machine learning pipeline to generate your anomaly detection model.

Because our model uses an **Unsupervised Autoencoder**, you *only* need to collect data from the machine when it is operating normally (healthy).

---

## 1. Hardware Setup & Sensor Mounting

Accurate anomaly detection relies completely on the quality of the mechanical coupling between the MPU6050 sensor and the machine.

### 1.1 Mounting Best Practices
* **Rigid Coupling:** Do NOT use double-sided tape or weak adhesives. Mount the MPU6050 using screws, cyanoacrylate (superglue), or a magnetic base onto a solid, non-resonant part of the machine chassis.
* **Location:** Mount the sensor as close to the load-bearing components as possible (e.g., directly on the bearing housing or motor casing).
* **Axis Alignment:** Align the Z-axis (usually perpendicular to the PCB) with the primary direction of expected vibration (e.g., radial to the shaft).

### 1.2 Wiring and Power
* Connect the MPU6050 to the ESP32-S3 via I2C (SDA, SCL) using short wires to prevent electrical noise.
* Ensure the ESP32-S3 is powered by a stable 5V source. If using Wi-Fi UDP streaming, ensure the ESP32 and the PC are on the same local network.

---

## 2. Software Configuration (PC App)

Once the hardware is mounted and the machine is running in a known **healthy** state:

1. Launch the PC Application:
   ```powershell
   cd pc_app
   uv run main.py
   ```
2. Connect to the ESP32-S3 via the **Dashboard** tab (select your Serial port or use UDP).
3. Verify that the live FFT and time-domain graphs look clean and stable.
4. **Configure Metadata:** In the Configuration panel, ensure the following fields are set correctly:
   * **Machine ID:** E.g., `Motor_A_Pump`
   * **Condition:** MUST be set to `healthy`. (The ML pipeline explicitly looks for this folder).
   * **Session ID:** E.g., `baseline_001`

---

## 3. Data Collection Procedure

To build a robust baseline model, the autoencoder needs to see the full range of *normal* operational variance.

1. **Warm-up:** Let the machine run for 10-15 minutes to reach steady-state thermal and mechanical operating conditions.
2. **Start Recording:** Click the **Start Recording** button in the PC App.
3. **Capture Variations:** While recording, allow the machine to experience normal load fluctuations. If the machine cycles between 80% and 100% load during normal operation, ensure the recording captures these cycles.
4. **Duration:** Record at least **5 to 10 minutes** of healthy baseline data. 
5. **Stop Recording:** Click **Stop Recording**. 

The app will seamlessly save the data in the optimized Apache Parquet format to:
`pc_app/dataset/<Machine_ID>/healthy/session_<ID>/`

---

## 4. Seamless Model Training

The `modeling` module is designed to directly ingest the data you just recorded from the PC app without any manual file moving.

1. Open a terminal and start the Dagster Orchestration UI:
   ```powershell
   cd modeling
   uv run dagster dev
   ```
2. Open your browser and navigate to **http://localhost:3000**.
3. Go to the **Assets** tab. You will see a 4-step pipeline:
   `raw_signal` → `training_features` → `trained_autoencoder` → `exported_model`
4. Click **Materialize All**.
   * The pipeline will automatically scan the `pc_app/dataset/` directory.
   * It will explicitly filter for the `healthy` subdirectories and load your new parquet files.
   * It will extract the FFT features, train the Autoencoder, calculate the 99th percentile anomaly threshold, and export the INT8 TFLite model.

---

## 5. Experiment Tracking (Optional)

If you want to compare different baselines or see how the anomaly threshold changes as you collect more data, you can view the MLflow dashboard:

```powershell
cd modeling
uv run mlflow ui
```
Navigate to **http://localhost:5000** to see all your historical training runs, reconstruction losses, and thresholds.

---

## 6. Deploying the Model to Hardware

The final Dagster step (`exported_model`) automatically generates a self-contained C header file at `modeling/model/model.h`.

To deploy your new anomaly detection model to the edge device:

1. Copy the generated header over to the firmware:
   ```powershell
   copy modeling\model\model.h firmware\include\model.h
   ```
2. Recompile and flash the ESP32-S3:
   ```powershell
   cd firmware
   idf.py build flash
   ```

The ESP32-S3 is now running **live anomaly detection** on-device! If the machine's vibration profile deviates significantly from the baseline you recorded, the firmware will flag an anomaly.
