#include <Arduino.h>

#include <esp_heap_caps.h>

#include "model.h"

// --- Binary Protocol Definitions ---
#pragma pack(push, 1)
struct SensorData {
    float ax, ay, az;
    float gx, gy, gz;
};

#define BATCH_SIZE 50

struct BinaryPacket {
    uint16_t header;       // 0xAABB
    uint32_t sequence;
    uint32_t timestamp_us;
    float rpm;
    float voltage;
    float current;
    uint8_t sample_count;
    SensorData samples[BATCH_SIZE];
    uint16_t crc;
};
#pragma pack(pop)

BinaryPacket tx_packet;
uint32_t sample_sequence = 0;

volatile uint32_t rpm_pulse_count = 0;
uint32_t last_rpm_time = 0;

void IRAM_ATTR rpm_isr() {
    rpm_pulse_count++;
}

#include "ota_manager.h"
#include "imu_manager.h"
#include "led_manager.h"
#include "config.h"
#include "nvs_manager.h"
#include "logger.h"

#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/schema/schema_generated.h"

#include <WiFi.h>
#include <WiFiUdp.h>
#include <PubSubClient.h>

namespace
{

const tflite::Model* model = nullptr;

tflite::MicroInterpreter* interpreter = nullptr;

TfLiteTensor* input = nullptr;

TfLiteTensor* output = nullptr;


// ---------------------------------------------------------
// Tensor arena
// ---------------------------------------------------------

uint8_t* tensor_arena = nullptr;

// ---------------------------------------------------------
// UDP Streaming
// ---------------------------------------------------------

WiFiUDP udpServer;
bool udpStarted = false;
IPAddress udpClientIp;
uint16_t udpClientPort = 0;
bool udpInitialized = false;


// ---------------------------------------------------------
// Resolver
// ---------------------------------------------------------

tflite::MicroMutableOpResolver<3> resolver;


} // namespace


OtaManager ota;
ImuManager imu;
LedManager statusLed;
NvsManager nvs;

WiFiClient espClient;
PubSubClient mqttClient(espClient);

uint32_t last_pc_msg = 0;
#ifdef INFERENCE_ONLY_MODE
static const bool predictionMode = true;
#else
bool predictionMode = false; // 0 = Logger, 1 = Prediction
#endif
bool buttonPressed = false;
uint32_t buttonPressTime = 0;
bool cli_logs_enabled = false;
float last_prediction_score = 0.0;
int last_predicted_class = 0;
String currentMqttServer;

void processSerial() {
    if (Serial.available()) {
        String cmd = Serial.readStringUntil('\n');
        cmd.trim();
        last_pc_msg = millis(); // Track that PC is actively communicating
        
        // Convert to uppercase for CLI commands, but keep original for exact matching on others
        String cmdUpper = cmd;
        cmdUpper.toUpperCase();

        if (cmdUpper == "HELP") {
            Serial.println("=== MECHAVYBE CLI ===");
            Serial.println("STATUS       : Show device and prediction status");
            Serial.println("MODE 0       : Switch to Data Collection Mode");
            Serial.println("MODE 1       : Switch to Inference Mode");
            Serial.println("LOG ON       : Stream predictions to Serial");
            Serial.println("LOG OFF      : Stop streaming predictions");
            Serial.println("WIFI <S> <P> : Set Wi-Fi credentials");
            Serial.println("MQTT <S> <P> <T> : Set MQTT config");
            return;
        } else if (cmdUpper == "STATUS") {
            Serial.println("=== STATUS ===");
            Serial.printf("Mode         : %s\n", predictionMode ? "INFERENCE" : "DATA COLLECTION");
            Serial.printf("Wi-Fi        : %s (SSID: %s)\n", WiFi.status() == WL_CONNECTED ? "CONNECTED" : "DISCONNECTED", nvs.getWifiSsid().c_str());
            Serial.printf("MQTT         : %s (%s:%d)\n", mqttClient.connected() ? "CONNECTED" : "DISCONNECTED", nvs.getMqttServer().c_str(), nvs.getMqttPort());
            if (predictionMode) {
                Serial.printf("Last Pred    : %.4f [%s]\n", last_prediction_score, last_predicted_class == 1 ? "ANOMALY" : "HEALTHY");
            }
            return;
        } else if (cmdUpper == "LOG ON") {
            cli_logs_enabled = true;
            Serial.println("Prediction logging ENABLED.");
            return;
        } else if (cmdUpper == "LOG OFF") {
            cli_logs_enabled = false;
            Serial.println("Prediction logging DISABLED.");
            return;
        } else if (cmdUpper == "MODE 0") {
            cmd = "MODE:0";
        } else if (cmdUpper == "MODE 1") {
            cmd = "MODE:1";
        } else if (cmdUpper.startsWith("WIFI ")) {
            // WIFI <ssid> <pwd> -> map to WIFI:<ssid>:<pwd>
            int space1 = cmd.indexOf(' ');
            int space2 = cmd.indexOf(' ', space1 + 1);
            if (space1 > 0 && space2 > 0) {
                cmd = "WIFI:" + cmd.substring(space1+1, space2) + ":" + cmd.substring(space2+1);
            }
        } else if (cmdUpper.startsWith("MQTT ")) {
            // MQTT <server> <port> <topic> -> map to SET:MQTT:<server>,<port>,<topic>
            int space1 = cmd.indexOf(' ');
            int space2 = cmd.indexOf(' ', space1 + 1);
            int space3 = cmd.indexOf(' ', space2 + 1);
            if (space1 > 0 && space2 > 0 && space3 > 0) {
                cmd = "SET:MQTT:" + cmd.substring(space1+1, space2) + "," + cmd.substring(space2+1, space3) + "," + cmd.substring(space3+1);
            }
        }

        if (predictionMode && !cmd.startsWith("MODE:") && cmd != "PING") {
            Serial.println("WARNING: Device is in Prediction Mode. Data collection is disabled.");
            return;
        }

        if (cmd.startsWith("WIFI:")) {
            int firstColon = cmd.indexOf(':');
            int secondColon = cmd.indexOf(':', firstColon + 1);
            if (firstColon > 0 && secondColon > 0) {
                String ssid = cmd.substring(firstColon + 1, secondColon);
                String pwd = cmd.substring(secondColon + 1);
                nvs.setWifiCredentials(ssid, pwd);
                Logger::info("Credentials updated. Rebooting...");
                delay(1000);
                ESP.restart();
            }
        } else if (cmd.startsWith("MODE:")) {
            int mode = cmd.substring(5).toInt();
#ifndef INFERENCE_ONLY_MODE
            predictionMode = (mode == 1);
#endif
            Logger::info("Mode set to %d", mode);
            if (!predictionMode) {
                statusLed.setDataCollection(); // Explicit Cyan for Data Collection
            } else {
                statusLed.setModeSwitching(); // Will turn Green when inference runs
            }
        } else if (cmd.startsWith("SET:RATE:")) {
            int rate = cmd.substring(9).toInt();
            nvs.setSampleRate(rate);
            imu.setSampleRate(rate);
            Logger::info("Sample rate set to %d Hz", rate);
        } else if (cmd.startsWith("SET:SENSOR:")) {
            String sensor = cmd.substring(11);
            nvs.setSensorType(sensor);
            Logger::info("Sensor type set to %s. Rebooting...", sensor.c_str());
            delay(1000);
            ESP.restart();
        } else if (cmd.startsWith("SET:ID:")) {
            String id = cmd.substring(7);
            nvs.setDeviceId(id);
            Logger::info("Device ID set to %s", id.c_str());
        } else if (cmd.startsWith("SET:ACCEL:")) {
            int range = cmd.substring(10).toInt();
            nvs.setAccelRange(range);
            imu.setRanges(range, nvs.getGyroRange());
            Logger::info("Accel range set to %d G", range);
        } else if (cmd.startsWith("SET:GYRO:")) {
            int range = cmd.substring(9).toInt();
            nvs.setGyroRange(range);
            imu.setRanges(nvs.getAccelRange(), range);
            Logger::info("Gyro range set to %d deg/s", range);
        } else if (cmd == "CMD:CALIBRATE") {
            imu.calibrate();
            nvs.setCalibration(imu.offsetAx, imu.offsetAy, imu.offsetAz, 
                               imu.offsetGx, imu.offsetGy, imu.offsetGz);
            Logger::info("Calibration saved to NVS.");
        } else if (cmd.startsWith("SET:CALIBA:")) {
            // SET:CALIBA:ox,oy,oz,sx,sy,sz
            int ptr1 = cmd.indexOf(',', 11);
            int ptr2 = cmd.indexOf(',', ptr1 + 1);
            int ptr3 = cmd.indexOf(',', ptr2 + 1);
            int ptr4 = cmd.indexOf(',', ptr3 + 1);
            int ptr5 = cmd.indexOf(',', ptr4 + 1);
            if (ptr1 > 0 && ptr5 > 0) {
                imu.offsetAx = cmd.substring(11, ptr1).toFloat();
                imu.offsetAy = cmd.substring(ptr1+1, ptr2).toFloat();
                imu.offsetAz = cmd.substring(ptr2+1, ptr3).toFloat();
                imu.scaleAx = cmd.substring(ptr3+1, ptr4).toFloat();
                imu.scaleAy = cmd.substring(ptr4+1, ptr5).toFloat();
                imu.scaleAz = cmd.substring(ptr5+1).toFloat();
                nvs.setCalibration(imu.offsetAx, imu.offsetAy, imu.offsetAz, imu.offsetGx, imu.offsetGy, imu.offsetGz);
                nvs.setAccelScale(imu.scaleAx, imu.scaleAy, imu.scaleAz);
                Logger::info("Manual calibration applied and saved!");
            }
        } else if (cmd.startsWith("SET:MQTT:")) {
            // SET:MQTT:<server>,<port>,<topic>
            int ptr1 = cmd.indexOf(',', 9);
            int ptr2 = cmd.indexOf(',', ptr1 + 1);
            if (ptr1 > 0 && ptr2 > 0) {
                String server = cmd.substring(9, ptr1);
                int port = cmd.substring(ptr1 + 1, ptr2).toInt();
                String topic = cmd.substring(ptr2 + 1);
                nvs.setMqttConfig(server, port, topic);
                currentMqttServer = server;
                mqttClient.setServer(currentMqttServer.c_str(), port);
                Logger::info("MQTT config applied and saved!");
            }
        } else if (cmd == "GET:INFO") {
            // Send JSON info
            String info = "INFO:{\"id\":\"" + nvs.getDeviceId() + "\"," +
                          "\"fw\":\"1.0.0\"," +
                          "\"sensor\":\"" + nvs.getSensorType() + "\"," +
                          "\"heap\":" + String(ESP.getFreeHeap()) + "," +
                          "\"rate\":" + String(nvs.getSampleRate()) + "," +
                          "\"accel\":" + String(nvs.getAccelRange()) + "," +
                          "\"gyro\":" + String(nvs.getGyroRange()) + "," +
                          "\"mqtt_server\":\"" + nvs.getMqttServer() + "\"," +
                          "\"mqtt_port\":" + String(nvs.getMqttPort()) + "," +
                          "\"mqtt_topic\":\"" + nvs.getMqttTopic() + "\"," +
                          "\"calib_ax\":" + String(imu.offsetAx) + "," +
                          "\"calib_ay\":" + String(imu.offsetAy) + "," +
                          "\"calib_az\":" + String(imu.offsetAz) + "," +
                          "\"calib_gx\":" + String(imu.offsetGx) + "," +
                          "\"calib_gy\":" + String(imu.offsetGy) + "," +
                          "\"calib_gz\":" + String(imu.offsetGz) + "," +
                          "\"scale_ax\":" + String(imu.scaleAx) + "," +
                          "\"scale_ay\":" + String(imu.scaleAy) + "," +
                          "\"scale_az\":" + String(imu.scaleAz) + "}";
            Serial.println(info);
        } else if (cmd == "PING") {
            // Heartbeat received
        }
    }
}

void setup() {
    Logger::begin();
    delay(Config::BOOT_DELAY_MS); // Wait for serial monitor

    if (Config::RPM_PIN >= 0) {
        pinMode(Config::RPM_PIN, INPUT_PULLUP);
        attachInterrupt(digitalPinToInterrupt(Config::RPM_PIN), rpm_isr, FALLING);
        last_rpm_time = micros();
    }
    if (Config::VOLTAGE_PIN >= 0) {
        pinMode(Config::VOLTAGE_PIN, INPUT);
    }
    if (Config::CURRENT_PIN >= 0) {
        pinMode(Config::CURRENT_PIN, INPUT);
    }

    pinMode(Config::BUTTON_PIN, INPUT_PULLUP);
    
    // Initialize Status LED
    statusLed.begin();
    statusLed.setWifiConnecting(); // Yellow during boot/connect

    // Initialize NVS
    nvs.begin();
    
    String ssid = nvs.getWifiSsid();
    String pwd = nvs.getWifiPassword();
    if (ssid == "") {
        ssid = Config::WIFI_SSID;
        pwd = Config::WIFI_PASSWORD;
    }
    
    currentMqttServer = nvs.getMqttServer();
    if (currentMqttServer == "") currentMqttServer = Config::MQTT_SERVER;
    int mqttPort = nvs.getMqttPort();
    if (mqttPort == 0) mqttPort = Config::MQTT_PORT;
    
    mqttClient.setServer(currentMqttServer.c_str(), mqttPort);
    
    // Initialize OTA with status LED
    ota.begin(ssid.c_str(), pwd.c_str(), Config::OTA_HOSTNAME, &statusLed);

    // Initialize IMU and load NVS configs
    imu.begin(nvs.getSensorType());
    imu.setSampleRate(nvs.getSampleRate());
    imu.setRanges(nvs.getAccelRange(), nvs.getGyroRange());
    nvs.getCalibration(imu.offsetAx, imu.offsetAy, imu.offsetAz, 
                       imu.offsetGx, imu.offsetGy, imu.offsetGz);
    nvs.getAccelScale(imu.scaleAx, imu.scaleAy, imu.scaleAz);

    Logger::info("");
    Logger::info("==============================");
    Logger::info(" ESP32-S3 TinyML Test");
    Logger::info("==============================");


    // -----------------------------------------------------
    // Memory information
    // -----------------------------------------------------

    Logger::info(
        "Free heap      : %u bytes",
        ESP.getFreeHeap()
    );

    Logger::info(
        "Free PSRAM     : %u bytes",
        ESP.getFreePsram()
    );

    Logger::info(
        "Flash size     : %u bytes",
        ESP.getFlashChipSize()
    );


    // -----------------------------------------------------
    // Allocate tensor arena
    // -----------------------------------------------------

    tensor_arena = static_cast<uint8_t*>(
        heap_caps_malloc(
            Config::TENSOR_ARENA_SIZE,
            MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT
        )
    );


    if (tensor_arena == nullptr)
    {
        Serial.println(
            "ERROR: Tensor arena allocation failed"
        );

        return;
    }


    Logger::info(
        "Tensor arena   : %u bytes",
        Config::TENSOR_ARENA_SIZE
    );


    // -----------------------------------------------------
    // Load model
    // -----------------------------------------------------

    model = tflite::GetModel(g_model);


    if (model == nullptr)
    {
        Serial.println(
            "ERROR: Could not load model"
        );

        return;
    }


    Logger::info(
        "TFLite schema  : %d",
        model->version()
    );


    if (model->version() != TFLITE_SCHEMA_VERSION)
    {
        Serial.println(
            "ERROR: Unsupported TFLite schema version"
        );

        return;
    }


    // -----------------------------------------------------
    // Register required operators
    // -----------------------------------------------------

    if (
        resolver.AddFullyConnected()
        != kTfLiteOk
    )
    {
        Serial.println(
            "ERROR: AddFullyConnected failed"
        );

        return;
    }


    if (
        resolver.AddRelu()
        != kTfLiteOk
    )
    {
        Serial.println(
            "ERROR: AddRelu failed"
        );

        return;
    }


    if (
        resolver.AddLogistic()
        != kTfLiteOk
    )
    {
        Serial.println(
            "ERROR: AddLogistic failed"
        );

        return;
    }


    // -----------------------------------------------------
    // Create interpreter
    // -----------------------------------------------------

    static tflite::MicroInterpreter static_interpreter(
        model,
        resolver,
        tensor_arena,
        Config::TENSOR_ARENA_SIZE
    );


    interpreter = &static_interpreter;


    // -----------------------------------------------------
    // Allocate tensors
    // -----------------------------------------------------

    TfLiteStatus status =
        interpreter->AllocateTensors();


    if (status != kTfLiteOk)
    {
        Serial.println(
            "ERROR: AllocateTensors failed"
        );

        return;
    }


    // -----------------------------------------------------
    // Get input/output tensors
    // -----------------------------------------------------

    input = interpreter->input(0);

    output = interpreter->output(0);


    Logger::info("");
    Logger::info("Model loaded successfully");


    Logger::info(
        "Input type     : %d",
        input->type
    );

    Logger::info(
        "Input scale    : %f",
        input->params.scale
    );

    Logger::info(
        "Input zero     : %d",
        input->params.zero_point
    );

    Logger::info(
        "Output scale   : %f",
        output->params.scale
    );

    Logger::info(
        "Output zero    : %d",
        output->params.zero_point
    );


    Logger::info("");
    Logger::info("Ready for inference.");
}


float run_inference(
    float x1,
    float x2
)
{
    if (input == nullptr || output == nullptr)
    {
        Serial.println(
            "ERROR: Model not initialized"
        );

        return -1.0f;
    }

    // -----------------------------------------------------
    // Quantize input
    // -----------------------------------------------------

    const float scale =
        input->params.scale;

    const int zero_point =
        input->params.zero_point;


    int8_t q_x1 = static_cast<int8_t>(
        fmaxf(-128.0f, fminf(127.0f,
            roundf(x1 / scale) + zero_point
        ))
    );


    int8_t q_x2 = static_cast<int8_t>(
        fmaxf(-128.0f, fminf(127.0f,
            roundf(x2 / scale) + zero_point
        ))
    );


    input->data.int8[0] = q_x1;

    input->data.int8[1] = q_x2;


    // -----------------------------------------------------
    // Run inference
    // -----------------------------------------------------

    uint32_t start = micros();


    TfLiteStatus status =
        interpreter->Invoke();


    uint32_t elapsed =
        micros() - start;


    if (status != kTfLiteOk)
    {
        Serial.println(
            "ERROR: Invoke failed"
        );

        return -1.0f;
    }


    // -----------------------------------------------------
    // Dequantize output
    // -----------------------------------------------------

    int8_t q_output =
        output->data.int8[0];


    float prediction =
        (
            q_output
            - output->params.zero_point
        )
        * output->params.scale;


    // -----------------------------------------------------
    // Print benchmark
    // -----------------------------------------------------

    Logger::info(
        "Inference: %.3f ms",
        elapsed / 1000.0f
    );


    return prediction;
}


void loop()
{
    // Update non-blocking LED blinking patterns
    statusLed.update();

    // Handle BOOT button for mode switching
    int btnState = digitalRead(Config::BUTTON_PIN);
    if (btnState == LOW) { // Button is pressed (active low)
        if (!buttonPressed) {
            buttonPressed = true;
            buttonPressTime = millis();
        } else if (millis() - buttonPressTime > 1500) { // 1.5s long press
#ifndef INFERENCE_ONLY_MODE
            predictionMode = !predictionMode;
            statusLed.setModeSwitching();
            Logger::info("Mode switched via button to: %s", predictionMode ? "Inference" : "Data Collection");
            delay(1000); // Wait 1s to show the magenta LED and debounce
            buttonPressed = false;
            
            if (!predictionMode) {
                // Restore LED to Data Collection mode explicitly
                statusLed.setDataCollection();
            }
#else
            Logger::info("Mode switching disabled in INFERENCE_ONLY_MODE");
            delay(1000);
            buttonPressed = false;
#endif
        }
    } else {
        buttonPressed = false;
    }

    // PC Connectivity tracking (needs heartbeat within 3 seconds)
    static bool lastPcConnected = false;
    bool pcConnected = (Serial && (millis() - last_pc_msg < 3000));
    
    if (pcConnected != lastPcConnected) {
        lastPcConnected = pcConnected;
        if (pcConnected && !predictionMode) {
            statusLed.setDataCollection();
            Logger::info("PC Connected!");
        } else if (!predictionMode) {
            statusLed.setDataCollection();
            Logger::info("PC Disconnected.");
        }
    }

    if (WiFi.status() == WL_CONNECTED) {
        if (!udpInitialized) {
            udpServer.begin(4242);
            udpInitialized = true;
            Logger::info("UDP Server listening on port 4242");
        }
        
        int packetSize = udpServer.parsePacket();
        if (packetSize) {
            char buf[32];
            int len = udpServer.read(buf, sizeof(buf)-1);
            if (len > 0) {
                buf[len] = 0;
                String msg = String(buf);
                if (msg.startsWith("START_STREAM")) {
                    if (predictionMode) {
                        udpServer.beginPacket(udpServer.remoteIP(), udpServer.remotePort());
                        udpServer.print("WARNING: Device is in Prediction Mode.\n");
                        udpServer.endPacket();
                    } else {
                        udpClientIp = udpServer.remoteIP();
                        udpClientPort = udpServer.remotePort();
                        udpStarted = true;
                        Logger::info("UDP Stream started to %s:%d", udpClientIp.toString().c_str(), udpClientPort);
                    }
                } else if (msg.startsWith("STOP_STREAM")) {
                    udpStarted = false;
                    Logger::info("UDP Stream stopped");
                }
            }
        }
    } else {
        udpInitialized = false;
        udpStarted = false;
    }

    processSerial();
    ota.handle();

    // Check for new IMU data
    if (imu.handle()) {
        sample_sequence++;
        
        if (tx_packet.sample_count == 0) {
            tx_packet.header = 0xBBAA; // 0xAABB transmitted Little Endian
            tx_packet.sequence = sample_sequence;
            tx_packet.timestamp_us = (uint32_t)micros();
        }
        
        SensorData& s = tx_packet.samples[tx_packet.sample_count];
        s.ax = imu.accelX;
        s.ay = imu.accelY;
        s.az = imu.accelZ;
        s.gx = imu.gyroX;
        s.gy = imu.gyroY;
        s.gz = imu.gyroZ;
        
        tx_packet.sample_count++;
        
        if (tx_packet.sample_count >= BATCH_SIZE) {
            // Read machine monitoring sensors
            if (Config::RPM_PIN >= 0) {
                uint32_t now = micros();
                float dt = (now - last_rpm_time) / 1000000.0f; // seconds
                if (dt > 0) {
                    uint32_t pulses = rpm_pulse_count;
                    rpm_pulse_count = 0;
                    tx_packet.rpm = (pulses / Config::RPM_PULSES_PER_REV) * (60.0f / dt);
                }
                last_rpm_time = now;
            } else {
                tx_packet.rpm = -1.0f;
            }

            if (Config::VOLTAGE_PIN >= 0) {
                tx_packet.voltage = analogRead(Config::VOLTAGE_PIN) * Config::VOLTAGE_SCALE;
            } else {
                tx_packet.voltage = -1.0f;
            }

            if (Config::CURRENT_PIN >= 0) {
                tx_packet.current = analogRead(Config::CURRENT_PIN) * Config::CURRENT_SCALE;
            } else {
                tx_packet.current = -1.0f;
            }

            // Calculate simple CRC16 (XOR sum for speed and basic integrity)
            uint16_t crc = 0;
            uint8_t* ptr = (uint8_t*)&tx_packet;
            for(size_t i = 0; i < sizeof(BinaryPacket) - 2; i++) {
                crc ^= ptr[i];
            }
            tx_packet.crc = crc;
            
            // Only stream raw data if we are NOT in prediction mode
            if (!predictionMode) {
                if (udpStarted && WiFi.status() == WL_CONNECTED) {
                    udpServer.beginPacket(udpClientIp, udpClientPort);
                    udpServer.write((uint8_t*)&tx_packet, sizeof(BinaryPacket));
                    udpServer.endPacket();
                } else {
                    Serial.write((uint8_t*)&tx_packet, sizeof(BinaryPacket));
                }
            }
            tx_packet.sample_count = 0;
        }
    }

    if (predictionMode) {
        if (WiFi.status() == WL_CONNECTED) {
            if (!mqttClient.connected()) {
                static uint32_t last_mqtt_try = 0;
                if (millis() - last_mqtt_try > 5000) {
                    last_mqtt_try = millis();
                    String clientId = "mechavybe-" + nvs.getDeviceId();
                    if (mqttClient.connect(clientId.c_str())) {
                        Logger::info("MQTT Connected to %s as %s", currentMqttServer.c_str(), clientId.c_str());
                    } else {
                        Logger::warn("MQTT Connection Failed.");
                    }
                }
            }
            if (mqttClient.connected()) {
                mqttClient.loop();
            }
        }

        if (interpreter == nullptr)
        {
            static uint32_t last_err_time = 0;
            if (millis() - last_err_time > Config::ERROR_DELAY_MS) {
                last_err_time = millis();
                Logger::info("Waiting for interpreter...");
            }
            return;
        }

        // Run inference every 500ms
        static uint32_t last_inference = 0;
        if (millis() - last_inference > 500) {
            last_inference = millis();
            
            // Note: In full deployment, this feeds the FFT of the batch to the model.
            // Here we run a dummy feed from instantaneous IMU data.
            float x1 = imu.accelX;
            float x2 = imu.accelY;
            
            float prediction = run_inference(x1, x2);
            int predicted_class = prediction >= Config::PREDICTION_THRESHOLD ? 1 : 0;
            
            // Update LED Status (Prioritize Anomaly > MQTT Error > Healthy)
            bool mqtt_ok = mqttClient.connected();
            if (predicted_class == 1) {
                statusLed.setInferenceAnomaly();
            } else if (!mqtt_ok) {
                statusLed.setMqttError();
            } else {
                statusLed.setInferenceHealthy();
            }

            // Publish via MQTT: Only flag anomalies, rate-limited to avoid spam
            static uint32_t last_anomaly_pub = 0;
            if (mqtt_ok && predicted_class == 1) {
                if (millis() - last_anomaly_pub > 10000) { // Max 1 alert per 10 seconds
                    last_anomaly_pub = millis();
                    String payload = "{\"id\": \"" + nvs.getDeviceId() + "\", \"status\": \"anomaly\", \"score\": " + String(prediction) + "}";
                    String topic = nvs.getMqttTopic();
                    if (topic == "") topic = Config::MQTT_TOPIC;
                    mqttClient.publish(topic.c_str(), payload.c_str());
                }
            }

            last_prediction_score = prediction;
            last_predicted_class = predicted_class;

            if (cli_logs_enabled) {
                // Print directly instead of using Logger::info so the PC app doesn't try to parse it as JSON
                Serial.printf(">>> [%s] Score: %.4f | Status: %s\n", 
                    mqtt_ok ? "MQTT ONLINE" : "MQTT OFFLINE",
                    prediction, predicted_class == 1 ? "ANOMALY" : "HEALTHY");
            }
        }
    }
}
