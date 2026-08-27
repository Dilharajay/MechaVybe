#pragma once
#include <Arduino.h>
#include <Adafruit_NeoPixel.h>

enum class LedPattern {
    OFF,
    SOLID,
    SLOW_PULSE,
    FAST_FLASH,
    DOUBLE_BLINK,
    RAPID_STROBE
};

class LedManager {
public:
    LedManager();
    
    void begin();
    void update(); // Must be called in loop()
    
    void setColor(uint8_t r, uint8_t g, uint8_t b); // Legacy compatibility
    
    void setWifiConnecting();
    void setWifiConnected();
    void setWifiError();
    void setMqttError();
    void setOtaUpdating();
    void setPcConnected();
    void setInferenceHealthy();
    void setInferenceAnomaly();
    void setDataCollection();
    void setModeSwitching();
    void turnOff();

private:
    Adafruit_NeoPixel pixels;
    LedPattern currentPattern = LedPattern::OFF;
    uint8_t r_val=255, g_val=0, b_val=0; // Default to red
};
