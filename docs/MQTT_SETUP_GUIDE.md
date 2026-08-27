# MechaVybe: End-to-End MQTT Setup Guide

This guide explains how to fully configure the MechaVybe ecosystem (ESP32 Firmware, PC Application, and Node-RED) to communicate via MQTT for real-time anomaly alerts.

---

## 1. The MQTT Architecture

Unlike the raw vibration data (which streams via high-bandwidth UDP), **MQTT is used exclusively for lightweight anomaly alerts**. 
When the ESP32 is running the Edge ML model (`esp32-s3-prod` environment or `MODE:1`), it calculates an anomaly score. If that score exceeds the threshold, it connects to your MQTT broker and publishes a JSON alert.

* **Rate Limiting:** The ESP32 enforces a strict limit of **1 message per 10 seconds** to prevent broker flooding.
* **Payload Format:** `{"id": "<device_id>", "status": "anomaly", "score": <float>}`
* **Default Topic:** `mechavybe/status` (customizable)

---

## 2. Choosing an MQTT Broker

You need a broker to route the messages. You have two main options:

### Option A: Local Broker (Mosquitto)
Best for factory floors or completely offline setups.
1. Install [Eclipse Mosquitto](https://mosquitto.org/download/).
2. Start the service. Your Broker IP will be the IPv4 address of the computer running Mosquitto (e.g., `192.168.1.50`).
3. Port: `1883`

### Option B: Cloud Broker (HiveMQ Public)
Best for quick testing over the internet without firewall port-forwarding.
* **Server:** `broker.hivemq.com`
* **Port:** `1883`

---

## 3. Configuring the ESP32

To configure the hardware, connect the ESP32-S3 via USB and open a Serial Terminal (like PuTTY, Arduino Serial Monitor, or PlatformIO Monitor) set to **921600 baud**.

### Step 3.1: Connect to Wi-Fi
The ESP32 must be on a network that can reach the broker. Type the following command and hit Enter:
```
WIFI:YourSSID:YourPassword
```
*The device will save these to NVS (Non-Volatile Storage) and reboot.*

### Step 3.2: Set the MQTT Credentials
Type the following command using spaces to separate the arguments:
```
MQTT <server_ip> <port> <topic>
```
**Example (Local):** `MQTT 192.168.1.50 1883 mechavybe/status`
**Example (Cloud):** `MQTT broker.hivemq.com 1883 mechavybe/status`

### Step 3.3: Enter Inference Mode
MQTT alerts are *only* published when the model is actively predicting. 
If you flashed the default `esp32-s3` environment, you must switch out of Data Collection mode:
```
MODE:1
```
*(Note: If you flashed the `esp32-s3-prod` environment, this step is unnecessary as the device is permanently locked into inference mode).*

### Step 3.4: Verify the LED
The built-in NeoPixel LED gives you the network status at a glance:
* 🟨 **Yellow:** Connecting to Wi-Fi / Trying to Reconnect
* 🟩 **Green:** Inference Mode (Healthy)
* 🟥 **Red:** Inference Mode (Anomaly Detected!)
* 🟧 **Orange (Flashing):** Inference Mode but **MQTT is Offline/Disconnected**

---

## 4. Configuring the PC Application

The MechaVybe PC App includes a "Live Prediction Status" dashboard that listens to the MQTT broker.

1. Launch `MechaVybe.exe` (or `uv run main.py`).
2. On the **Dashboard** tab, locate the **MQTT Settings** box on the left sidebar.
3. Enter the exact same Server IP and Port you gave the ESP32.
4. Click **Start Listener**.
5. The UI will stay green ("HEALTHY") until it receives an anomaly payload over MQTT. When it does, it will flash **Red** and display the Node ID and Score. It will automatically revert to Green after 12 seconds of silence.

---

## 5. Configuring Node-RED for Automation

If you want to trigger emails, PLCs, or Telegram alerts when an anomaly occurs, use Node-RED.

Please refer to the `NODE_RED_MQTT_GUIDE.md` located in the `docs/` folder for the full JSON flow block that parses the `{"id": "node-1", "status": "anomaly", "score": 1.254}` payload and displays it on a dashboard gauge.
