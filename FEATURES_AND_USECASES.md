# MECHAVYBE: Features, Use Cases, and Philosophy

## 1. Why MECHAVYBE Exists (The Problem & The Solution)

### The Problem
Industrial machinery (motors, pumps, compressors, fans, CNC spindles) vibrate naturally as they operate. However, changes in these vibration patterns are the earliest and most reliable indicators of impending mechanical failure. 
Historically, Condition Monitoring Systems (CMS) have been overwhelmingly expensive, often costing tens of thousands of dollars per machine. They rely on proprietary hardware (piezoelectric sensors, DAQ racks), closed-source software, and expensive licensing fees. Furthermore, modern engineers and data scientists looking to deploy **Edge AI** (Machine Learning directly on the sensor) often find that commercial systems do not allow access to raw, unadulterated time-series data, nor do they provide a pathway to upload custom models back to the edge device.

### The Solution
**MECHAVYBE** was created to bridge this gap. It provides a completely open-source, end-to-end predictive maintenance pipeline using ultra-low-cost, off-the-shelf hardware (a ~$10 ESP32-S3 and an MPU6050/ADXL345). It is designed to give researchers, maintenance technicians, and engineers a professional-grade software suite to acquire high-speed vibration data, apply complex signal processing in real-time, train machine learning models seamlessly, and push those models back to the edge.

---

## 2. Comprehensive Software Features (PC Application)

The MECHAVYBE desktop application (built in Python and PyQt6) serves as the central command hub.

### 🔴 High-Performance Data Acquisition & Storage
* **Dual-Interface Streaming:** Supports both ultra-fast USB Serial (921,600 baud) and wireless Wi-Fi UDP streaming for remote or moving machinery.
* **Apache Parquet Data Logging:** Records raw, unadulterated time-series data using the highly compressed columnar Parquet format, which is optimized for machine learning and Big Data ingestion.
* **Dynamic JSON Metadata Tagging:** Allows users to create custom metadata profiles to tag recordings (e.g., tagging a recording with `machine_id: CNC_Spindle`, `condition: healthy`, `load: 80%`).

### 📈 Responsive & Live Visualization
* **Split-Pane UI:** A fully responsive interface featuring a `QSplitter` that allows users to independently resize the configuration panels versus the live graphing areas.
* **High-Speed Plotting:** Utilizes PyqtGraph and zero-copy deque buffers to render 6,000+ data points per second (6 axes @ 1kHz) without lagging the UI thread.
* **Live Spectrogram:** A real-time waterfall plot (heatmap) that visualizes the evolution of the frequency spectrum over time, making it easy to spot transient anomalies like intermittent rubbing.

### 🧮 Digital Signal Processing (DSP) & Frequency Analysis
* **Configurable Butterworth Filters:** Apply Low-pass, High-pass, Band-pass, or Band-stop filters on the fly (up to 10th order) to isolate specific mechanical frequencies.
* **Mains Interference Rejection:** Built-in Notch filters to remove 50Hz or 60Hz electrical noise.
* **Real-Time FFT (Fast Fourier Transform):** Live frequency domain analysis with selectable block sizes (256 to 4096) and windowing functions (Hanning, Hamming, Blackman, Rectangular).
* **Switchable Spectral Modes:** View data as raw Magnitude or Power Spectral Density (PSD) using Welch's method.

### ⚙️ Live Diagnostic Metrics
Calculates standard ISO 10816 vibration metrics in real-time:
* **Time-Domain:** RMS (Overall Severity), Peak Amplitude, Peak-to-Peak, and Crest Factor (Impulsiveness).
* **Frequency-Domain:** Dominant Frequency, 2nd/3rd Harmonics, Spectral Centroid, and targeted Band Power.

---

## 3. Comprehensive Edge ML Features (Dagster & TensorFlow)

The ML pipeline handles the transition from raw data to a deployed Edge AI model.

* **Seamless Dagster Orchestration:** The pipeline automatically reads the PC App's directory structure, locating all files tagged as `healthy` to build a baseline dataset without manual file manipulation.
* **Unsupervised Anomaly Detection:** Uses a Keras Autoencoder. Because it is unsupervised, you do *not* need to damage your machine to collect "faulty" data. The model learns the normal frequency fingerprint and flags anything that deviates from it.
* **Automated Thresholding:** Automatically calculates a 99th-percentile Mean Squared Error (MSE) boundary based on the training data to act as the trigger for anomalies.
* **MLflow Tracking:** Provides a web UI to track experiment parameters, reconstruction loss curves, and anomaly thresholds across multiple training runs.
* **INT8 Quantization & C-Header Export:** Compresses the 32-bit floating-point neural network into an 8-bit integer format suitable for microcontrollers. It automatically generates a self-contained `model.h` C header file that gets compiled directly into the ESP32 firmware.

---

## 4. Comprehensive Hardware Features (Firmware)

The ESP32-S3 firmware is written in C++ (PlatformIO) and acts as the brain of the edge node.

* **Deterministic Hardware Timers:** Uses hardware interrupts to guarantee precise sampling rates (up to 1kHz) with minimal jitter.
* **Hardware Anti-Aliasing:** Configures the sensor's internal Digital Low Pass Filter (DLPF) to cleanly attenuate frequencies above the Nyquist limit.
* **Binary Packet Protocol:** To prevent serial bottlenecks, data is packed into highly efficient binary structs containing a header, sequence ID, timestamp, 50-sample arrays, and a CRC16 checksum for data integrity.
* **NVS (Non-Volatile Storage):** Saves configuration states (Wi-Fi credentials, calibration offsets, sampling rates, sensor ranges) to flash memory so the device boots up correctly without needing the PC.
* **On-Device TFLite Micro Inference:** The ESP32 executes the quantized TensorFlow model in real-time. It analyzes the FFT spectrum on the edge and can trigger an alert (via the NeoPixel LED or UDP) immediately when an anomaly occurs.

---

## 5. Detailed Use Cases

### A. Predictive Maintenance of Rotating Equipment
* **Rotor Imbalance:** The software's live FFT can instantly identify heavy 1x RPM peaks, indicating that a fan blade or motor rotor is out of balance.
* **Shaft Misalignment:** By observing the live 2x and 3x RPM harmonics in the PC app, technicians can detect angular or parallel misalignment between a motor and a pump.
* **Mechanical Looseness:** The Spectrogram will show a suddenly elevated "noise floor" and multiple high-order harmonics if holding bolts become loose.

### B. Bearing Condition Monitoring
Rolling element bearings typically fail at very high frequencies before low-frequency vibrations become apparent.
* Using the MECHAVYBE PC App, an engineer can apply a **High-Pass Filter** (e.g., >200Hz) to remove the motor's running speed.
* They can monitor the **Crest Factor**. A Crest Factor rising above 3.5 strongly indicates microscopic pitting on the bearing races (impulsive impacts).

### C. End-of-Line Quality Assurance (Manufacturing)
Instead of relying on human inspectors to "listen" to a newly manufactured motor to see if it sounds right:
1. Record 10 known-good motors using the MECHAVYBE app.
2. Train the Autoencoder pipeline.
3. Deploy the model to an ESP32 mounted at the end of the assembly line.
4. If a newly built motor has a grinding bearing, the ESP32's on-device inference will yield a high Reconstruction Error and light up the NeoPixel LED red, automatically rejecting the part.

### D. Structural Resonance Testing (Run-Up / Coast-Down)
When a machine speeds up, it passes through various frequencies. If the running speed matches the natural frequency of the metal frame, catastrophic resonance occurs.
* By using the **Spectrogram feature**, engineers can perform a coast-down test (cutting power and letting the motor spin to a stop). 
* The spectrogram will clearly show a bright horizontal band at the specific frequency where the machine's frame amplifies the vibration, allowing engineers to stiffen the structure or program the VFD (Variable Frequency Drive) to avoid that speed.

### E. Academic Research & Algorithm Prototyping
Because the MECHAVYBE pipeline logs data in open Apache Parquet format and uses standard Python/TensorFlow for modeling, University researchers can easily rip out the Autoencoder and replace it with novel algorithms (like 1D-CNNs, LSTMs, or Spiking Neural Networks) without having to reverse-engineer a proprietary commercial system.
