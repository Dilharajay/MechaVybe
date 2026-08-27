#pragma once

#include <cstddef>
#include <cstdint>

namespace Config {
    // ==========================================
    // Wi-Fi Configuration
    // ==========================================
    constexpr char WIFI_SSID[]     = "SLT-4G-87D7";
    constexpr char WIFI_PASSWORD[] = "HJBT5JD1NY0";

    // ==========================================
    // OTA Configuration
    // ==========================================
    constexpr char OTA_HOSTNAME[]  = "esp32-s3";

    // ==========================================
    // Hardware / Serial Configuration
    // ==========================================
    constexpr uint32_t SERIAL_BAUD_RATE = 921600;
    
    // 0=DEBUG, 1=INFO, 2=WARN, 3=ERROR, 4=NONE
    constexpr int DEFAULT_LOG_LEVEL = 0;

    // ==========================================
    // I2C & MPU6050 Configuration
    // ==========================================
    constexpr int I2C_SDA_PIN = 8;
    constexpr int I2C_SCL_PIN = 9;
    constexpr int MPU_INT_PIN = 10;

    // ==========================================
    // Machine Monitoring Configuration
    // ==========================================
    constexpr int RPM_PIN = -1;             // Hall effect sensor digital pin
    constexpr float RPM_PULSES_PER_REV = 1.0f;
    constexpr int VOLTAGE_PIN = -1;         // ADC pin for voltage
    constexpr int CURRENT_PIN = -1;         // ADC pin for current
    constexpr float VOLTAGE_SCALE = 0.01f;
    constexpr float CURRENT_SCALE = 0.01f;

    // ==========================================
    // Built-in WS2812 RGB LED Configuration
    // ==========================================
    // On many ESP32-S3 boards (like DevKitC-1), the built-in RGB is on pin 48.
    constexpr int WS2812_PIN       = 48;
    constexpr int WS2812_NUM_LEDS  = 1;
    constexpr int LED_BRIGHTNESS = 10;

    // ==========================================
    // TinyML Configuration
    // ==========================================
    constexpr size_t TENSOR_ARENA_SIZE  = 32 * 1024;
    constexpr float PREDICTION_THRESHOLD = 0.5f;

    // ==========================================
    // Application Timing
    // ==========================================
    constexpr uint32_t INFERENCE_DELAY_MS = 2000;
    constexpr uint32_t ERROR_DELAY_MS     = 5000;
    constexpr uint32_t BOOT_DELAY_MS      = 2000;

    // ==========================================
    // Button Configuration
    // ==========================================
    constexpr int BUTTON_PIN = 0; // Standard BOOT button on ESP32-S3

    // ==========================================
    // MQTT Configuration
    // ==========================================
    constexpr char MQTT_SERVER[]   = "broker.hivemq.com";
    constexpr int  MQTT_PORT       = 1883;
    constexpr char MQTT_TOPIC[]    = "mechavybe/status";
}
