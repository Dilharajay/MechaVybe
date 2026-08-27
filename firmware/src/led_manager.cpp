#include "led_manager.h"
#include "config.h"

LedManager::LedManager() 
    : pixels(Config::WS2812_NUM_LEDS, Config::WS2812_PIN, NEO_GRB + NEO_KHZ800) {
}

void LedManager::begin() {
    if (!Config::ENABLE_STATUS_LED) return;
    pixels.begin();
    pixels.setBrightness(Config::LED_BRIGHTNESS);
    turnOff();
}

void LedManager::update() {
    if (!Config::ENABLE_STATUS_LED) return;

    uint32_t now = millis();
    bool ledOn = false;

    switch (currentPattern) {
        case LedPattern::OFF:
            ledOn = false;
            break;
        case LedPattern::SOLID:
            ledOn = true;
            break;
        case LedPattern::SLOW_PULSE:
            ledOn = (now % 1000) < 500;
            break;
        case LedPattern::FAST_FLASH:
            ledOn = (now % 200) < 100;
            break;
        case LedPattern::DOUBLE_BLINK: {
            uint32_t t = now % 1000;
            ledOn = (t < 100) || (t > 200 && t < 300);
            break;
        }
        case LedPattern::RAPID_STROBE:
            ledOn = (now % 100) < 50;
            break;
    }

    if (ledOn) {
        for(int i = 0; i < Config::WS2812_NUM_LEDS; i++) {
            pixels.setPixelColor(i, pixels.Color(r_val, g_val, b_val));
        }
    } else {
        for(int i = 0; i < Config::WS2812_NUM_LEDS; i++) {
            pixels.setPixelColor(i, 0);
        }
    }
    pixels.show();
}

void LedManager::setColor(uint8_t r, uint8_t g, uint8_t b) {
    r_val = r; g_val = g; b_val = b;
    currentPattern = LedPattern::SOLID;
    update();
}

// 🟨 Yellow: Connecting to Wi-Fi
void LedManager::setWifiConnecting() {
    r_val = 255; g_val = 255; b_val = 0; 
    currentPattern = LedPattern::SOLID;
}

void LedManager::setWifiConnected() {
    r_val = 0; g_val = 255; b_val = 0; 
    currentPattern = LedPattern::SOLID;
}

void LedManager::setWifiError() {
    r_val = 255; g_val = 0; b_val = 0; 
    currentPattern = LedPattern::FAST_FLASH;
}

// 🟧 Orange (Flashing): MQTT Offline
void LedManager::setMqttError() {
    r_val = 255; g_val = 128; b_val = 0; 
    currentPattern = LedPattern::SLOW_PULSE;
}

// 🟦 Blue: OTA Update in progress
void LedManager::setOtaUpdating() {
    r_val = 0; g_val = 0; b_val = 255; 
    currentPattern = LedPattern::RAPID_STROBE;
}

void LedManager::setPcConnected() {
    r_val = 0; g_val = 255; b_val = 255; 
    currentPattern = LedPattern::SOLID;
}

// 🟩 Green: Inference Mode (Healthy)
void LedManager::setInferenceHealthy() {
    r_val = 0; g_val = 255; b_val = 0; 
    currentPattern = LedPattern::SOLID;
}

// 🟥 Red: Inference Mode (Anomaly)
void LedManager::setInferenceAnomaly() {
    r_val = 255; g_val = 0; b_val = 0; 
    currentPattern = LedPattern::SOLID;
}

// 🩵 Cyan: Data Collection Mode
void LedManager::setDataCollection() {
    r_val = 0; g_val = 255; b_val = 255; 
    currentPattern = LedPattern::SOLID;
}

// 🟪 Magenta: Mode switching
void LedManager::setModeSwitching() {
    r_val = 255; g_val = 0; b_val = 255; 
    currentPattern = LedPattern::SOLID;
}

void LedManager::turnOff() {
    currentPattern = LedPattern::OFF;
    update();
}
